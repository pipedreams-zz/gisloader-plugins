"""
gisloader für Blender: Exporte des Kontos abholen und als Collections mit
Georeferenz importieren. Zusätzlich eine lokale Brücke (HTTP auf 127.0.0.1),
über die der Knopf „An Blender senden“ in der Web-App den Import anstößt.

Georeferenz: Die GLB ist um den Ursprung (Südwest-Ecke, tiefster Punkt)
verschoben; Ursprung und CRS stehen als Custom Properties an der Collection
(`crs`, `origin_x`, `origin_y`, `origin_z`) und, falls noch nicht gesetzt,
an der Szene in der Form von BlenderGIS (`crs`, `crsx`, `crsy`).
"""

bl_info = {
    "name": "gisloader",
    "author": "gisloader",
    "version": (0, 1, 13),
    "blender": (3, 6, 0),
    "location": "3D-Ansicht › Seitenleiste (N) › gisloader",
    "description": "Exporte von gisloader abholen und mit Georeferenz importieren",
    "category": "Import-Export",
}

import datetime
import json
import os
import queue
import re
import ssl
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

ADDON_ID = __package__ or __name__
ADDON_VERSION = "0.1.13"
DEFAULT_SERVER = "https://gisloader.ampsrvr.xyz"
# Blender-Instanzen nehmen den ersten freien Port ab 47800 (bis +9); Cinema 4D ab 47810.
BRIDGE_PORT_SPAN = 10
IMPORT_QUEUE: "queue.Queue[dict]" = queue.Queue()
_bridge: "ThreadingHTTPServer | None" = None
_bridge_thread: "threading.Thread | None" = None
_bridge_port = 0
_jobs: list = []  # zuletzt geladene Exportliste (ungefiltert)
_ssl_ctx = None

DEFAULT_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads", "gisloader")


def resolve_folder(chosen=None):
    """Speicherordner: gewählter, sonst Vorgabe aus den Einstellungen, sonst Downloads, sonst Temp."""
    candidates = [chosen, getattr(prefs(), "folder", ""), DEFAULT_FOLDER, os.path.join(tempfile.gettempdir(), "gisloader")]
    for c in candidates:
        c = (c or "").strip()
        if not c:
            continue
        c = os.path.abspath(bpy.path.abspath(c))
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


PERIODS = [
    ("week", "Diese Woche", "Exporte seit Montag dieser Woche"),
    ("month", "Dieser Monat", "Exporte seit dem 1. dieses Monats"),
    ("year", "Dieses Jahr", "Exporte seit dem 1. Januar"),
    ("all", "Alle", "Alle Exporte des Kontos"),
]


def in_period(created_iso, period):
    """Fällt der Zeitstempel (ISO, UTC) in den gewählten Zeitraum, gerechnet in Ortszeit?"""
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
    """Zertifikatsprüfung: Blender bringt certifi mit; sonst Systembündel (macOS /etc/ssl/cert.pem)."""
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


# ── Server-Zugriff ──────────────────────────────────────────────────────


def prefs(context=None):
    context = context or bpy.context
    return context.preferences.addons[ADDON_ID].preferences


def api(p, path, method="GET", body=None, raw=False, timeout=120):
    """GET/POST gegen die gisloader-API mit Bearer-Token aus den Einstellungen."""
    url = p.server.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "*/*" if raw else "application/json")
    req.add_header("User-Agent", "gisloader-blender/" + ADDON_VERSION)
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("Origin", p.server.rstrip("/"))
    if p.token:
        req.add_header("Authorization", "Bearer " + p.token)
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as r:
        payload = r.read()
        token = r.headers.get("set-auth-token")
        if token:
            p.token = token
        return payload if raw else json.loads(payload.decode("utf-8"))


def describe_error(e):
    if isinstance(e, urllib.error.HTTPError):
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error") or ""
        except Exception:
            msg = ""
        if e.code == 401:
            return "Nicht angemeldet (401)" + (": " + msg if msg else "")
        return f"HTTP {e.code}" + (": " + msg if msg else "")
    return str(e)


# ── Einstellungen ───────────────────────────────────────────────────────


class GisloaderPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    server: StringProperty(name="Server", default=DEFAULT_SERVER)
    email: StringProperty(name="E-Mail")
    token: StringProperty(name="Sitzungstoken", subtype="PASSWORD")
    bridge: BoolProperty(
        name="Lokale Brücke",
        description="HTTP-Listener auf 127.0.0.1, damit die Web-App Importe anstoßen kann",
        default=True,
        update=lambda self, ctx: _apply_bridge(self),
    )
    folder: StringProperty(
        name="Speicherordner",
        description="Hier landen GLB, Texturen und Provenienz je Export (Unterordner je Export)",
        subtype="DIR_PATH",
        default=DEFAULT_FOLDER,
    )
    ask_folder: BoolProperty(
        name="Beim Import nach dem Ordner fragen",
        description="Vor jedem Import (auch über die Brücke) einen Ordnerdialog zeigen, vorbelegt mit dem Speicherordner",
        default=True,
    )
    port: IntProperty(
        name="Port",
        description="Erster Port der Brücke; belegt ihn eine andere Blender-Instanz, nimmt das Add-on den nächsten freien (bis +9)",
        default=47800,
        min=1024,
        max=65535,
    )

    def draw(self, context):
        col = self.layout.column()
        col.label(text=f"gisloader-Add-on {ADDON_VERSION}")
        col.prop(self, "server")
        col.prop(self, "email")
        row = col.row()
        row.operator("gisloader.login", icon="KEYINGSET")
        row.operator("gisloader.logout", icon="X")
        col.label(text="Angemeldet" if self.token else "Nicht angemeldet", icon="CHECKMARK" if self.token else "ERROR")
        col.separator()
        col.prop(self, "folder")
        col.prop(self, "ask_folder")
        col.separator()
        col.prop(self, "bridge")
        col.prop(self, "port")


class GISLOADER_OT_login(bpy.types.Operator):
    bl_idname = "gisloader.login"
    bl_label = "Anmelden"
    bl_description = "Mit E-Mail und Passwort am gisloader-Server anmelden"

    password: StringProperty(name="Passwort", subtype="PASSWORD")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        p = prefs(context)
        try:
            p.token = ""
            r = api(p, "/api/auth/sign-in/email", "POST", {"email": p.email, "password": self.password})
            if not p.token and r.get("token"):
                p.token = r["token"]
            self.password = ""
            self.report({"INFO"}, f"Angemeldet als {r.get('user', {}).get('email', p.email)}")
            bpy.ops.gisloader.refresh()
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, "Anmeldung fehlgeschlagen: " + describe_error(e))
            return {"CANCELLED"}


class GISLOADER_OT_logout(bpy.types.Operator):
    bl_idname = "gisloader.logout"
    bl_label = "Abmelden"

    def execute(self, context):
        prefs(context).token = ""
        context.scene.gisloader_exports.clear()
        return {"FINISHED"}


# ── Exportliste ─────────────────────────────────────────────────────────


class GisloaderExportItem(bpy.types.PropertyGroup):
    export_id: StringProperty()
    name: StringProperty()
    created: StringProperty()
    state: StringProperty()
    area_km2: FloatProperty()


def _fill_items(scene):
    """Exportliste der Szene aus der letzten Serverantwort füllen, gefiltert nach Zeitraum."""
    items = scene.gisloader_exports
    items.clear()
    for j in _jobs:
        if not in_period(j.get("createdAt", ""), scene.gisloader_period):
            continue
        it = items.add()
        it.export_id = j["id"]
        it.name = j.get("request", {}).get("name") or j["id"][:8]
        it.created = j.get("createdAt", "")[:16].replace("T", " ")
        it.state = j.get("state", "")
        b = j.get("request", {}).get("bbox", {})
        it.area_km2 = abs((b.get("maxX", 0) - b.get("minX", 0)) * (b.get("maxY", 0) - b.get("minY", 0))) / 1e6
    if scene.gisloader_export_index >= len(items):
        scene.gisloader_export_index = max(0, len(items) - 1)
    return len(items)


def _period_changed(self, context):
    _fill_items(context.scene)


class GISLOADER_OT_refresh(bpy.types.Operator):
    bl_idname = "gisloader.refresh"
    bl_label = "Exporte aktualisieren"
    bl_description = "Exportliste des Kontos vom Server laden"

    def execute(self, context):
        global _jobs
        p = prefs(context)
        try:
            _jobs = list(api(p, "/api/exports"))
        except Exception as e:
            self.report({"ERROR"}, describe_error(e))
            return {"CANCELLED"}
        n = _fill_items(context.scene)
        self.report({"INFO"}, f"{n} von {len(_jobs)} Exporten im Zeitraum")
        return {"FINISHED"}


class GISLOADER_UL_exports(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        row.label(text=item.name, icon="CHECKMARK" if item.state == "done" else "TIME")
        row.label(text=f"{item.area_km2:.3f} km²")
        row.label(text=item.created)


# ── Import ──────────────────────────────────────────────────────────────


def _download(p, export_id, name, folder):
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(api(p, f"/api/exports/{export_id}/files/{name}", raw=True, timeout=600))
    return path


def _move_to_collection(objs, coll):
    for o in objs:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)


def _relink_textures(images, tex_dir):
    """Eingebettete (gepackte) Bilder als Dateien in tex/ ablegen und absolut verknüpfen."""
    os.makedirs(tex_dir, exist_ok=True)
    n = 0
    for img in images:
        pf = img.packed_file
        if not pf:
            continue
        data = bytes(pf.data)
        ext = ".jpg" if data[:2] == b"\xff\xd8" else ".png" if data[:4] == b"\x89PNG" else ".bin"
        base = re.sub(r"[^\w.-]+", "_", img.name) or "texture"
        path = os.path.join(tex_dir, base + ext)
        with open(path, "wb") as f:
            f.write(data)
        img.filepath_raw = path
        img.filepath = path
        img.unpack(method="REMOVE")
        img.reload()
        n += 1
    return n


def import_export(context, export_id, report, folder=None):
    p = prefs(context)
    job = api(p, f"/api/exports/{export_id}")
    if job.get("state") != "done":
        raise RuntimeError(f"Export ist {job.get('state')}")
    files = job.get("files", [])
    name = job.get("request", {}).get("name") or export_id[:8]
    folder = export_folder(resolve_folder(folder), export_id, name)
    prov = None
    # Alles außer dem Zip lokal ablegen: GLB, Texturen (JPEG), OBJ/MTL, Provenienz, README.
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
    coll = bpy.data.collections.new(f"gisloader · {name}")
    context.scene.collection.children.link(coll)
    georef = None
    for f in (prov or {}).get("files", []):
        if f.get("georef"):
            georef = f["georef"]
            break
    images_before = set(bpy.data.images.keys())
    for g in glbs:
        path = os.path.join(folder, g)
        before = set(bpy.data.objects.keys())
        bpy.ops.import_scene.gltf(filepath=path)
        new = [o for o in bpy.data.objects if o.name not in before]
        _move_to_collection(new, coll)
    relinked = _relink_textures(
        [i for i in bpy.data.images if i.name not in images_before], os.path.join(folder, "tex")
    )
    coll["gisloader_export_id"] = export_id
    coll["gisloader_server"] = p.server
    coll["gisloader_folder"] = folder
    if prov:
        coll["attribution"] = prov.get("attribution", "")
        region = prov.get("region") or {}
        if region.get("name"):
            coll["region"] = region["name"]
    if georef:
        crs = f"EPSG:{georef.get('epsg')}"
        origin = georef.get("origin") or {}
        coll["crs"] = crs
        coll["crs_name"] = georef.get("crsName", "")
        coll["origin_x"] = float(origin.get("x", 0))
        coll["origin_y"] = float(origin.get("y", 0))
        coll["origin_z"] = float(origin.get("z", 0))
        coll["up_axis"] = "Z (Blender); Quelle glTF Y-up, vom Importer gedreht"
        coll["axis_note"] = "X = Ost, Y = Nord, Z = Höhe; Ursprung ist die Südwest-Ecke des Ausschnitts"
        scn = context.scene
        if "crs" not in scn:
            # Form von BlenderGIS: Szenenursprung in Weltkoordinaten
            scn["crs"] = crs
            scn["crsx"] = float(origin.get("x", 0))
            scn["crsy"] = float(origin.get("y", 0))
    report({"INFO"}, f"{len(glbs)} Datei(en) importiert in „{coll.name}“, {relinked} Textur(en) unter {folder}")
    return coll


class GISLOADER_OT_import(bpy.types.Operator):
    bl_idname = "gisloader.import_export"
    bl_label = "Importieren"
    bl_description = "Ausgewählten Export als Collection mit Georeferenz importieren; Dateien landen im Speicherordner"
    bl_options = {"REGISTER", "UNDO"}

    export_id: StringProperty(name="Export-ID", default="")
    directory: StringProperty(name="Speicherordner", subtype="DIR_PATH", default="")
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})

    def _resolve_id(self, context):
        if self.export_id:
            return self.export_id
        items = context.scene.gisloader_exports
        idx = context.scene.gisloader_export_index
        if idx < 0 or idx >= len(items):
            return None
        return items[idx].export_id

    def invoke(self, context, event):
        if not self._resolve_id(context):
            self.report({"ERROR"}, "Kein Export ausgewählt")
            return {"CANCELLED"}
        p = prefs(context)
        if not p.ask_folder:
            return self.execute(context)
        self.directory = resolve_folder() + os.sep
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        export_id = self._resolve_id(context)
        if not export_id:
            self.report({"ERROR"}, "Kein Export ausgewählt")
            return {"CANCELLED"}
        try:
            import_export(context, export_id, self.report, self.directory or None)
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, "Import fehlgeschlagen: " + describe_error(e))
            return {"CANCELLED"}


# ── Lokale Brücke ───────────────────────────────────────────────────────


class BridgeHandler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        # Chrome: Zugriff von https auf das lokale Netz braucht diese Antwort im Preflight.
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
            self._json(200, {"app": "blender", "version": bpy.app.version_string, "addon": ADDON_VERSION, "port": _bridge_port})
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
        self._json(202, {"queued": True})

    def log_message(self, *args):
        pass


def _import_from_bridge(export_id):
    """Import aus der Brücke: mit Ordnerdialog (braucht ein Fenster), sonst direkt in den Speicherordner."""
    wm = bpy.context.window_manager
    if prefs().ask_folder and wm.windows:
        win = wm.windows[0]
        try:
            with bpy.context.temp_override(window=win, screen=win.screen):
                bpy.ops.gisloader.import_export("INVOKE_DEFAULT", export_id=export_id)
            return
        except Exception as e:
            print("[gisloader] Ordnerdialog nicht möglich, Speicherordner wird genutzt:", e)
    bpy.ops.gisloader.import_export("EXEC_DEFAULT", export_id=export_id)


def _poll_queue():
    try:
        while True:
            data = IMPORT_QUEUE.get_nowait()
            server = data.get("server")
            p = prefs()
            if server and server.rstrip("/") != p.server.rstrip("/"):
                print(f"[gisloader] Import abgelehnt: Server {server} ≠ {p.server}")
                continue
            _import_from_bridge(data["exportId"])
    except queue.Empty:
        pass
    except Exception as e:
        print("[gisloader] Import über Brücke fehlgeschlagen:", e)
    return 1.0


def _start_bridge(port):
    """Ersten freien Port ab `port` binden, damit mehrere Blender-Instanzen nebeneinander laufen."""
    global _bridge, _bridge_thread, _bridge_port
    if _bridge:
        return
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
    if not bpy.app.timers.is_registered(_poll_queue):
        bpy.app.timers.register(_poll_queue, persistent=True)


def _stop_bridge():
    global _bridge, _bridge_thread, _bridge_port
    if _bridge:
        _bridge.shutdown()
        _bridge.server_close()
        _bridge = None
        _bridge_thread = None
        _bridge_port = 0


def _start_bridge_later():
    try:
        _apply_bridge(prefs())
    except Exception as e:
        print("[gisloader] Brücke nicht gestartet:", e)
    return None


def _apply_bridge(p):
    try:
        if p.bridge:
            _stop_bridge()
            _start_bridge(p.port)
        else:
            _stop_bridge()
    except OSError as e:
        print("[gisloader] Brücke konnte nicht starten:", e)


class GISLOADER_OT_web(bpy.types.Operator):
    bl_idname = "gisloader.open_web"
    bl_label = "gisloader im Browser"
    bl_description = "Die Web-App mit dem eingestellten Server öffnen"

    def execute(self, context):
        bpy.ops.wm.url_open(url=prefs(context).server.rstrip("/") + "/")
        return {"FINISHED"}


class GISLOADER_OT_bridge(bpy.types.Operator):
    bl_idname = "gisloader.bridge"
    bl_label = "Brücke neu starten"

    def execute(self, context):
        _apply_bridge(prefs(context))
        self.report({"INFO"}, "Brücke läuft" if _bridge else "Brücke aus")
        return {"FINISHED"}


# ── Panel ───────────────────────────────────────────────────────────────


class GISLOADER_PT_panel(bpy.types.Panel):
    bl_label = "gisloader"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "gisloader"

    def draw_header(self, context):
        self.layout.label(text=f"v{ADDON_VERSION}")

    def draw(self, context):
        p = prefs(context)
        lay = self.layout
        col = lay.column(align=True)
        col.label(text=p.server.replace("https://", ""), icon="URL")
        if p.token:
            col.label(text=p.email or "angemeldet", icon="USER")
            row = col.row(align=True)
            row.operator("gisloader.refresh", icon="FILE_REFRESH")
            row.operator("gisloader.logout", text="", icon="X")
        else:
            col.operator("gisloader.login", icon="KEYINGSET")
        lay.prop(context.scene, "gisloader_period", text="")
        lay.template_list("GISLOADER_UL_exports", "", context.scene, "gisloader_exports", context.scene, "gisloader_export_index", rows=6)
        lay.operator("gisloader.import_export", icon="IMPORT").export_id = ""
        lay.label(text=(p.folder or DEFAULT_FOLDER).replace(os.path.expanduser("~"), "~"), icon="FILE_FOLDER")
        lay.operator("gisloader.open_web", icon="URL")
        box = lay.box()
        row = box.row()
        row.label(text=f"Brücke 127.0.0.1:{_bridge_port or p.port}", icon="LINKED" if _bridge else "UNLINKED")
        row.operator("gisloader.bridge", text="", icon="FILE_REFRESH")
        box.label(text="„An Blender senden“ in der Web-App nutzt sie.")


CLASSES = (
    GisloaderPreferences,
    GisloaderExportItem,
    GISLOADER_OT_login,
    GISLOADER_OT_logout,
    GISLOADER_OT_refresh,
    GISLOADER_UL_exports,
    GISLOADER_OT_import,
    GISLOADER_OT_bridge,
    GISLOADER_OT_web,
    GISLOADER_PT_panel,
)


def register():
    for c in CLASSES:
        try:
            bpy.utils.register_class(c)
        except ValueError:
            # Bereits registriert (z. B. nach einem fehlgeschlagenen Ausschalten): erst lösen.
            bpy.utils.unregister_class(getattr(bpy.types, c.__name__, c))
            bpy.utils.register_class(c)
    bpy.types.Scene.gisloader_exports = CollectionProperty(type=GisloaderExportItem)
    bpy.types.Scene.gisloader_export_index = IntProperty(default=0)
    bpy.types.Scene.gisloader_period = EnumProperty(
        name="Zeitraum", items=PERIODS, default="month", update=_period_changed
    )
    # Einstellungen sind erst nach der Registrierung erreichbar: Brücke verzögert starten.
    bpy.app.timers.register(_start_bridge_later, first_interval=0.5)


def unregister():
    _stop_bridge()
    if bpy.app.timers.is_registered(_poll_queue):
        bpy.app.timers.unregister(_poll_queue)
    del bpy.types.Scene.gisloader_exports
    del bpy.types.Scene.gisloader_export_index
    del bpy.types.Scene.gisloader_period
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
