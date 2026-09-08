#include "GisloaderPalette.hpp"

#include <cstdlib>
#include <string>

#include <cstdio>

#include "Base64.hpp"
#include "Log.hpp"
#include "MiniJson.hpp"
#include "Version.hpp"

static const GS::Guid paletteGuid ("{7C2E4B1A-5D3F-4E86-9A0B-2F6C1D8E4A57}");

GS::Ref<GisloaderPalette> GisloaderPalette::instance;

/** Konfigurationsdatei ~/.gisloader/archicad.json (macOS) bzw. %USERPROFILE%\\.gisloader\\archicad.json. */
static std::string ConfigPath ()
{
#if defined (macintosh)
	const char* home = std::getenv ("HOME");
	return std::string (home ? home : "/tmp") + "/.gisloader/archicad.json";
#else
	const char* home = std::getenv ("USERPROFILE");
	return std::string (home ? home : ".") + "\\.gisloader\\archicad.json";
#endif
}

GS::UniString GisloaderServerUrl ()
{
	std::string url = GISLOADER_DEFAULT_SERVER;
	if (FILE* f = std::fopen (ConfigPath ().c_str (), "rb")) {
		std::string text;
		char buf[4096];
		size_t n;
		while ((n = std::fread (buf, 1, sizeof buf, f)) > 0) text.append (buf, n);
		std::fclose (f);
		try {
			const gisloader::JsonValue cfg = gisloader::JsonParser::Parse (text);
			const std::string s = cfg["server"].StringOr ("");
			if (s.rfind ("http", 0) == 0) url = s;
		} catch (...) {
			GisloaderLog ("Konfiguration unlesbar: " + ConfigPath ());
		}
	}
	while (!url.empty () && url.back () == '/') url.pop_back ();
	return GS::UniString (url.c_str (), CC_UTF8);
}

bool GisloaderSetServerUrl (const std::string& url)
{
	const std::string path = ConfigPath ();
	const std::string dir = path.substr (0, path.find_last_of ("/\\"));
#if defined (macintosh)
	std::system (("mkdir -p '" + dir + "'").c_str ());
#else
	std::system (("mkdir \"" + dir + "\" 2>nul").c_str ());
#endif
	FILE* f = std::fopen (path.c_str (), "wb");
	if (!f) return false;
	std::string esc;
	for (char c : url) { if (c == '"' || c == '\\') esc += '\\'; esc += c; }
	std::fprintf (f, "{\n  \"server\": \"%s\"\n}\n", esc.c_str ());
	std::fclose (f);
	return true;
}

namespace {

std::string Utf8Of (GS::Ref<JS::Base> jsVariable)
{
	GS::Ref<JS::Value> jsValue = GS::DynamicCast<JS::Value> (jsVariable);
	if (jsValue == nullptr || jsValue->GetType () != JS::Value::STRING) return "";
	return std::string (jsValue->GetString ().ToCStr (0, MaxUSize, CC_UTF8).Get ());
}

GS::Ref<JS::Base> JsString (const std::string& utf8)
{
	return new JS::Value (GS::UniString (utf8.c_str (), CC_UTF8));
}

/** "epsg;ox;oy;oz;lon;lat" aus der Web-App. */
gisloader::Georef ParseGeoref (const std::string& csv)
{
	gisloader::Georef g;
	double v[6] = {0, 0, 0, 0, 0, 0};
	size_t pos = 0;
	for (int i = 0; i < 6; ++i) {
		size_t next = csv.find (';', pos);
		std::string part = csv.substr (pos, next == std::string::npos ? std::string::npos : next - pos);
		v[i] = std::strtod (part.c_str (), nullptr);
		if (next == std::string::npos) { if (i < 5) return g; break; }
		pos = next + 1;
	}
	g.epsg = static_cast<int> (v[0]);
	g.originX = v[1]; g.originY = v[2]; g.originZ = v[3];
	g.lon = v[4]; g.lat = v[5];
	g.valid = g.epsg > 0;
	return g;
}

GSErrCode NotificationHandler (API_NotifyEventID notifID, Int32)
{
	if (notifID == APINotify_Quit) GisloaderPalette::DestroyInstance ();
	return NoError;
}

} // namespace

GisloaderPalette::GisloaderPalette () :
	DG::Palette (ACAPI_GetOwnResModule (), GisloaderPaletteResId, ACAPI_GetOwnResModule (), paletteGuid),
	browser (GetReference (), BrowserId)
{
	ACAPI_ProjectOperation_CatchProjectEvent (APINotify_Quit, NotificationHandler);
	Attach (*this);
	BeginEventProcessing ();
	RegisterHostObject ();
	ReloadWebApp ();
}

GisloaderPalette::~GisloaderPalette ()
{
	EndEventProcessing ();
}

bool GisloaderPalette::HasInstance () { return instance != nullptr; }

void GisloaderPalette::CreateInstance ()
{
	instance = new GisloaderPalette ();
	ACAPI_KeepInMemory (true);
}

GisloaderPalette& GisloaderPalette::GetInstance () { return *instance; }

void GisloaderPalette::DestroyInstance () { instance = nullptr; }

void GisloaderPalette::Show ()
{
	DG::Palette::Show ();
	SetMenuItemCheckedState (true);
}

void GisloaderPalette::Hide ()
{
	DG::Palette::Hide ();
	SetMenuItemCheckedState (false);
}

void GisloaderPalette::ReloadWebApp ()
{
	browser.LoadURL (GisloaderServerUrl () + "/?embed=archicad");
}

void GisloaderPalette::EnsureShown ()
{
	if (!HasInstance ()) CreateInstance ();
	GetInstance ().Show ();
}

bool GisloaderPalette::ExecuteJs (const GS::UniString& code)
{
	return browser.ExecuteJS (code);
}

void GisloaderPalette::RegisterHostObject ()
{
	// window.gisloaderHost in der Web-App; jede Funktion nimmt genau einen String.
	JS::Object* host = new JS::Object ("gisloaderHost");

	host->AddItem (new JS::Function ("getInfo", [] (GS::Ref<JS::Base>) {
		API_ServerApplicationInfo info;
		ACAPI_AddOnIdentification_Application (&info);
		return JsString ("archicad;" + std::to_string (info.mainVersion) + "." + std::to_string (info.releaseVersion) + ";" GISLOADER_ADDON_VERSION);
	}));

	host->AddItem (new JS::Function ("log", [] (GS::Ref<JS::Base> param) {
		GisloaderLog ("web: " + Utf8Of (param));
		return JsString ("ok");
	}));

	host->AddItem (new JS::Function ("beginImport", [this] (GS::Ref<JS::Base> param) {
		session.Begin (Utf8Of (param));
		return JsString ("ok");
	}));

	host->AddItem (new JS::Function ("setGeoref", [this] (GS::Ref<JS::Base> param) {
		session.SetGeoref (ParseGeoref (Utf8Of (param)));
		return JsString ("ok");
	}));

	host->AddItem (new JS::Function ("addGlb", [this] (GS::Ref<JS::Base> param) {
		if (!session.IsActive ()) return JsString ("ERROR: kein Import begonnen");
		session.AddGlb (gisloader::DecodeBase64 (Utf8Of (param)));
		return JsString ("ok");
	}));

	host->AddItem (new JS::Function ("finishImport", [this] (GS::Ref<JS::Base>) {
		try {
			return JsString (session.Finish ());
		} catch (const std::exception& e) {
			return JsString (std::string ("ERROR: ") + e.what ());
		}
	}));

	browser.RegisterAsynchJSObject (host);
}

void GisloaderPalette::SetMenuItemCheckedState (bool isChecked)
{
	API_MenuItemRef itemRef = {};
	GSFlags itemFlags = {};
	itemRef.menuResID = GisloaderMenuResId;
	itemRef.itemIndex = GisloaderMenuItemPalette;
	ACAPI_MenuItem_GetMenuItemFlags (&itemRef, &itemFlags);
	if (isChecked) itemFlags |= API_MenuItemChecked; else itemFlags &= ~API_MenuItemChecked;
	ACAPI_MenuItem_SetMenuItemFlags (&itemRef, &itemFlags);
}

void GisloaderPalette::PanelResized (const DG::PanelResizeEvent& ev)
{
	BeginMoveResizeItems ();
	browser.Resize (ev.GetHorizontalChange (), ev.GetVerticalChange ());
	EndMoveResizeItems ();
}

void GisloaderPalette::PanelCloseRequested (const DG::PanelCloseRequestEvent&, bool* accepted)
{
	Hide ();
	*accepted = true;
}

GSErrCode GisloaderPalette::PaletteControlCallBack (Int32, API_PaletteMessageID messageID, GS::IntPtr param)
{
	switch (messageID) {
		case APIPalMsg_OpenPalette:
			if (!HasInstance ()) CreateInstance ();
			GetInstance ().Show ();
			break;
		case APIPalMsg_ClosePalette:
			if (HasInstance ()) GetInstance ().Hide ();
			break;
		case APIPalMsg_HidePalette_Begin:
			if (HasInstance () && GetInstance ().IsVisible ()) GetInstance ().Hide ();
			break;
		case APIPalMsg_HidePalette_End:
			if (HasInstance () && !GetInstance ().IsVisible ()) GetInstance ().Show ();
			break;
		case APIPalMsg_DisableItems_Begin:
			if (HasInstance () && GetInstance ().IsVisible ()) GetInstance ().DisableItems ();
			break;
		case APIPalMsg_DisableItems_End:
			if (HasInstance () && GetInstance ().IsVisible ()) GetInstance ().EnableItems ();
			break;
		case APIPalMsg_IsPaletteVisible:
			*(reinterpret_cast<bool*> (param)) = HasInstance () && GetInstance ().IsVisible ();
			break;
		default:
			break;
	}
	return NoError;
}

GSErrCode GisloaderPalette::RegisterPaletteControlCallBack ()
{
	return ACAPI_RegisterModelessWindow (
		GS::CalculateHashValue (paletteGuid),
		PaletteControlCallBack,
		API_PalEnabled_FloorPlan + API_PalEnabled_Section + API_PalEnabled_Elevation +
		API_PalEnabled_InteriorElevation + API_PalEnabled_3D + API_PalEnabled_Detail +
		API_PalEnabled_Worksheet + API_PalEnabled_Layout + API_PalEnabled_DocumentFrom3D,
		GSGuid2APIGuid (paletteGuid));
}
