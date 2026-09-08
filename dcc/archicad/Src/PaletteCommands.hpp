// JSON-Befehle rund um die Palette: gisloader.ShowPalette (show|hide|reload) und,
// nur im Testbuild (GISLOADER_DEBUG), gisloader.DebugExecuteJS für automatische Tests.
#pragma once

#include "APIEnvir.h"
#include "ACAPinc.h"

class ShowPaletteCommand : public API_AddOnCommand {
public:
	virtual GS::String GetName () const override { return "ShowPalette"; }
	virtual GS::String GetNamespace () const override { return "gisloader"; }
	virtual GS::Optional<GS::UniString> GetSchemaDefinitions () const override { return GS::NoValue; }
	virtual GS::Optional<GS::UniString> GetInputParametersSchema () const override;
	virtual GS::Optional<GS::UniString> GetResponseSchema () const override;
	virtual API_AddOnCommandExecutionPolicy GetExecutionPolicy () const override
	{
		return API_AddOnCommandExecutionPolicy::ScheduleForExecutionOnMainThread;
	}
	virtual bool IsProcessWindowVisible () const override { return false; }
	virtual GS::ObjectState Execute (const GS::ObjectState& parameters, GS::ProcessControl& processControl) const override;
	virtual void OnResponseValidationFailed (const GS::ObjectState&) const override {}
};

class SetServerCommand : public API_AddOnCommand {
public:
	virtual GS::String GetName () const override { return "SetServer"; }
	virtual GS::String GetNamespace () const override { return "gisloader"; }
	virtual GS::Optional<GS::UniString> GetSchemaDefinitions () const override { return GS::NoValue; }
	virtual GS::Optional<GS::UniString> GetInputParametersSchema () const override;
	virtual GS::Optional<GS::UniString> GetResponseSchema () const override;
	virtual API_AddOnCommandExecutionPolicy GetExecutionPolicy () const override
	{
		return API_AddOnCommandExecutionPolicy::ScheduleForExecutionOnMainThread;
	}
	virtual bool IsProcessWindowVisible () const override { return false; }
	virtual GS::ObjectState Execute (const GS::ObjectState& parameters, GS::ProcessControl& processControl) const override;
	virtual void OnResponseValidationFailed (const GS::ObjectState&) const override {}
};

#if defined (GISLOADER_DEBUG)
class DebugExecuteJsCommand : public API_AddOnCommand {
public:
	virtual GS::String GetName () const override { return "DebugExecuteJS"; }
	virtual GS::String GetNamespace () const override { return "gisloader"; }
	virtual GS::Optional<GS::UniString> GetSchemaDefinitions () const override { return GS::NoValue; }
	virtual GS::Optional<GS::UniString> GetInputParametersSchema () const override;
	virtual GS::Optional<GS::UniString> GetResponseSchema () const override;
	virtual API_AddOnCommandExecutionPolicy GetExecutionPolicy () const override
	{
		return API_AddOnCommandExecutionPolicy::ScheduleForExecutionOnMainThread;
	}
	virtual bool IsProcessWindowVisible () const override { return false; }
	virtual GS::ObjectState Execute (const GS::ObjectState& parameters, GS::ProcessControl& processControl) const override;
	virtual void OnResponseValidationFailed (const GS::ObjectState&) const override {}
};
#endif
