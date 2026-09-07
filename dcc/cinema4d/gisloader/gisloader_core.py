"""
Kern des gisloader-Plugins für Cinema 4D (ohne Oberfläche, damit er sich in
c4dpy prüfen lässt): Einstellungen, Server-Zugriff, Import mit Georeferenz
und die lokale Brücke.

Achsen: Cinema 4D und glTF sind beide Y-up, der Importer dreht nichts:
X = Ost, Y = Höhe, Z = −Nord. Dokumenteinheit ist Zentimeter, der glTF-Import
rechnet Meter um. Ursprung und CRS stehen als User Data am Null-Objekt.
"""

import datetime
import glob
import json
import os
import queue
import re
import shutil
import ssl
import struct
import tempfile
import threading
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import c4d

try:
    import maxon
except ImportError:  # pragma: no cover – alte Versionen ohne Node-API
    maxon = None

VERSION = "0.1.7"
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
        "corona": False,
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


def _target_for(fn, tex_dir):
    base = os.path.basename(str(fn).split("?")[0].rstrip("/")) or "texture"
    if not os.path.splitext(base)[1]:
        base += ".png"
    return os.path.join(tex_dir, base)


def _materialize(doc, fn, tex_dir, shader=None):
    """
    Bild hinter einem Pfad als Datei unter tex/ ablegen und den Zielpfad liefern.
    Der glTF-Importer legt eingebettete Bilder auf einer virtuellen Ramdisk ab
    (ramdisk://…); Reihenfolge der Versuche: Datei liegt schon auf der Platte,
    maxon-Url-Stream kopieren, BaseBitmap.InitWith, Bitmap aus dem Shader.
    """
    fn = str(fn or "")
    target = _target_for(fn, tex_dir)
    if os.path.exists(target):
        return target
    os.makedirs(tex_dir, exist_ok=True)
    if fn and not fn.startswith("ramdisk://") and os.path.exists(fn):
        shutil.copy2(fn, target)
        return target
    if maxon is not None and fn:
        try:
            stream = maxon.Url(fn).OpenInputStream()
            data = stream.ReadEOS()
            stream.Close()
            if data:
                with open(target, "wb") as f:
                    f.write(bytes(data))
                return target
        except Exception as e:
            print(f"[gisloader] Url-Stream für {fn} nicht lesbar: {e}")
    bmp = c4d.bitmaps.BaseBitmap()
    ok = False
    try:
        ok = fn != "" and bmp.InitWith(fn)[0] == c4d.IMAGERESULT_OK
    except Exception:
        ok = False
    if not ok and shader is not None:
        irs = c4d.modules.render.InitRenderStruct(doc)
        if shader.InitRender(irs) == c4d.INITRENDERRESULT_OK:
            got = shader.GetBitmap()
            shader.FreeRender()
            if got:
                bmp, ok = got, True
    if not ok:
        return None
    fmt = c4d.FILTER_JPG if target.lower().endswith((".jpg", ".jpeg")) else c4d.FILTER_PNG
    if bmp.Save(target, fmt) != c4d.IMAGERESULT_OK:
        return None
    return target


def relink_textures(doc, materials, folder, search_dirs):
    """Texturen der importierten Materialien (Bitmap-Shader und Node-Materialien) nach tex/ legen."""
    tex_dir = os.path.join(folder, "tex")
    n = 0
    for mat in materials:
        for sh in _shaders(mat.GetFirstShader()):
            if sh.GetType() != c4d.Xbitmap:
                continue
            fn = sh[c4d.BITMAPSHADER_FILENAME] or ""
            src = _find_texture(fn, search_dirs)
            target = _materialize(doc, src or fn, tex_dir, sh)
            if not target:
                print(f"[gisloader] Textur nicht sicherbar: {fn}")
                continue
            sh[c4d.BITMAPSHADER_FILENAME] = target
            n += 1
        try:
            n += _relink_node_material(doc, mat, tex_dir)
        except Exception as e:
            print(f"[gisloader] Node-Material {mat.GetName()} nicht umgelegt: {e!r}")
    return n


# Node-Spaces und ihre Bildknoten: (Space-ID, Pfad des URL-Ports in den Eingängen)
NODE_IMAGE_PORTS = [
    (maxon.Id("net.maxon.nodespace.standard") if maxon else None, ("url",)),
    (maxon.Id("com.redshift3d.redshift4c4d.class.nodespace") if maxon else None, ("tex0", "path")),
]


def _find_port(node, path):
    port = node.GetInputs()
    for seg in path:
        port = port.FindChild(seg)
        if port is None or not port.IsValid():
            return None
    return port


def _port_value(port):
    for getter in ("GetPortValue", "GetDefaultValue"):
        fn = getattr(port, getter, None)
        if fn:
            try:
                v = fn()
                if v is not None:
                    return v
            except Exception:
                pass
    return None


def _relink_node_material(doc, mat, tex_dir):
    """Image-Knoten eines Node-Materials (Standard oder Redshift) auf Dateien unter tex/ umlegen."""
    if maxon is None:
        return 0
    nm = mat.GetNodeMaterialReference()
    if nm is None:
        return 0
    n = 0
    for space, path in NODE_IMAGE_PORTS:
        if space is None or not nm.HasSpace(space):
            continue
        graph = nm.GetGraph(space)
        if graph is None or graph.IsNullValue():
            continue
        root = graph.GetViewRoot()
        with graph.BeginTransaction() as tr:
            for node in root.GetInnerNodes(mask=maxon.NODE_KIND.NODE, includeThis=False):
                port = _find_port(node, path)
                if port is None:
                    continue
                current = _port_value(port)
                fn = str(current) if current is not None else ""
                if not fn or (not fn.startswith("ramdisk://") and os.path.exists(fn) and os.path.dirname(fn) == tex_dir):
                    continue
                target = _materialize(doc, fn, tex_dir)
                if not target:
                    print(f"[gisloader] Node-Textur nicht sicherbar: {fn}")
                    continue
                url = maxon.Url()
                url.SetSystemPath(target)
                port.SetPortValue(url)
                n += 1
            tr.Commit()
    return n


# ── Corona Renderer ────────────────────────────────────────────────────

CORONA_PHYSICAL_MTL = 1056306  # Corona Physical Material (ab Corona 7)
CORONA_LEGACY_MTL = 1032100  # Corona Material (klassisch)
CORONA_BITMAP = 1036473  # Corona Bitmap Shader


def corona_available():
    return any(
        c4d.plugins.FindPlugin(i, c4d.PLUGINTYPE_MATERIAL) is not None
        for i in (CORONA_PHYSICAL_MTL, CORONA_LEGACY_MTL)
    )


def _glb_materials(path):
    """Materialien der GLB (Name, Grundfarbe, ob Textur) aus dem JSON-Chunk lesen."""
    with open(path, "rb") as f:
        magic, _version, _length = struct.unpack("<III", f.read(12))
        if magic != 0x46546C67:
            return []
        chunk_len, chunk_type = struct.unpack("<II", f.read(8))
        if chunk_type != 0x4E4F534A:
            return []
        gltf = json.loads(f.read(chunk_len).decode("utf-8"))
    out = []
    for m in gltf.get("materials", []):
        pbr = m.get("pbrMetallicRoughness", {})
        factor = pbr.get("baseColorFactor", [1, 1, 1, 1])
        out.append({"name": m.get("name", ""), "color": factor[:3], "textured": "baseColorTexture" in pbr})
    return out


def _lin_to_srgb(v):
    return v * 12.92 if v <= 0.0031308 else 1.055 * (v ** (1 / 2.4)) - 0.055


def _desc_params(node):
    """(Name, Gruppenname, DescID, DTYPE) aller Parameter einer Beschreibung."""
    desc = node.GetDescription(c4d.DESCFLAGS_DESC_NONE)
    groups = {}
    entries = []
    for bc, pid, gid in desc:
        name = bc[c4d.DESC_NAME] or bc[c4d.DESC_SHORT_NAME] or ""
        dtype = pid[-1].dtype if pid.GetDepth() else 0
        if dtype == c4d.DTYPE_GROUP:
            groups[str(pid)] = name
        entries.append((name, str(gid), pid, dtype))
    return [(n, groups.get(g, ""), pid, dt) for n, g, pid, dt in entries]


def _find_param(params, dtype, names):
    """Ersten Parameter mit Typ dtype finden, dessen Name oder Gruppenname eines der Muster enthält."""
    for pattern in names:
        pat = pattern.lower()
        for name, group, pid, dt in params:
            if dt == dtype and (pat in name.lower() or pat in group.lower()):
                return pid, name, group
    return None


def _corona_material(doc, name, color, texture_path):
    """Corona-Material mit Grundfarbe oder Textur anlegen; Parameter-IDs kommen aus der Beschreibung."""
    mtl_id = CORONA_PHYSICAL_MTL if c4d.plugins.FindPlugin(CORONA_PHYSICAL_MTL, c4d.PLUGINTYPE_MATERIAL) else CORONA_LEGACY_MTL
    mat = c4d.BaseMaterial(mtl_id)
    if mat is None:
        return None
    mat.SetName(name)
    params = _desc_params(mat)
    color_param = _find_param(params, c4d.DTYPE_COLOR, ["base color", "diffuse color", "diffuse", "color"])
    tex_param = _find_param(params, c4d.DTYPE_BASELISTLINK, ["base color", "diffuse", "color"])
    if color_param and color is not None:
        mat[color_param[0]] = c4d.Vector(*[_lin_to_srgb(max(0.0, min(1.0, c))) for c in color])
    if texture_path and tex_param:
        shader = c4d.BaseShader(CORONA_BITMAP) if c4d.plugins.FindPlugin(CORONA_BITMAP, c4d.PLUGINTYPE_SHADER) else None
        if shader is not None:
            sp = _desc_params(shader)
            fparam = _find_param(sp, c4d.DTYPE_FILENAME, ["filename", "file", "path", "image"])
            if fparam:
                shader[fparam[0]] = texture_path
            else:
                shader = None
        if shader is None:
            shader = c4d.BaseShader(c4d.Xbitmap)
            shader[c4d.BITMAPSHADER_FILENAME] = texture_path
        mat.InsertShader(shader)
        mat[tex_param[0]] = shader
    elif texture_path:
        print(f"[gisloader] Corona: kein Textur-Slot in {mat.GetTypeName()} gefunden; Parameter: "
              + ", ".join(f"{n}/{g}" for n, g, _, dt in params if dt == c4d.DTYPE_BASELISTLINK)[:800])
    mat.Update(True, True)
    doc.InsertMaterial(mat)
    doc.AddUndo(c4d.UNDOTYPE_NEW, mat)
    return mat


def _walk(obj):
    while obj:
        yield obj
        yield from _walk(obj.GetDown())
        obj = obj.GetNext()


def convert_to_corona(doc, root, glb_paths, materials, tex_dir):
    """
    Für jedes Material der GLBs ein Corona-Material anlegen (Farbe aus baseColorFactor,
    Textur aus tex/), Texture-Tags unter root umhängen, importierte Materialien entfernen.
    Liefert die Zahl der ersetzten Materialien.
    """
    by_name = {}
    for g in glb_paths:
        for m in _glb_materials(g):
            by_name.setdefault(m["name"], m)
    created = {}
    for mat in materials:
        name = mat.GetName()
        info = by_name.get(name) or by_name.get(name.split(".")[0]) or {"name": name, "color": None, "textured": False}
        texture = None
        if info["textured"] or not by_name.get(name):
            hits = sorted(glob.glob(os.path.join(tex_dir, f"{name}_*"))) + sorted(glob.glob(os.path.join(tex_dir, f"{name}.*")))
            texture = hits[0] if hits else None
        cm = _corona_material(doc, name, info["color"], texture)
        if cm is not None:
            created[name] = (mat, cm)
    if not created:
        return 0
    old_by_name = {n: pair[0] for n, pair in created.items()}
    for obj in _walk(root):
        for tag in obj.GetTags():
            if tag.GetType() != c4d.Ttexture:
                continue
            old = tag[c4d.TEXTURETAG_MATERIAL]
            if old is None:
                continue
            pair = created.get(old.GetName())
            if pair and old == pair[0]:
                doc.AddUndo(c4d.UNDOTYPE_CHANGE, tag)
                tag[c4d.TEXTURETAG_MATERIAL] = pair[1]
    for name, (old, _cm) in created.items():
        doc.AddUndo(c4d.UNDOTYPE_DELETE, old)
        old.Remove()
    return len(created)


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
    mats_before = list(doc.GetMaterials())  # C4DAtom vergleicht den zugrunde liegenden Zeiger
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
    new_mats = [m for m in doc.GetMaterials() if all(m != b for b in mats_before)]
    search = [folder, os.path.join(folder, "tex"), tempfile.gettempdir(), doc.GetDocumentPath() or ""]
    for g in glbs:
        search.append(os.path.join(folder, os.path.splitext(g)[0]))
        search.append(os.path.join(folder, os.path.splitext(g)[0] + "_tex"))
    relinked = relink_textures(doc, new_mats, folder, [d for d in search if d])
    print(f"[gisloader] {relinked} Textur(en) verknüpft unter {os.path.join(folder, 'tex')}")
    if p.get("corona") and corona_available():
        try:
            n_corona = convert_to_corona(doc, root, [os.path.join(folder, g) for g in glbs], new_mats, os.path.join(folder, "tex"))
            print(f"[gisloader] {n_corona} Material(ien) durch Corona-Materialien ersetzt")
        except Exception as e:
            import traceback

            print("[gisloader] Corona-Umwandlung fehlgeschlagen:", repr(e))
            traceback.print_exc()
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
