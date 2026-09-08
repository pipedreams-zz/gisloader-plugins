// gisloader für Archicad 28: Menü „gisloader“ mit Palette (eingebettete Web-App)
// und Sprung in den Browser. Aufbau nach dem DevKit-Beispiel Browser_Control.

#include "APIEnvir.h"
#include "ACAPinc.h"

#include <cstdlib>
#include <string>

#include "GisloaderPalette.hpp"

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
	return APIAddon_Preload;
}

GSErrCode RegisterInterface (void)
{
	return ACAPI_MenuItem_RegisterMenu (GisloaderMenuResId, 0, MenuCode_UserDef, MenuFlag_Default);
}

GSErrCode Initialize (void)
{
	GSErrCode err = ACAPI_MenuItem_InstallMenuHandler (GisloaderMenuResId, MenuCommandHandler);
	if (err != NoError) return err;
	return GisloaderPalette::RegisterPaletteControlCallBack ();
}

GSErrCode FreeData (void)
{
	return NoError;
}
