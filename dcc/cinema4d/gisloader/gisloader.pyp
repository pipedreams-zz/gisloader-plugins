"""
gisloader für Cinema 4D 2025/2026: Exporte des Kontos abholen und mit
Georeferenz importieren, lokale Brücke für „An Cinema 4D senden“.
Menü: Extensions › gisloader.
"""

import os
import sys

import c4d
from c4d import gui, plugins

sys.path.insert(0, os.path.dirname(__file__))
import gisloader_core as core  # noqa: E402

# Plugin-IDs von plugincafe.maxon.net (registriert 7. September 2026): Dialog und Brücke (MessageData).
PLUGIN_ID = 1070158
BRIDGE_EVENT_ID = 1070160

ID_SERVER = 1001
ID_EMAIL = 1002
ID_PASSWORD = 1003
ID_LOGIN = 1004
ID_LOGOUT = 1005
ID_REFRESH = 1006
ID_LIST = 1007
ID_IMPORT = 1008
ID_STATUS = 1009
ID_WEB = 1010
ID_BRIDGE = 1011
ID_PERIOD = 1012
ID_FOLDER = 1013
ID_FOLDER_PICK = 1014
ID_ASK_FOLDER = 1015
ID_CORONA = 1016
ID_ACCOUNT = 1017
ID_PREFER_OBJ = 1018
ID_LOG = 1019


class GisloaderDialog(gui.GeDialog):
    def __init__(self):
        super().__init__()
        self.p = core.load_prefs()
        self.exports = []
        self.accounts = []  # Konten aus /api/exports/accounts; Combo: 0 = Alle, dann je Konto

    def CreateLayout(self):
        self.SetTitle(f"gisloader {core.VERSION}")
        self.GroupBegin(2000, c4d.BFH_SCALEFIT, cols=2, rows=3)
        self.GroupBorderSpace(8, 8, 8, 4)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Server")
        self.AddEditText(ID_SERVER, c4d.BFH_SCALEFIT, initw=320)
        self.AddStaticText(0, c4d.BFH_LEFT, name="E-Mail")
        self.AddEditText(ID_EMAIL, c4d.BFH_SCALEFIT, initw=320)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Passwort")
        self.AddEditText(ID_PASSWORD, c4d.BFH_SCALEFIT, initw=320, editflags=c4d.EDITTEXT_PASSWORD)
        self.GroupEnd()
        self.GroupBegin(2001, c4d.BFH_SCALEFIT, cols=4)
        self.GroupBorderSpace(8, 0, 8, 4)
        self.AddButton(ID_LOGIN, c4d.BFH_SCALEFIT, name="Anmelden")
        self.AddButton(ID_LOGOUT, c4d.BFH_SCALEFIT, name="Abmelden")
        self.AddButton(ID_REFRESH, c4d.BFH_SCALEFIT, name="Exporte aktualisieren")
        self.AddButton(ID_WEB, c4d.BFH_SCALEFIT, name="gisloader im Browser")
        self.GroupEnd()
        self.GroupBegin(2006, c4d.BFH_SCALEFIT, cols=4)
        self.GroupBorderSpace(8, 0, 8, 4)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Konto")
        self.AddComboBox(ID_ACCOUNT, c4d.BFH_SCALEFIT, initw=200)
        self.AddChild(ID_ACCOUNT, 0, "Alle Konten")
        self.AddStaticText(0, c4d.BFH_LEFT, name="Zeitraum")
        self.AddComboBox(ID_PERIOD, c4d.BFH_LEFT, initw=130)
        for i, (_, label) in enumerate(core.PERIODS):
            self.AddChild(ID_PERIOD, i, label)
        self.GroupEnd()
        self.GroupBegin(2002, c4d.BFH_SCALEFIT, cols=2)
        self.GroupBorderSpace(8, 0, 8, 4)
        self.AddComboBox(ID_LIST, c4d.BFH_SCALEFIT, initw=320)
        self.AddButton(ID_IMPORT, c4d.BFH_RIGHT, name="Importieren")
        self.GroupEnd()
        self.GroupBegin(2004, c4d.BFH_SCALEFIT, cols=4)
        self.GroupBorderSpace(8, 0, 8, 4)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Ordner")
        self.AddEditText(ID_FOLDER, c4d.BFH_SCALEFIT, initw=320)
        self.AddButton(ID_FOLDER_PICK, c4d.BFH_RIGHT, name="…")
        self.AddCheckbox(ID_ASK_FOLDER, c4d.BFH_LEFT, initw=0, inith=0, name="Beim Import fragen")
        self.GroupEnd()
        self.GroupBegin(2005, c4d.BFH_SCALEFIT, cols=1)
        self.GroupBorderSpace(8, 0, 8, 4)
        self.AddCheckbox(ID_PREFER_OBJ, c4d.BFH_LEFT, initw=0, inith=0, name="Über OBJ importieren (Materialien aus MTL, Höhenlinien als Splines; sonst GLB)")
        self.AddCheckbox(ID_CORONA, c4d.BFH_LEFT, initw=0, inith=0, name="Corona-Materialien erzeugen (Corona Renderer installiert)")
        self.GroupEnd()
        self.GroupBegin(2003, c4d.BFH_SCALEFIT, cols=3)
        self.GroupBorderSpace(8, 0, 8, 8)
        self.AddCheckbox(ID_BRIDGE, c4d.BFH_LEFT, initw=0, inith=0, name=self.bridge_label())
        self.AddStaticText(ID_STATUS, c4d.BFH_SCALEFIT, name="")
        self.AddButton(ID_LOG, c4d.BFH_RIGHT, name="Protokoll")
        self.GroupEnd()
        return True

    def bridge_label(self):
        port = core.bridge_port() or self.p.get("port", core.BRIDGE_PORT)
        return f"Brücke 127.0.0.1:{port} für „An Cinema 4D senden“"

    def period(self):
        idx = self.GetInt32(ID_PERIOD)
        return core.PERIODS[idx][0] if 0 <= idx < len(core.PERIODS) else "all"

    def account(self):
        """Gewähltes Konto: "all" oder die Konto-ID."""
        idx = self.GetInt32(ID_ACCOUNT)
        return self.accounts[idx - 1]["id"] if 1 <= idx <= len(self.accounts) else "all"

    def fill_accounts(self):
        """Kontoauswahl vom Server füllen und die gespeicherte Wahl wiederherstellen."""
        try:
            self.accounts = core.list_accounts(self.p)
        except Exception as e:
            self.accounts = []
            self.status("Konten: " + core.describe_error(e))
        self.FreeChildren(ID_ACCOUNT)
        self.AddChild(ID_ACCOUNT, 0, "Alle Konten")
        for i, a in enumerate(self.accounts):
            label = a["name"] if a.get("kind") == "user" else f"Team {a['name']}"
            self.AddChild(ID_ACCOUNT, i + 1, label + (" (aktiv in der Web-App)" if a.get("active") else ""))
        wanted = self.p.get("account", "all")
        idx = next((i + 1 for i, a in enumerate(self.accounts) if a["id"] == wanted), 0)
        self.SetInt32(ID_ACCOUNT, idx)
        self.LayoutChanged(ID_ACCOUNT)

    def InitValues(self):
        self.SetString(ID_SERVER, self.p["server"])
        self.SetString(ID_EMAIL, self.p["email"])
        self.SetBool(ID_BRIDGE, bool(self.p.get("bridge", True)))
        self.SetString(ID_FOLDER, self.p.get("folder") or core.DEFAULT_FOLDER)
        self.SetBool(ID_ASK_FOLDER, bool(self.p.get("ask_folder", True)))
        has_corona = core.corona_available()
        self.SetBool(ID_CORONA, has_corona and bool(self.p.get("corona", False)))
        self.Enable(ID_CORONA, has_corona)
        self.SetBool(ID_PREFER_OBJ, bool(self.p.get("prefer_obj", True)))
        ids = [k for k, _ in core.PERIODS]
        self.SetInt32(ID_PERIOD, ids.index(self.p.get("period", "month")) if self.p.get("period") in ids else 1)
        self.status("Angemeldet" if self.p.get("token") else "Nicht angemeldet")
        if self.p.get("token"):
            self.check_session_and_refresh()
        return True

    def check_session_and_refresh(self):
        """Beim Öffnen: Sitzung prüfen (abgelaufene Sitzungen liefern sonst stumm eine leere Liste), dann Liste laden."""
        try:
            ok = core.session_ok(self.p)
        except Exception as e:
            self.status("Server nicht erreichbar: " + core.describe_error(e))
            return
        if not ok:
            self.p["token"] = ""
            core.save_prefs(self.p)
            self.status("Sitzung abgelaufen, bitte neu anmelden")
            return
        self.fill_accounts()
        self.refresh()

    def status(self, text):
        self.SetString(ID_STATUS, text)

    def sync_prefs(self):
        self.p["server"] = self.GetString(ID_SERVER).strip() or core.DEFAULT_SERVER
        self.p["email"] = self.GetString(ID_EMAIL).strip()
        self.p["bridge"] = self.GetBool(ID_BRIDGE)
        self.p["period"] = self.period()
        self.p["folder"] = self.GetString(ID_FOLDER).strip() or core.DEFAULT_FOLDER
        self.p["ask_folder"] = self.GetBool(ID_ASK_FOLDER)
        self.p["corona"] = self.GetBool(ID_CORONA)
        self.p["prefer_obj"] = self.GetBool(ID_PREFER_OBJ)
        self.p["account"] = self.account()
        core.save_prefs(self.p)

    def refresh(self):
        if not self.p.get("token"):
            self.status("Nicht angemeldet")
            return
        try:
            self.exports = core.list_exports(self.p, self.period(), self.account())
        except Exception as e:
            self.status("Liste: " + core.describe_error(e))
            return
        self.FreeChildren(ID_LIST)
        for i, ex in enumerate(self.exports):
            self.AddChild(ID_LIST, i, core.export_label(ex, show_account=self.account() == "all"))
        if self.exports:
            self.SetInt32(ID_LIST, 0)
        self.LayoutChanged(ID_LIST)
        where = "in allen Konten" if self.account() == "all" else "im Konto"
        self.status(f"{len(self.exports)} Exporte {where} im Zeitraum" + ("" if self.exports else " – Zeitraum oder Konto wechseln"))

    def Command(self, id, msg):
        if id == ID_LOGIN:
            self.sync_prefs()
            try:
                who = core.login(self.p, self.GetString(ID_PASSWORD))
                self.SetString(ID_PASSWORD, "")
                self.status("Angemeldet als " + who)
                self.fill_accounts()
                self.refresh()
            except Exception as e:
                self.status("Anmeldung: " + core.describe_error(e))
        elif id == ID_LOGOUT:
            self.p["token"] = ""
            core.save_prefs(self.p)
            self.FreeChildren(ID_LIST)
            self.status("Abgemeldet")
        elif id == ID_REFRESH:
            self.sync_prefs()
            if self.p.get("token") and not self.accounts:
                self.check_session_and_refresh()
            else:
                self.refresh()
        elif id in (ID_PERIOD, ID_ACCOUNT):
            self.sync_prefs()
            self.refresh()
        elif id == ID_LOG:
            path = os.path.join(c4d.storage.GeGetC4DPath(c4d.C4D_PATH_PREFS), "gisloader.log")
            if os.path.exists(path):
                c4d.storage.ShowInFinder(path, True)
            else:
                self.status("Noch kein Protokoll: " + path)
        elif id == ID_WEB:
            self.sync_prefs()
            core.open_web(self.p)
        elif id == ID_FOLDER_PICK:
            chosen = c4d.storage.LoadDialog(
                title="Speicherordner für gisloader-Exporte",
                flags=c4d.FILESELECT_DIRECTORY,
                def_path=self.GetString(ID_FOLDER).strip() or core.DEFAULT_FOLDER,
            )
            if chosen:
                self.SetString(ID_FOLDER, chosen)
                self.sync_prefs()
        elif id in (ID_ASK_FOLDER, ID_CORONA, ID_PREFER_OBJ):
            self.sync_prefs()
        elif id == ID_IMPORT:
            idx = self.GetInt32(ID_LIST)
            if idx < 0 or idx >= len(self.exports):
                self.status("Kein Export ausgewählt")
                return True
            self.sync_prefs()
            folder = choose_folder(self.p)
            if folder is None:
                self.status("Import abgebrochen")
                return True
            try:
                doc = c4d.documents.GetActiveDocument()
                self.status("Import läuft …")
                root, n = core.import_export(doc, self.p, self.exports[idx]["id"], folder)
                self.status(f"{n} Objekte unter „{root.GetName()}“ · Dateien unter {core.resolve_folder(self.p, folder)}")
            except Exception as e:
                core.log("Import fehlgeschlagen: " + core.describe_error(e))
                self.status("Import: " + core.describe_error(e))
        elif id == ID_BRIDGE:
            self.sync_prefs()
            apply_bridge(self.p)
            self.SetString(ID_BRIDGE, self.bridge_label())
            self.status(f"Brücke läuft auf Port {core.bridge_port()}" if core.bridge_running() else "Brücke aus")
        return True


def choose_folder(p):
    """Speicherordner für einen Import: Dialog (vorbelegt), wenn eingestellt; None = Abbruch."""
    if not p.get("ask_folder", True):
        return core.resolve_folder(p)
    chosen = c4d.storage.LoadDialog(
        title="Speicherordner für diesen Export",
        flags=c4d.FILESELECT_DIRECTORY,
        def_path=core.resolve_folder(p),
    )
    return chosen or None


def apply_bridge(p):
    try:
        core.stop_bridge()
        if p.get("bridge", True):
            core.start_bridge(int(p.get("port", core.BRIDGE_PORT)), lambda: c4d.SpecialEventAdd(BRIDGE_EVENT_ID))
    except OSError as e:
        print("[gisloader] Brücke konnte nicht starten:", e)


class GisloaderCommand(plugins.CommandData):
    dialog = None  # klassenweit, damit der Brücken-Listener den Status ins offene Fenster schreiben kann

    def Execute(self, doc):
        if GisloaderCommand.dialog is None:
            GisloaderCommand.dialog = GisloaderDialog()
        return GisloaderCommand.dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID, defaultw=520, defaulth=240)

    def RestoreLayout(self, sec_ref):
        if GisloaderCommand.dialog is None:
            GisloaderCommand.dialog = GisloaderDialog()
        return GisloaderCommand.dialog.Restore(pluginid=PLUGIN_ID, secret=sec_ref)


class GisloaderBridgeListener(plugins.MessageData):
    """Importe aus der Brücke laufen hier im Hauptthread."""

    def CoreMessage(self, id, bc):
        if id == BRIDGE_EVENT_ID:
            dialog = GisloaderCommand.dialog
            try:
                p = core.load_prefs()
                if dialog is not None and dialog.IsOpen():
                    dialog.status("Import über die Brücke läuft …")
                core.drain_queue(c4d.documents.GetActiveDocument(), p, choose_folder)
            except Exception as e:
                core.set_last("", False, describe(e))
            last = core.BRIDGE_STATE.get("last") or {}
            text = last.get("message", "")
            if dialog is not None and dialog.IsOpen():
                dialog.status(("Brücke: " if last.get("ok") else "Brücke, Fehler: ") + text)
            if last and not last.get("ok"):
                gui.MessageDialog("gisloader: Import über die Brücke fehlgeschlagen.\n\n" + text)
        return True


def describe(e):
    return core.describe_error(e)


def load_icon():
    """Logo aus res/icon.png als Menü- und Palettensymbol; None, wenn es fehlt."""
    path = os.path.join(os.path.dirname(__file__), "res", "icon.png")
    bmp = c4d.bitmaps.BaseBitmap()
    if os.path.exists(path) and bmp.InitWith(path)[0] == c4d.IMAGERESULT_OK:
        return bmp
    return None


if __name__ == "__main__":
    plugins.RegisterCommandPlugin(
        id=PLUGIN_ID,
        str="gisloader",
        info=0,
        icon=load_icon(),
        help="Exporte von gisloader abholen und mit Georeferenz importieren",
        dat=GisloaderCommand(),
    )
    plugins.RegisterMessagePlugin(id=BRIDGE_EVENT_ID, str="gisloader Brücke", info=0, dat=GisloaderBridgeListener())
    apply_bridge(core.load_prefs())
