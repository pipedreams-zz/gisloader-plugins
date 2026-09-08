#include "PaletteCommands.hpp"

#include <string>

#include "ObjectState.hpp"

#include "GisloaderPalette.hpp"

GS::Optional<GS::UniString> ShowPaletteCommand::GetInputParametersSchema () const
{
	return R"json(
		{
			"type": "object",
			"properties": {
				"action": { "type": "string", "enum": ["show", "hide", "reload"] }
			},
			"additionalProperties": false
		}
	)json";
}

GS::Optional<GS::UniString> ShowPaletteCommand::GetResponseSchema () const
{
	return R"json(
		{
			"type": "object",
			"properties": { "visible": { "type": "boolean" } },
			"additionalProperties": false,
			"required": ["visible"]
		}
	)json";
}

GS::ObjectState ShowPaletteCommand::Execute (const GS::ObjectState& parameters, GS::ProcessControl&) const
{
	GS::UniString action = "show";
	parameters.Get ("action", action);
	if (action == "hide") {
		if (GisloaderPalette::HasInstance ()) GisloaderPalette::GetInstance ().Hide ();
	} else {
		GisloaderPalette::EnsureShown ();
		if (action == "reload") GisloaderPalette::GetInstance ().ReloadWebApp ();
	}
	GS::ObjectState response;
	response.Add ("visible", GisloaderPalette::HasInstance () && GisloaderPalette::GetInstance ().IsVisible ());
	return response;
}

GS::Optional<GS::UniString> SetServerCommand::GetInputParametersSchema () const
{
	return R"json(
		{
			"type": "object",
			"properties": { "url": { "type": "string" } },
			"additionalProperties": false,
			"required": ["url"]
		}
	)json";
}

GS::Optional<GS::UniString> SetServerCommand::GetResponseSchema () const
{
	return R"json(
		{
			"type": "object",
			"properties": { "ok": { "type": "boolean" }, "server": { "type": "string" } },
			"additionalProperties": false,
			"required": ["ok", "server"]
		}
	)json";
}

GS::ObjectState SetServerCommand::Execute (const GS::ObjectState& parameters, GS::ProcessControl&) const
{
	GS::UniString url;
	parameters.Get ("url", url);
	const bool ok = GisloaderSetServerUrl (std::string (url.ToCStr (0, MaxUSize, CC_UTF8).Get ()));
	if (ok && GisloaderPalette::HasInstance ()) GisloaderPalette::GetInstance ().ReloadWebApp ();
	GS::ObjectState response;
	response.Add ("ok", ok);
	response.Add ("server", GisloaderServerUrl ());
	return response;
}

#if defined (GISLOADER_DEBUG)
GS::Optional<GS::UniString> DebugExecuteJsCommand::GetInputParametersSchema () const
{
	return R"json(
		{
			"type": "object",
			"properties": { "script": { "type": "string" } },
			"additionalProperties": false,
			"required": ["script"]
		}
	)json";
}

GS::Optional<GS::UniString> DebugExecuteJsCommand::GetResponseSchema () const
{
	return R"json(
		{
			"type": "object",
			"properties": { "ok": { "type": "boolean" } },
			"additionalProperties": false,
			"required": ["ok"]
		}
	)json";
}

GS::ObjectState DebugExecuteJsCommand::Execute (const GS::ObjectState& parameters, GS::ProcessControl&) const
{
	GS::UniString script;
	parameters.Get ("script", script);
	GisloaderPalette::EnsureShown ();
	GS::ObjectState response;
	response.Add ("ok", GisloaderPalette::GetInstance ().ExecuteJs (script));
	return response;
}
#endif
