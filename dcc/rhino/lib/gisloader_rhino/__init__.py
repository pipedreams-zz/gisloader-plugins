"""
gisloader für Rhino 8: Exporte des Kontos abholen und mit Georeferenz
importieren, lokale Brücke für „An Rhino senden“ aus der Web-App.

Als Plugin (Befehle `gisloader`, `gisloaderBridge`) aus dem Skriptprojekt
gisloader.rhproj gebaut; alternativ per _-RunPythonScript "<Pfad>/gisloader.py".
Das Fenster ist nicht-modal; die Brücke läuft weiter, solange Rhino offen ist
(Zustand in scriptcontext.sticky).

Georeferenz: Rhino ist Z-up und dreht glTF (Y-up) beim Import. Ursprung und
CRS stehen als Dokumenttexte (gisloader:crs, gisloader:origin_x/y/z) und, bei
UTM-Systemen, als EarthAnchorPoint (Breite/Länge des Ursprungs, Norden = +Y).
"""

import datetime
import json
import math
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

import Rhino
import scriptcontext as sc
import System
import Eto.Drawing as drawing
import Eto.Forms as forms

VERSION = "0.1.13"
DEFAULT_SERVER = "https://gisloader.ampsrvr.xyz"
# Rhino nimmt den ersten freien Port ab 47820 (bis +9); Blender ab 47800, Cinema 4D ab 47810.
BRIDGE_PORT = 47820
BRIDGE_PORT_SPAN = 10
DEFAULT_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads", "gisloader")
STICKY = "gisloader.rhino"

PERIODS = [("week", "Diese Woche"), ("month", "Dieser Monat"), ("year", "Dieses Jahr"), ("all", "Alle")]


def state():
    """Sitzungszustand (Brücke, Warteschlange, Fenster) überlebt erneute Skriptläufe."""
    st = sc.sticky.get(STICKY)
    if st is None:
        st = {"bridge": None, "thread": None, "port": 0, "queue": queue.Queue(), "form": None, "ssl": None, "last": None}
        sc.sticky[STICKY] = st
    return st


# ── Einstellungen ───────────────────────────────────────────────────────


def prefs_path():
    return os.path.join(os.path.expanduser("~"), ".gisloader", "rhino.json")


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
    return p


def save_prefs(p):
    os.makedirs(os.path.dirname(prefs_path()), exist_ok=True)
    with open(prefs_path(), "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2)


# ── Server-Zugriff ──────────────────────────────────────────────────────


def ssl_context():
    st = state()
    if st["ssl"] is None:
        ctx = ssl.create_default_context()
        try:
            import certifi

            ctx.load_verify_locations(certifi.where())
        except Exception:
            pass
        for bundle in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
            if os.path.exists(bundle):
                try:
                    ctx.load_verify_locations(bundle)
                except Exception:
                    pass
        st["ssl"] = ctx
    return st["ssl"]


def api(p, path, method="GET", body=None, raw=False, timeout=120):
    url = p["server"].rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "*/*" if raw else "application/json")
    req.add_header("User-Agent", "gisloader-rhino/" + VERSION)
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


def in_period(created_iso, period):
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


def list_exports(p, period="all"):
    out = []
    for j in api(p, "/api/exports"):
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


# ── Speicherordner ──────────────────────────────────────────────────────


def resolve_folder(p, chosen=None):
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


def _download(p, export_id, name, folder):
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(api(p, f"/api/exports/{export_id}/files/{name}", raw=True, timeout=600))
    return path


# ── Georeferenz: UTM (ETRS89/GRS80) → Breite/Länge ──────────────────────


def utm_to_latlon(easting, northing, zone):
    a = 6378137.0
    f = 1 / 298.257222101
    k0 = 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    x = easting - 500000.0
    m = northing / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
    )
    n1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = ep2 * math.cos(phi1) ** 2
    r1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * k0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * ep2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * ep2 - 3 * c1**2) * d**6 / 720
    )
    lon = math.radians(zone * 6 - 183) + (
        d - (1 + 2 * t1 + c1) * d**3 / 6 + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * ep2 + 24 * t1**2) * d**5 / 120
    ) / math.cos(phi1)
    return math.degrees(lat), math.degrees(lon)


UTM_ZONES = {25832: 32, 25833: 33, 4647: 32}


# ── Import ──────────────────────────────────────────────────────────────


def _glb_materials(path):
    """Materialnamen der GLB mit Texturkennung (JSON-Chunk)."""
    import struct

    with open(path, "rb") as f:
        magic, _v, _l = struct.unpack("<III", f.read(12))
        if magic != 0x46546C67:
            return {}
        n, t = struct.unpack("<II", f.read(8))
        if t != 0x4E4F534A:
            return {}
        gltf = json.loads(f.read(n).decode("utf-8"))
    return {m.get("name", ""): "baseColorTexture" in m.get("pbrMetallicRoughness", {}) for m in gltf.get("materials", [])}


def _relink_textures(doc, mats_before, folder, glbs):
    """
    Texturen als Dateien unter tex/ und absolut im Material verknüpfen. Rhino
    bettet glTF-Bilder ins Dokument ein; wo eine Datei bekannt ist (Textur des
    Geländes liegt als JPEG im Export), wird sie nach tex/ kopiert und gesetzt.
    """
    tex_dir = os.path.join(folder, "tex")
    textured = {}
    for g in glbs:
        textured.update(_glb_materials(os.path.join(folder, g)))
    jpgs = [f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    n = 0
    for i in range(mats_before, doc.Materials.Count):
        mat = doc.Materials[i]
        if mat is None or mat.IsDeleted:
            continue
        name = mat.Name or ""
        tex = mat.GetBitmapTexture()
        src = None
        if tex is not None and tex.FileName and os.path.exists(tex.FileName):
            src = tex.FileName
        elif textured.get(name):
            cands = [f for f in jpgs if name.lower() in f.lower()] or ([f for f in jpgs if "texture" in f.lower()] if name == "terrain" else [])
            if cands:
                src = os.path.join(folder, cands[0])
        if not src:
            continue
        os.makedirs(tex_dir, exist_ok=True)
        target = os.path.join(tex_dir, os.path.basename(src))
        if os.path.abspath(src) != os.path.abspath(target) and not os.path.exists(target):
            shutil.copy2(src, target)
        mat.SetBitmapTexture(target)
        mat.CommitChanges()
        n += 1
    return n


BUILDING_KINDS = {
    "dach": "Dach",
    "roof": "Dach",
    "wand": "Wand",
    "wall": "Wand",
    "boden": "Boden",
    "ground": "Boden",
    "grund": "Boden",
    "footprint": "Grundriss",
}


def _kind_of(doc, obj):
    """Bauteilart eines importierten Gebäudeobjekts aus Objekt- oder Materialname."""
    name = (obj.Name or "").strip().lower()
    for key, kind in BUILDING_KINDS.items():
        if name.startswith(key):
            return kind
    try:
        mi = obj.Attributes.MaterialIndex
        mat = doc.Materials[mi] if mi >= 0 else None
        mname = (mat.Name or "").lower() if mat else ""
        for key, kind in BUILDING_KINDS.items():
            if key in mname:
                return kind
    except Exception:
        pass
    return "Sonstige"


def _flatten_building_layers(doc, new_objs, new_layers):
    """
    Der glTF-Importer legt je Gebäude eine Ebene an (gml:id). Für Rhino genügt je
    Bauteilart eine Ebene (Gebaeude/Dach, Gebaeude/Wand …); die gml:id bleibt als
    Benutzertext am Objekt, die leeren Gebäudeebenen verschwinden.
    """
    parents = [l for l in new_layers if (l.Name or "").lower() in ("gebaeude", "gebäude", "buildings")]
    if not parents:
        return 0
    parent = parents[0]
    building_layers = {l.Index: l for l in new_layers if l.ParentLayerId == parent.Id}
    if not building_layers:
        return 0
    kind_layers = {}
    moved = 0
    for o in new_objs:
        src = building_layers.get(o.Attributes.LayerIndex)
        if src is None:
            continue
        kind = _kind_of(doc, o)
        if kind not in kind_layers:
            existing = doc.Layers.FindByFullPath(parent.FullPath + "::" + kind, -1)
            if existing >= 0:
                kind_layers[kind] = existing
            else:
                layer = Rhino.DocObjects.Layer()
                layer.Name = kind
                layer.ParentLayerId = parent.Id
                layer.Color = src.Color
                kind_layers[kind] = doc.Layers.Add(layer)
        attrs = o.Attributes
        attrs.LayerIndex = kind_layers[kind]
        attrs.SetUserString("gml_id", src.Name or "")
        doc.Objects.ModifyAttributes(o, attrs, True)
        moved += 1
    for idx, layer in building_layers.items():
        if not doc.Objects.FindByLayer(layer):
            doc.Layers.Delete(idx, True)
    return moved


def import_export(doc, p, export_id, folder=None):
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

    ids_before = {o.Id for o in doc.Objects}
    layers_before = {l.Id for l in doc.Layers}
    mats_before = doc.Materials.Count
    for g in glbs:
        if not doc.Import(os.path.join(folder, g)):
            raise RuntimeError(f"Import von {g} fehlgeschlagen")
    new_objs = [o for o in doc.Objects if o.Id not in ids_before]
    # Maßstab: glTF ist in Metern; Rhino rechnet beim Import in die Dokumenteinheit um
    # (geprüft mit einem Zentimeter-Dokument: Faktor 100 wird angewandt).
    unit_scale = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Meters, doc.ModelUnitSystem)
    bbox = Rhino.Geometry.BoundingBox.Empty
    for o in new_objs:
        bbox.Union(o.Geometry.GetBoundingBox(True))
    # Ebene je Export; vom Importer angelegte Ebenen darunter hängen
    parent = Rhino.DocObjects.Layer()
    parent.Name = f"gisloader · {name}"
    parent_idx = doc.Layers.Add(parent)
    parent_id = doc.Layers[parent_idx].Id
    new_layers = [l for l in doc.Layers if l.Id not in layers_before and l.Id != parent_id]
    for l in new_layers:
        if l.ParentLayerId == System.Guid.Empty or l.ParentLayerId not in {x.Id for x in new_layers}:
            l.ParentLayerId = parent_id
    default_idx = doc.Layers.FindByFullPath("Default", -1)
    for o in new_objs:
        attrs = o.Attributes
        if not new_layers or attrs.LayerIndex == default_idx:
            attrs.LayerIndex = parent_idx
        attrs.SetUserString("gisloader_export_id", export_id)
        if prov and prov.get("attribution"):
            attrs.SetUserString("attribution", prov.get("attribution", ""))
        doc.Objects.ModifyAttributes(o, attrs, True)

    _flatten_building_layers(doc, new_objs, new_layers)
    new_layers = [l for l in doc.Layers if l.Id not in layers_before and not l.IsDeleted]
    relinked = _relink_textures(doc, mats_before, folder, glbs)

    doc.Strings.SetString("gisloader:export_id", export_id)
    doc.Strings.SetString("gisloader:server", p["server"])
    doc.Strings.SetString("gisloader:folder", folder)
    if georef:
        epsg = int(georef.get("epsg") or 0)
        origin = georef.get("origin") or {}
        ox, oy, oz = float(origin.get("x", 0)), float(origin.get("y", 0)), float(origin.get("z", 0))
        doc.Strings.SetString("gisloader:crs", f"EPSG:{epsg}")
        doc.Strings.SetString("gisloader:crs_name", georef.get("crsName", ""))
        doc.Strings.SetString("gisloader:origin_x", repr(ox))
        doc.Strings.SetString("gisloader:origin_y", repr(oy))
        doc.Strings.SetString("gisloader:origin_z", repr(oz))
        doc.Strings.SetString("gisloader:axis_note", "X = Ost, Y = Nord, Z = Höhe (Z-up); Ursprung Südwest-Ecke des Ausschnitts; Ursprung in Metern, Modell in Dokumenteinheit")
        zone = UTM_ZONES.get(epsg)
        if zone:
            lat, lon = utm_to_latlon(ox, oy, zone)
            ea = Rhino.DocObjects.EarthAnchorPoint()
            ea.EarthBasepointLatitude = lat
            ea.EarthBasepointLongitude = lon
            ea.EarthBasepointElevation = oz
            ea.ModelBasePoint = Rhino.Geometry.Point3d(0, 0, 0)
            ea.ModelNorth = Rhino.Geometry.Vector3d(0, 1, 0)
            ea.ModelEast = Rhino.Geometry.Vector3d(1, 0, 0)
            ea.Name = f"gisloader · {name}"
            ea.Description = f"EPSG:{epsg} Ursprung {ox:.2f} / {oy:.2f}"
            doc.EarthAnchorPoint = ea
    doc.Views.Redraw()
    # Zusammenfassung für /ping (Fehlersuche ohne Blick in Rhino).
    anchor = doc.EarthAnchorPoint
    state()["last"] = {
        "name": name,
        "objects": len(new_objs),
        "layers": [l.FullPath for l in new_layers],
        "relinked": relinked,
        "folder": folder,
        "units": str(doc.ModelUnitSystem),
        "unit_scale": unit_scale,
        "extent": [round(bbox.Max.X - bbox.Min.X, 3), round(bbox.Max.Y - bbox.Min.Y, 3), round(bbox.Max.Z - bbox.Min.Z, 3)] if new_objs else None,
        "materials": [
            {"name": doc.Materials[i].Name, "texture": (doc.Materials[i].GetBitmapTexture().FileName if doc.Materials[i].GetBitmapTexture() else None)}
            for i in range(mats_before, doc.Materials.Count)
            if doc.Materials[i] is not None and not doc.Materials[i].IsDeleted
        ],
        "anchor": {"lat": anchor.EarthBasepointLatitude, "lon": anchor.EarthBasepointLongitude} if anchor.EarthLocationIsSet() else None,
    }
    return name, len(new_objs), relinked, folder


# ── Lokale Brücke ───────────────────────────────────────────────────────


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
            self._json(200, {"app": "rhino", "version": str(Rhino.RhinoApp.Version), "addon": VERSION, "port": state()["port"], "form": state()["form"] is not None, "last": state()["last"]})
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
        state()["queue"].put(data)
        Rhino.RhinoApp.InvokeOnUiThread(System.Action(drain_queue))
        self._json(202, {"queued": True})

    def log_message(self, *args):
        pass


def start_bridge(port):
    st = state()
    if st["bridge"]:
        return st["port"]
    last = None
    for candidate in range(port, port + BRIDGE_PORT_SPAN):
        try:
            st["bridge"] = ThreadingHTTPServer(("127.0.0.1", candidate), BridgeHandler)
            st["port"] = candidate
            break
        except OSError as e:
            last = e
    if not st["bridge"]:
        raise OSError(f"kein freier Port {port}–{port + BRIDGE_PORT_SPAN - 1}: {last}")
    st["thread"] = threading.Thread(target=st["bridge"].serve_forever, daemon=True)
    st["thread"].start()
    return st["port"]


def stop_bridge():
    st = state()
    if st["bridge"]:
        st["bridge"].shutdown()
        st["bridge"].server_close()
        st["bridge"] = None
        st["thread"] = None
        st["port"] = 0


def apply_bridge(p):
    try:
        stop_bridge()
        if p.get("bridge", True):
            start_bridge(int(p.get("port", BRIDGE_PORT)))
    except OSError as e:
        print("[gisloader] Brücke konnte nicht starten:", e)


def choose_folder(p, parent=None):
    if not p.get("ask_folder", True):
        return resolve_folder(p)
    dlg = forms.SelectFolderDialog()
    dlg.Title = "Speicherordner für diesen Export"
    dlg.Directory = resolve_folder(p)
    if dlg.ShowDialog(parent) == forms.DialogResult.Ok:
        return dlg.Directory
    return None


def drain_queue():
    """Im UI-Thread: wartende Importe der Brücke ausführen."""
    st = state()
    p = load_prefs()
    doc = Rhino.RhinoDoc.ActiveDoc
    while True:
        try:
            data = st["queue"].get_nowait()
        except queue.Empty:
            return
        server = data.get("server")
        if server and server.rstrip("/") != p["server"].rstrip("/"):
            print(f"[gisloader] Import abgelehnt: Server {server} ≠ {p['server']}")
            continue
        folder = choose_folder(p, st["form"])
        if folder is None:
            print("[gisloader] Import abgebrochen (kein Ordner gewählt)")
            continue
        try:
            name, n, relinked, out = import_export(doc, p, data["exportId"], folder)
            msg = f"{n} Objekte in „gisloader · {name}“, {relinked} Textur(en), Dateien unter {out}"
            print("[gisloader]", msg)
            if st["form"] is not None:
                st["form"].status(msg)
        except Exception as e:
            print("[gisloader] Import über Brücke fehlgeschlagen:", describe_error(e))


# ── Fenster (Eto, nicht-modal) ──────────────────────────────────────────


def _text(cls, text):
    c = cls()
    c.Text = text
    return c


PASSWORD_DUMMY = "••••••••"


class GisloaderForm(forms.Form):
    def __init__(self):
        super().__init__()
        self.p = load_prefs()
        self.exports = []
        self.Title = f"gisloader {VERSION}"
        self.Padding = drawing.Padding(12)
        self.Resizable = True
        self.MinimumSize = drawing.Size(640, 0)

        # pythonnet in Rhino 8 kennt keine Eigenschaften im Konstruktor: erst erzeugen, dann setzen.
        self.server = _text(forms.TextBox, self.p["server"])
        self.email = _text(forms.TextBox, self.p["email"])
        self.password = forms.PasswordBox()
        if self.p.get("token"):
            self.password.Text = PASSWORD_DUMMY
        self.btn_login = _text(forms.Button, "🔑 Anmelden")
        self.btn_logout = _text(forms.Button, "⏏ Abmelden")
        self.btn_refresh = _text(forms.Button, "⟳ Exporte aktualisieren")
        self.btn_web = _text(forms.Button, "🌐 gisloader im Browser")
        self.period = forms.DropDown()
        for _, label in PERIODS:
            self.period.Items.Add(label)
        ids = [k for k, _ in PERIODS]
        self.period.SelectedIndex = ids.index(self.p.get("period", "month")) if self.p.get("period") in ids else 1
        self.list = forms.DropDown()
        self.btn_import = _text(forms.Button, "⬇ Importieren")
        self.folder = _text(forms.TextBox, self.p.get("folder") or DEFAULT_FOLDER)
        self.btn_folder = _text(forms.Button, "📁 Wählen …")
        self.ask = _text(forms.CheckBox, "Beim Import fragen")
        self.ask.Checked = bool(self.p.get("ask_folder", True))
        self.bridge = forms.CheckBox()
        self.bridge.Checked = bool(self.p.get("bridge", True))
        self.lbl_status = forms.Label()
        self.lbl_status.Wrap = forms.WrapMode.Word

        self.btn_login.Click += self.on_login
        self.btn_logout.Click += self.on_logout
        self.btn_refresh.Click += lambda s, e: self.refresh()
        self.btn_web.Click += lambda s, e: webbrowser.open(self.p["server"].rstrip("/") + "/")
        self.period.SelectedIndexChanged += lambda s, e: (self.sync_prefs(), self.refresh())
        self.btn_import.Click += self.on_import
        self.btn_folder.Click += self.on_folder
        self.ask.CheckedChanged += lambda s, e: self.sync_prefs()
        self.bridge.CheckedChanged += self.on_bridge
        self.Closed += self.on_closed

        def hstack(*controls):
            st = forms.StackLayout()
            st.Orientation = forms.Orientation.Horizontal
            st.Spacing = 6
            st.VerticalContentAlignment = forms.VerticalAlignment.Center
            for c in controls:
                st.Items.Add(forms.StackLayoutItem(c))
            return st

        def row(label, control):
            cells = [forms.TableCell(_text(forms.Label, label) if label else None), forms.TableCell(control, True)]
            return forms.TableRow(*cells)

        def split(left, right):
            """Zweispaltig: links dehnbar, rechts natürliche Breite."""
            t = forms.TableLayout()
            t.Spacing = drawing.Size(6, 0)
            t.Rows.Add(forms.TableRow(forms.TableCell(left, True), forms.TableCell(right)))
            return t

        table = forms.TableLayout()
        table.Spacing = drawing.Size(8, 6)
        table.Rows.Add(row("Server", self.server))
        table.Rows.Add(row("E-Mail", self.email))
        table.Rows.Add(row("Passwort", self.password))
        table.Rows.Add(row(None, hstack(self.btn_login, self.btn_logout, self.btn_refresh, self.btn_web)))
        table.Rows.Add(row("Zeitraum", split(self.period, None)))
        table.Rows.Add(row("Export", split(self.list, self.btn_import)))
        table.Rows.Add(row("Ordner", split(self.folder, hstack(self.btn_folder, self.ask))))
        table.Rows.Add(row("Brücke", self.bridge))
        table.Rows.Add(row(None, self.lbl_status))
        spacer = forms.TableRow()
        spacer.ScaleHeight = True  # fängt zusätzliche Höhe ab, damit die Felder nicht wachsen
        table.Rows.Add(spacer)
        self.Content = table
        self.update_bridge_label()
        self.status("Angemeldet" if self.p.get("token") else "Nicht angemeldet")
        if self.p.get("token"):
            self.refresh()

    def status(self, text):
        self.lbl_status.Text = text

    def period_id(self):
        i = self.period.SelectedIndex
        return PERIODS[i][0] if 0 <= i < len(PERIODS) else "all"

    def update_bridge_label(self):
        port = state()["port"] or self.p.get("port", BRIDGE_PORT)
        self.bridge.Text = f"127.0.0.1:{port} für „An Rhino senden“ aus der Web-App"

    def sync_prefs(self):
        self.p["server"] = self.server.Text.strip() or DEFAULT_SERVER
        self.p["email"] = self.email.Text.strip()
        self.p["period"] = self.period_id()
        self.p["folder"] = self.folder.Text.strip() or DEFAULT_FOLDER
        self.p["ask_folder"] = bool(self.ask.Checked)
        self.p["bridge"] = bool(self.bridge.Checked)
        save_prefs(self.p)

    def refresh(self):
        try:
            self.exports = list_exports(self.p, self.period_id())
        except Exception as e:
            self.status("Liste: " + describe_error(e))
            return
        self.list.Items.Clear()
        for ex in self.exports:
            mark = "✓" if ex["state"] == "done" else "…"
            self.list.Items.Add(f"{mark} {ex['name']} · {ex['area_km2']:.3f} km² · {ex['created']}")
        if self.exports:
            self.list.SelectedIndex = 0
        self.status(f"{len(self.exports)} Exporte im Zeitraum")

    def on_login(self, sender, e):
        self.sync_prefs()
        pw = self.password.Text
        if pw == PASSWORD_DUMMY and self.p.get("token"):
            self.status("Bereits angemeldet als " + (self.p.get("email") or ""))
            self.refresh()
            return
        try:
            who = login(self.p, pw)
            self.password.Text = PASSWORD_DUMMY
            self.status("Angemeldet als " + who)
            self.refresh()
        except Exception as ex:
            self.status("Anmeldung: " + describe_error(ex))

    def on_logout(self, sender, e):
        self.p["token"] = ""
        save_prefs(self.p)
        self.password.Text = ""
        self.list.Items.Clear()
        self.status("Abgemeldet")

    def on_folder(self, sender, e):
        dlg = forms.SelectFolderDialog()
        dlg.Title = "Speicherordner für gisloader-Exporte"
        dlg.Directory = resolve_folder(self.p, self.folder.Text.strip())
        if dlg.ShowDialog(self) == forms.DialogResult.Ok:
            self.folder.Text = dlg.Directory
            self.sync_prefs()

    def on_import(self, sender, e):
        idx = self.list.SelectedIndex
        if idx < 0 or idx >= len(self.exports):
            self.status("Kein Export ausgewählt")
            return
        self.sync_prefs()
        folder = choose_folder(self.p, self)
        if folder is None:
            self.status("Import abgebrochen")
            return
        try:
            name, n, relinked, out = import_export(Rhino.RhinoDoc.ActiveDoc, self.p, self.exports[idx]["id"], folder)
            self.status(f"{n} Objekte in „gisloader · {name}“, {relinked} Textur(en) · {out}")
        except Exception as ex:
            self.status("Import: " + describe_error(ex))

    def on_bridge(self, sender, e):
        self.sync_prefs()
        apply_bridge(self.p)
        self.update_bridge_label()
        self.status(f"Brücke läuft auf Port {state()['port']}" if state()["bridge"] else "Brücke aus")

    def on_closed(self, sender, e):
        # Brücke läuft weiter; nur das Fenster verschwindet.
        state()["form"] = None


def log_error(where):
    """Traceback in die Rhino-Kommandozeile und nach ~/.gisloader/rhino.log (Fehlersuche)."""
    import traceback

    text = f"[gisloader] {where}:\n{traceback.format_exc()}"
    print(text)
    try:
        os.makedirs(os.path.dirname(prefs_path()), exist_ok=True)
        with open(os.path.join(os.path.dirname(prefs_path()), "rhino.log"), "a", encoding="utf-8") as f:
            f.write(datetime.datetime.now().isoformat(timespec="seconds") + " " + text + "\n")
    except Exception:
        pass


def main():
    st = state()
    p = load_prefs()
    if p.get("bridge", True) and not st["bridge"]:
        apply_bridge(p)
    if st["form"] is not None:
        try:
            st["form"].BringToFront()
            return
        except Exception:
            st["form"] = None
    try:
        form = GisloaderForm()
        form.Owner = Rhino.UI.RhinoEtoApp.MainWindow
        form.Show()
        st["form"] = form
    except Exception:
        log_error("Fenster konnte nicht geöffnet werden")


def bridge_only():
    """Befehl gisloaderBridge: nur die Brücke starten (für die Startbefehle von Rhino)."""
    st = state()
    p = load_prefs()
    if p.get("bridge", True) and not st["bridge"]:
        apply_bridge(p)
    print(f"[gisloader] Brücke {'läuft auf Port ' + str(st['port']) if st['bridge'] else 'aus'}")


if __name__ == "__main__":
    main()
