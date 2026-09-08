// Andockbare Palette mit eingebetteter gisloader-Web-App. Die Web-App erkennt
// den Host (window.gisloaderHost) und übergibt fertige Exporte über die
// JavaScript-Brücke; der Import läuft in C++ (Morph-Elemente).
#pragma once

#include "APIEnvir.h"
#include "ACAPinc.h"
#include "DGModule.hpp"
#include "DGBrowser.hpp"

#include "Importer.hpp"

#define GisloaderPaletteResId 32500
#define GisloaderMenuResId 32500
#define GisloaderMenuItemPalette 1
#define GisloaderMenuItemBrowser 2

class GisloaderPalette final : public DG::Palette, public DG::PanelObserver {
public:
	static bool HasInstance ();
	static void CreateInstance ();
	static GisloaderPalette& GetInstance ();
	static void DestroyInstance ();
	static GSErrCode RegisterPaletteControlCallBack ();

	void Show ();
	void Hide ();
	void ReloadWebApp ();
	/** Palette anlegen (falls nötig) und zeigen. */
	static void EnsureShown ();
	/** JavaScript im eingebetteten Browser ausführen (Testbuild). */
	bool ExecuteJs (const GS::UniString& code);

	virtual ~GisloaderPalette ();

protected:
	enum { BrowserId = 1 };

	DG::Browser browser;
	gisloader::ImportSession session;

	GisloaderPalette ();
	void RegisterHostObject ();
	void SetMenuItemCheckedState (bool);

	virtual void PanelResized (const DG::PanelResizeEvent& ev) override;
	virtual void PanelCloseRequested (const DG::PanelCloseRequestEvent& ev, bool* accepted) override;

	static GSErrCode PaletteControlCallBack (Int32 paletteId, API_PaletteMessageID messageID, GS::IntPtr param);
	static GS::Ref<GisloaderPalette> instance;
};

/** Serveradresse der Web-App (später aus den Einstellungen). */
GS::UniString GisloaderServerUrl ();
