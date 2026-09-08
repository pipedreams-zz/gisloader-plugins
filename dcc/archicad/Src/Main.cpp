// gisloader für Archicad 28: Menü „gisloader“ mit Palette (eingebettete Web-App)
// und Sprung in den Browser. Aufbau nach dem DevKit-Beispiel Browser_Control.

#include "APIEnvir.h"
#include "ACAPinc.h"

#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <string>

#include "GisloaderPalette.hpp"
#include "ImportCommand.hpp"
#include "Version.hpp"

/** Protokoll für die Fehlersuche: ~/Library/Logs/gisloader-archicad.log (macOS) bzw. %TEMP% (Windows). */
static void LogLine (const std::string& line)
{
	const char* home = std::getenv ("HOME");
#if defined (macintosh)
	const std::string path = std::string (home ? home : "/tmp") + "/Library/Logs/gisloader-archicad.log";
#else
	const char* tmp = std::getenv ("TEMP");
	const std::string path = std::string (tmp ? tmp : ".") + "\\gisloader-archicad.log";
#endif
	if (FILE* f = std::fopen (path.c_str (), "a")) {
		std::time_t now = std::time (nullptr);
		char stamp[32];
		std::strftime (stamp, sizeof stamp, "%Y-%m-%d %H:%M:%S", std::localtime (&now));
		std::fprintf (f, "%s [gisloader %s] %s\n", stamp, GISLOADER_ADDON_VERSION, line.c_str ());
		std::fclose (f);
	}
}

static void ShowOrHidePalette ()
{
	if (GisloaderPalette::HasInstance () && GisloaderPalette::GetInstance ().IsVisible ()) {
		GisloaderPalette::GetInstance ().Hide ();
	} else {
		if (!GisloaderPalette::HasInstance ()) GisloaderPalette::CreateInstance ();
		GisloaderPalette::GetInstance ().Show ();
	}
}

static void OpenInBrowser ()
{
	// Kein API-Aufruf dafür im DevKit: Standardbrowser des Systems verwenden.
	const std::string url = std::string (GisloaderServerUrl ().ToCStr (0, MaxUSize, CC_UTF8).Get ()) + "/";
#if defined (macintosh)
	std::system (("open '" + url + "'").c_str ());
#else
	std::system (("start \"\" \"" + url + "\"").c_str ());
#endif
}

static GSErrCode MenuCommandHandler (const API_MenuParams* menuParams)
{
	if (menuParams->menuItemRef.menuResID != GisloaderMenuResId) return NoError;
	switch (menuParams->menuItemRef.itemIndex) {
		case GisloaderMenuItemPalette: ShowOrHidePalette (); break;
		case GisloaderMenuItemBrowser: OpenInBrowser (); break;
		default: break;
	}
	return NoError;
}

API_AddonType CheckEnvironment (API_EnvirParams* envir)
{
	RSGetIndString (&envir->addOnInfo.name, 32000, 1, ACAPI_GetOwnResModule ());
	RSGetIndString (&envir->addOnInfo.description, 32000, 2, ACAPI_GetOwnResModule ());
	LogLine ("CheckEnvironment: Name=" + std::string (envir->addOnInfo.name.ToCStr (0, MaxUSize, CC_UTF8).Get ()));
	return APIAddon_Preload;
}

GSErrCode RegisterInterface (void)
{
	GSErrCode err = ACAPI_MenuItem_RegisterMenu (GisloaderMenuResId, 0, MenuCode_UserDef, MenuFlag_Default);
	LogLine ("RegisterInterface: Menü " + std::to_string (err));
	return err;
}

GSErrCode Initialize (void)
{
	GSErrCode err = ACAPI_MenuItem_InstallMenuHandler (GisloaderMenuResId, MenuCommandHandler);
	LogLine ("Initialize: Menühandler " + std::to_string (err));
	if (err != NoError) return err;
	// JSON-Befehl gisloader.ImportFile (Archicad-JSON-Schnittstelle, ExecuteAddOnCommand).
	err = ACAPI_AddOnAddOnCommunication_InstallAddOnCommandHandler (GS::NewOwned<ImportFileCommand> ());
	LogLine ("Initialize: ImportFile-Befehl " + std::to_string (err));
	if (err != NoError) return err;
	err = GisloaderPalette::RegisterPaletteControlCallBack ();
	LogLine ("Initialize: Palette " + std::to_string (err));
	return err;
}

GSErrCode FreeData (void)
{
	return NoError;
}
