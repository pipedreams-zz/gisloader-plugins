// gisloader für Archicad 28: Menü „gisloader“ mit Palette (eingebettete Web-App)
// und Sprung in den Browser. Aufbau nach dem DevKit-Beispiel Browser_Control.

#include "APIEnvir.h"
#include "ACAPinc.h"

#include <cstdlib>
#include <string>
#if defined (GS_WIN)
#include <windows.h>
#include <shellapi.h>
#endif

#include "GisloaderPalette.hpp"
#include "ImportCommand.hpp"
#include "Log.hpp"
#include "PaletteCommands.hpp"
#include "Version.hpp"

static void ShowOrHidePalette ()
{
	if (GisloaderPalette::HasInstance () && GisloaderPalette::GetInstance ().IsVisible ()) {
		GisloaderPalette::GetInstance ().Hide ();
	} else {
		GisloaderPalette::EnsureShown ();
	}
}

static void OpenInBrowser ()
{
	// Kein API-Aufruf dafür im DevKit: Standardbrowser des Systems verwenden.
	const std::string url = std::string (GisloaderServerUrl ().ToCStr (0, MaxUSize, CC_UTF8).Get ()) + "/";
#if defined (macintosh)
	std::system (("open '" + url + "'").c_str ());
#else
	ShellExecuteA (nullptr, "open", url.c_str (), nullptr, nullptr, SW_SHOWNORMAL);
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
	GisloaderLog ("CheckEnvironment: Name=" + std::string (envir->addOnInfo.name.ToCStr (0, MaxUSize, CC_UTF8).Get ()));
	return APIAddon_Preload;
}

GSErrCode RegisterInterface (void)
{
	GSErrCode err = ACAPI_MenuItem_RegisterMenu (GisloaderMenuResId, 0, MenuCode_UserDef, MenuFlag_Default);
	GisloaderLog ("RegisterInterface: Menü " + std::to_string (err));
	return err;
}

GSErrCode Initialize (void)
{
	GSErrCode err = ACAPI_MenuItem_InstallMenuHandler (GisloaderMenuResId, MenuCommandHandler);
	GisloaderLog ("Initialize: Menühandler " + std::to_string (err));
	if (err != NoError) return err;
	// JSON-Befehl gisloader.ImportFile (Archicad-JSON-Schnittstelle, ExecuteAddOnCommand).
	err = ACAPI_AddOnAddOnCommunication_InstallAddOnCommandHandler (GS::NewOwned<ImportFileCommand> ());
	GisloaderLog ("Initialize: ImportFile-Befehl " + std::to_string (err));
	if (err != NoError) return err;
	err = ACAPI_AddOnAddOnCommunication_InstallAddOnCommandHandler (GS::NewOwned<ShowPaletteCommand> ());
	GisloaderLog ("Initialize: ShowPalette-Befehl " + std::to_string (err));
	if (err != NoError) return err;
	err = ACAPI_AddOnAddOnCommunication_InstallAddOnCommandHandler (GS::NewOwned<SetServerCommand> ());
	GisloaderLog ("Initialize: SetServer-Befehl " + std::to_string (err));
	if (err != NoError) return err;
#if defined (GISLOADER_DEBUG)
	err = ACAPI_AddOnAddOnCommunication_InstallAddOnCommandHandler (GS::NewOwned<DebugExecuteJsCommand> ());
	GisloaderLog ("Initialize: DebugExecuteJS-Befehl (Testbuild) " + std::to_string (err));
	if (err != NoError) return err;
#endif
	err = GisloaderPalette::RegisterPaletteControlCallBack ();
	GisloaderLog ("Initialize: Palette " + std::to_string (err));
	return err;
}

GSErrCode FreeData (void)
{
	return NoError;
}
