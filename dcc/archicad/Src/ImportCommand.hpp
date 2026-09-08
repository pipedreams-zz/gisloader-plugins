// JSON-Befehl „gisloader.ImportFile“ über die Archicad-JSON-Schnittstelle
// (Port 19723): Import einer GLB-Datei vom Dateisystem, mit Name und
// Georeferenz. Dient dem automatisierten Test und später der lokalen Brücke
// („An Archicad senden“ aus dem normalen Browser).
#pragma once

#include "APIEnvir.h"
#include "ACAPinc.h"

class ImportFileCommand : public API_AddOnCommand {
public:
	virtual GS::String GetName () const override;
	virtual GS::String GetNamespace () const override;
	virtual GS::Optional<GS::UniString> GetSchemaDefinitions () const override;
	virtual GS::Optional<GS::UniString> GetInputParametersSchema () const override;
	virtual GS::Optional<GS::UniString> GetResponseSchema () const override;
	virtual API_AddOnCommandExecutionPolicy GetExecutionPolicy () const override
	{
		return API_AddOnCommandExecutionPolicy::ScheduleForExecutionOnMainThread;
	}
	virtual bool IsProcessWindowVisible () const override { return false; }
	virtual GS::ObjectState Execute (const GS::ObjectState& parameters, GS::ProcessControl& processControl) const override;
	virtual void OnResponseValidationFailed (const GS::ObjectState& response) const override;
};
