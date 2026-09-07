"""
Kern des gisloader-Plugins für Cinema 4D (ohne Oberfläche, damit er sich in
c4dpy prüfen lässt): Einstellungen, Server-Zugriff, Import mit Georeferenz
und die lokale Brücke.

Achsen: Cinema 4D und glTF sind beide Y-up, der Importer dreht nichts:
X = Ost, Y = Höhe, Z = −Nord. Dokumenteinheit ist Zentimeter, der glTF-Import
rechnet Meter um. Ursprung und CRS stehen als User Data am Null-Objekt.
"""

import datetime
import json
import os
import queue
import re
import shutil
import ssl
import tempfile
import threading
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import c4d

VERSION = "0.1.2"
DEFAULT_SERVER = "https://gisloader.ampsrvr.xyz"
# Cinema 4D nimmt den ersten freien Port ab 47810 (bis +9); Blender liegt ab 47800.
BRIDGE_PORT = 47810
BRIDGE_PORT_SPAN = 10
OLD_BRIDGE_PORT = 47801  # Vorgabe bis 0.1.0, wird beim Laden der Einstellungen umgestellt
IMPORT_QUEUE: "queue.Queue[dict]" = queue.Queue()
_ssl_ctx = None
DEFAULT_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads", "gisloader")

PERIODS = [
    ("week", "Diese Woche"),
    ("month", "Dieser Monat"),
    ("year", "Dieses Jahr"),
    ("all", "Alle"),
]


def in_period(created_iso, period):
    """Fällt der Zeitstempel (ISO, UTC) in den Zeitraum (Woche ab Montag, Monat, Jahr), in Ortszeit?"""
    if period == "all" or not created_iso:
        return True
    try:
        t = datetime.datetime.fromisoformat(created_iso.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return True
    now = datetime.datetime.now().astimezone()
    if period == "week":
        start = (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return t >= start


def ssl_context():
    """
    Zertifikatsprüfung: Das Python in Cinema 4D bringt kein CA-Bündel mit
    („CERTIFICATE_VERIFY_FAILED“). Wir nehmen certifi, falls vorhanden, und
    die Systembündel (macOS /etc/ssl/cert.pem, Linux ca-certificates); unter
    Windows liest Python den Zertifikatspeicher des Systems selbst.
    """
    global _ssl_ctx
    if _ssl_ctx is None:
        ctx = ssl.create_default_context()
        try:
            import certifi

            ctx.load_verify_locations(certifi.where())
        except Exception:
            pass
        for bundle in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"):
            if os.path.exists(bundle):
                try:
                    ctx.load_verify_locations(bundle)
                except Exception:
                    pass
        _ssl_ctx = ctx
    return _ssl_ctx


# ── Einstellungen (JSON im Prefs-Ordner) ────────────────────────────────


def prefs_path():
    return os.path.join(c4d.storage.GeGetC4DPath(c4d.C4D_PATH_PREFS), "gisloader.json")


def load_prefs():
    p = {
        "server": DEFAULT_SERVER,
        "email": "",
        "token": "",
        "bridge": True,
        "port": BRIDGE_PORT,
        "period": "month",
        "folder": DEFAULT_FOLDER,
        "ask_folder": True,
    }
    try:
        with open(prefs_path(), "r", encoding="utf-8") as f:
            p.update(json.load(f))
    except Exception:
        pass
    if p.get("port") == OLD_BRIDGE_PORT:
        p["port"] = BRIDGE_PORT
    return p


def save_prefs(p):
    with open(prefs_path(), "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2)


# ── Server-Zugriff ──────────────────────────────────────────────────────


def api(p, path, method="GET", body=None, raw=False, timeout=120):
    url = p["server"].rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "*/*" if raw else "application/json")
    req.add_header("User-Agent", "gisloader-cinema4d/" + VERSION)
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("Origin", p["server"].rstrip("/"))
    if p.get("token"):
        req.add_header("Authorization", "Bearer " + p["token"])
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as r:
        payload = r.read()
        token = r.headers.get("set-auth-token")
        if token:
            p["token"] = token
            save_prefs(p)
        return payload if raw else json.loads(payload.decode("utf-8"))


def describe_error(e):
    if isinstance(e, urllib.error.HTTPError):
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error") or ""
        except Exception:
            msg = ""
        return f"HTTP {e.code}" + (": " + msg if msg else "")
    return str(e)


def login(p, password):
    p["token"] = ""
    r = api(p, "/api/auth/sign-in/email", "POST", {"email": p["email"], "password": password})
    if not p.get("token") and r.get("token"):
        p["token"] = r["token"]
    save_prefs(p)
    return r.get("user", {}).get("email", p["email"])


def list_exports(p, period="all"):
    """Exporte des Kontos, auf den Zeitraum gefiltert (week/month/year/all)."""
    jobs = api(p, "/api/exports")
    out = []
    for j in jobs:
        if not in_period(j.get("createdAt", ""), period):
            continue
        b = j.get("request", {}).get("bbox", {})
        area = abs((b.get("maxX", 0) - b.get("minX", 0)) * (b.get("maxY", 0) - b.get("minY", 0))) / 1e6
        out.append(
            {
                "id": j["id"],
                "name": j.get("request", {}).get("name") or j["id"][:8],
                "created": j.get("createdAt", "")[:16].replace("T", " "),
                "state": j.get("state", ""),
                "area_km2": area,
            }
        )
    return out


def open_web(p):
    webbrowser.open(p["server"].rstrip("/") + "/")


# ── Speicherordner ──────────────────────────────────────────────────────


def resolve_folder(p, chosen=None):
    """Speicherordner: gewählter, sonst Vorgabe aus den Einstellungen, sonst Downloads, sonst Temp."""
    for c in (chosen, p.get("folder"), DEFAULT_FOLDER, os.path.join(tempfile.gettempdir(), "gisloader")):
        c = (c or "").strip()
        if not c:
            continue
        c = os.path.abspath(os.path.expanduser(c))
        try:
            os.makedirs(c, exist_ok=True)
            return c
        except OSError:
            continue
    return tempfile.gettempdir()


def export_folder(base, export_id, name):
    slug = re.sub(r"[^\w.-]+", "_", name or "export", flags=re.UNICODE).strip("_")[:40] or "export"
    folder = os.path.join(base, f"{slug}_{export_id[:8]}")
    os.makedirs(folder, exist_ok=True)
    return folder


# ── Import ──────────────────────────────────────────────────────────────


def _download(p, export_id, name, folder):
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(api(p, f"/api/exports/{export_id}/files/{name}", raw=True, timeout=600))
    return path


def _add_userdata(obj, name, value):
    dtype = c4d.DTYPE_STRING if isinstance(value, str) else c4d.DTYPE_REAL
    bc = c4d.GetCustomDataTypeDefault(dtype)
    bc[c4d.DESC_NAME] = name
    did = obj.AddUserData(bc)
    obj[did] = value


def _top_guids(doc):
    return {o.GetGUID() for o in doc.GetObjects()}


def _shaders(node):
    while node:
        yield node
        yield from _shaders(node.GetDown())
        node = node.GetNext()


def _find_texture(fn, search_dirs):
    """Texturdatei des Importers finden: absolut, relativ zu den Suchordnern oder in deren tex/-Unterordnern."""
    if not fn:
        return None
    if os.path.isabs(fn) and os.path.exists(fn):
        return fn
    base = os.path.basename(fn)
    for d in search_dirs:
        for cand in (os.path.join(d, fn), os.path.join(d, base), os.path.join(d, "tex", base)):
            if os.path.exists(cand):
                return cand
    return None


def relink_textures(doc, materials, folder, search_dirs):
    """Bitmap-Shader der importierten Materialien auf absolute Pfade unter folder/tex legen."""
    tex_dir = os.path.join(folder, "tex")
    n = 0
    for mat in materials:
        for sh in _shaders(mat.GetFirstShader()):
            if sh.GetType() != c4d.Xbitmap:
                continue
            fn = sh[c4d.BITMAPSHADER_FILENAME]
            src = _find_texture(fn, search_dirs)
            if not src:
                continue
            target = src
            if os.path.abspath(os.path.dirname(src)) != os.path.abspath(tex_dir):
                os.makedirs(tex_dir, exist_ok=True)
                target = os.path.join(tex_dir, os.path.basename(src))
                if not os.path.exists(target):
                    shutil.copy2(src, target)
            sh[c4d.BITMAPSHADER_FILENAME] = target
            n += 1
    return n


def import_export(doc, p, export_id, folder=None):
    """
    Lädt die Dateien eines Exports in den Speicherordner (Unterordner je Export),
    importiert die GLBs unter ein Null-Objekt mit Georeferenz und verknüpft die
    Texturen absolut unter <Ordner>/tex.
    """
    job = api(p, f"/api/exports/{export_id}")
    if job.get("state") != "done":
        raise RuntimeError(f"Export ist {job.get('state')}")
    files = job.get("files", [])
    name = job.get("request", {}).get("name") or export_id[:8]
    folder = export_folder(resolve_folder(p, folder), export_id, name)
    prov = None
    for f in files:
        if f["name"].endswith(".zip"):
            continue
        path = _download(p, export_id, f["name"], folder)
        if f["name"].endswith("provenance.json"):
            with open(path, "r", encoding="utf-8") as fh:
                prov = json.load(fh)
    glbs = [f["name"] for f in files if f["name"].endswith(".glb")]
    if not glbs:
        raise RuntimeError("Export enthält keine GLB")
    georef = None
    for f in (prov or {}).get("files", []):
        if f.get("georef"):
            georef = f["georef"]
            break

    doc.StartUndo()
    root = c4d.BaseObject(c4d.Onull)
    root.SetName(f"gisloader · {name}")
    doc.InsertObject(root)
    doc.AddUndo(c4d.UNDOTYPE_NEW, root)
    imported = 0
    mats_before = {m.GetGUID() for m in doc.GetMaterials()}
    for g in glbs:
        path = os.path.join(folder, g)
        before = _top_guids(doc)
        ok = c4d.documents.MergeDocument(
            doc, path, c4d.SCENEFILTER_OBJECTS | c4d.SCENEFILTER_MATERIALS | c4d.SCENEFILTER_MERGESCENE, None
        )
        if not ok:
            raise RuntimeError(f"Import von {g} fehlgeschlagen")
        new = [o for o in doc.GetObjects() if o.GetGUID() not in before and o is not root]
        for o in new:
            o.Remove()
            o.InsertUnderLast(root)
            imported += 1
    new_mats = [m for m in doc.GetMaterials() if m.GetGUID() not in mats_before]
    search = [folder, os.path.join(folder, "tex"), tempfile.gettempdir(), doc.GetDocumentPath() or ""]
    for g in glbs:
        search.append(os.path.join(folder, os.path.splitext(g)[0]))
        search.append(os.path.join(folder, os.path.splitext(g)[0] + "_tex"))
    relinked = relink_textures(doc, new_mats, folder, [d for d in search if d])
    print(f"[gisloader] {relinked} Textur(en) verknüpft unter {os.path.join(folder, 'tex')}")
    _add_userdata(root, "gisloader_export_id", export_id)
    _add_userdata(root, "gisloader_server", p["server"])
    _add_userdata(root, "gisloader_folder", folder)
    if prov:
        _add_userdata(root, "attribution", prov.get("attribution", ""))
        region = prov.get("region") or {}
        if region.get("name"):
            _add_userdata(root, "region", region["name"])
    if georef:
        origin = georef.get("origin") or {}
        _add_userdata(root, "crs", f"EPSG:{georef.get('epsg')}")
        _add_userdata(root, "crs_name", georef.get("crsName", ""))
        _add_userdata(root, "origin_x", float(origin.get("x", 0)))
        _add_userdata(root, "origin_y", float(origin.get("y", 0)))
        _add_userdata(root, "origin_z", float(origin.get("z", 0)))
        _add_userdata(root, "axis_note", "X = Ost, Y = Höhe, Z = −Nord (Y-up); Ursprung Südwest-Ecke des Ausschnitts; Einheit im Dokument cm")
    doc.EndUndo()
    c4d.EventAdd()
    return root, imported


# ── Lokale Brücke ───────────────────────────────────────────────────────

_bridge = None
_bridge_thread = None
_bridge_port = 0
_on_queued = None  # Rückruf, der den Hauptthread anstößt (SpecialEventAdd)


class BridgeHandler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/ping"):
            self._json(200, {"app": "cinema4d", "version": str(c4d.GetC4DVersion()), "addon": VERSION, "port": _bridge_port})
        else:
            self._json(404, {"error": "unbekannt"})

    def do_POST(self):
        if not self.path.startswith("/import"):
            return self._json(404, {"error": "unbekannt"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return self._json(400, {"error": "ungültiges JSON"})
        if not data.get("exportId"):
            return self._json(400, {"error": "exportId fehlt"})
        IMPORT_QUEUE.put(data)
        if _on_queued:
            _on_queued()
        self._json(202, {"queued": True})

    def log_message(self, *args):
        pass


def start_bridge(port, on_queued=None):
    """Ersten freien Port ab `port` binden, damit mehrere Instanzen nebeneinander laufen."""
    global _bridge, _bridge_thread, _bridge_port, _on_queued
    if _bridge:
        return _bridge_port
    _on_queued = on_queued
    last = None
    for candidate in range(port, port + BRIDGE_PORT_SPAN):
        try:
            _bridge = ThreadingHTTPServer(("127.0.0.1", candidate), BridgeHandler)
            _bridge_port = candidate
            break
        except OSError as e:
            last = e
    if not _bridge:
        raise OSError(f"kein freier Port {port}–{port + BRIDGE_PORT_SPAN - 1}: {last}")
    _bridge_thread = threading.Thread(target=_bridge.serve_forever, daemon=True)
    _bridge_thread.start()
    return _bridge_port


def stop_bridge():
    global _bridge, _bridge_thread, _bridge_port
    if _bridge:
        _bridge.shutdown()
        _bridge.server_close()
        _bridge = None
        _bridge_thread = None
        _bridge_port = 0


def bridge_running():
    return _bridge is not None


def bridge_port():
    return _bridge_port


def drain_queue(doc, p, choose_folder=None):
    """Im Hauptthread: alle wartenden Importe ausführen; choose_folder(p) liefert den Ordner oder None (Abbruch)."""
    done = []
    try:
        while True:
            data = IMPORT_QUEUE.get_nowait()
            server = data.get("server")
            if server and server.rstrip("/") != p["server"].rstrip("/"):
                print(f"[gisloader] Import abgelehnt: Server {server} ≠ {p['server']}")
                continue
            folder = choose_folder(p) if choose_folder else None
            if choose_folder and folder is None:
                print("[gisloader] Import abgebrochen (kein Ordner gewählt)")
                continue
            done.append(import_export(doc, p, data["exportId"], folder))
    except queue.Empty:
        pass
    return done
