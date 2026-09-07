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

# Plugin-ID von plugincafe.maxon.net (registriert 7. September 2026). Die Brücke braucht eine
# zweite ID für ihr MessageData-Plugin; bis dahin eine aus dem Testbereich 1000001–1000010.
PLUGIN_ID = 1070158
BRIDGE_EVENT_ID = 1000008

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


class GisloaderDialog(gui.GeDialog):
    def __init__(self):
        super().__init__()
        self.p = core.load_prefs()
        self.exports = []

    def CreateLayout(self):
        self.SetTitle("gisloader")
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
        self.GroupBegin(2002, c4d.BFH_SCALEFIT, cols=3)
        self.GroupBorderSpace(8, 0, 8, 4)
        self.AddComboBox(ID_PERIOD, c4d.BFH_LEFT, initw=130)
        for i, (_, label) in enumerate(core.PERIODS):
            self.AddChild(ID_PERIOD, i, label)
        self.AddComboBox(ID_LIST, c4d.BFH_SCALEFIT, initw=320)
        self.AddButton(ID_IMPORT, c4d.BFH_RIGHT, name="Importieren")
        self.GroupEnd()
        self.GroupBegin(2003, c4d.BFH_SCALEFIT, cols=2)
        self.GroupBorderSpace(8, 0, 8, 8)
        self.AddCheckbox(ID_BRIDGE, c4d.BFH_LEFT, initw=0, inith=0, name=self.bridge_label())
        self.AddStaticText(ID_STATUS, c4d.BFH_SCALEFIT, name="")
        self.GroupEnd()
        return True

    def bridge_label(self):
        port = core.bridge_port() or self.p.get("port", core.BRIDGE_PORT)
        return f"Brücke 127.0.0.1:{port} für „An Cinema 4D senden“"

    def period(self):
        idx = self.GetInt32(ID_PERIOD)
        return core.PERIODS[idx][0] if 0 <= idx < len(core.PERIODS) else "all"

    def InitValues(self):
        self.SetString(ID_SERVER, self.p["server"])
        self.SetString(ID_EMAIL, self.p["email"])
        self.SetBool(ID_BRIDGE, bool(self.p.get("bridge", True)))
        ids = [k for k, _ in core.PERIODS]
        self.SetInt32(ID_PERIOD, ids.index(self.p.get("period", "month")) if self.p.get("period") in ids else 1)
        self.status("Angemeldet" if self.p.get("token") else "Nicht angemeldet")
        if self.p.get("token"):
            self.refresh()
        return True

    def status(self, text):
        self.SetString(ID_STATUS, text)

    def sync_prefs(self):
        self.p["server"] = self.GetString(ID_SERVER).strip() or core.DEFAULT_SERVER
        self.p["email"] = self.GetString(ID_EMAIL).strip()
        self.p["bridge"] = self.GetBool(ID_BRIDGE)
        self.p["period"] = self.period()
        core.save_prefs(self.p)

    def refresh(self):
        try:
            self.exports = core.list_exports(self.p, self.period())
        except Exception as e:
            self.status("Liste: " + core.describe_error(e))
            return
        self.FreeChildren(ID_LIST)
        for i, ex in enumerate(self.exports):
            mark = "✓" if ex["state"] == "done" else "…"
            self.AddChild(ID_LIST, i, f"{mark} {ex['name']} · {ex['area_km2']:.3f} km² · {ex['created']}")
        if self.exports:
            self.SetInt32(ID_LIST, 0)
        self.status(f"{len(self.exports)} Exporte im Zeitraum")

    def Command(self, id, msg):
        if id == ID_LOGIN:
            self.sync_prefs()
            try:
                who = core.login(self.p, self.GetString(ID_PASSWORD))
                self.SetString(ID_PASSWORD, "")
                self.status("Angemeldet als " + who)
                self.refresh()
            except Exception as e:
                self.status("Anmeldung: " + core.describe_error(e))
        elif id == ID_LOGOUT:
            self.p["token"] = ""
            core.save_prefs(self.p)
            self.FreeChildren(ID_LIST)
            self.status("Abgemeldet")
        elif id == ID_REFRESH or id == ID_PERIOD:
            self.sync_prefs()
            self.refresh()
        elif id == ID_WEB:
            self.sync_prefs()
            core.open_web(self.p)
        elif id == ID_IMPORT:
            idx = self.GetInt32(ID_LIST)
            if idx < 0 or idx >= len(self.exports):
                self.status("Kein Export ausgewählt")
                return True
            try:
                doc = c4d.documents.GetActiveDocument()
                root, n = core.import_export(doc, self.p, self.exports[idx]["id"])
                self.status(f"{n} Objekte unter „{root.GetName()}“")
            except Exception as e:
                self.status("Import: " + core.describe_error(e))
        elif id == ID_BRIDGE:
            self.sync_prefs()
            apply_bridge(self.p)
            self.SetString(ID_BRIDGE, self.bridge_label())
            self.status(f"Brücke läuft auf Port {core.bridge_port()}" if core.bridge_running() else "Brücke aus")
        return True


def apply_bridge(p):
    try:
        core.stop_bridge()
        if p.get("bridge", True):
            core.start_bridge(int(p.get("port", core.BRIDGE_PORT)), lambda: c4d.SpecialEventAdd(BRIDGE_EVENT_ID))
    except OSError as e:
        print("[gisloader] Brücke konnte nicht starten:", e)


class GisloaderCommand(plugins.CommandData):
    dialog = None

    def Execute(self, doc):
        if self.dialog is None:
            self.dialog = GisloaderDialog()
        return self.dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID, defaultw=460, defaulth=200)

    def RestoreLayout(self, sec_ref):
        if self.dialog is None:
            self.dialog = GisloaderDialog()
        return self.dialog.Restore(pluginid=PLUGIN_ID, secret=sec_ref)


class GisloaderBridgeListener(plugins.MessageData):
    """Importe aus der Brücke laufen hier im Hauptthread."""

    def CoreMessage(self, id, bc):
        if id == BRIDGE_EVENT_ID:
            try:
                p = core.load_prefs()
                for root, n in core.drain_queue(c4d.documents.GetActiveDocument(), p):
                    print(f"[gisloader] {n} Objekte importiert unter „{root.GetName()}“")
            except Exception as e:
                print("[gisloader] Import über Brücke fehlgeschlagen:", e)
        return True


if __name__ == "__main__":
    plugins.RegisterCommandPlugin(
        id=PLUGIN_ID,
        str="gisloader",
        info=0,
        icon=None,
        help="Exporte von gisloader abholen und mit Georeferenz importieren",
        dat=GisloaderCommand(),
    )
    plugins.RegisterMessagePlugin(id=BRIDGE_EVENT_ID, str="gisloader Brücke", info=0, dat=GisloaderBridgeListener())
    apply_bridge(core.load_prefs())
