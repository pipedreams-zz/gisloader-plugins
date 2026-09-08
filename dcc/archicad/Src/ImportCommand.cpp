#include "ImportCommand.hpp"

#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

#include "ObjectState.hpp"

#include "Importer.hpp"

GS::String ImportFileCommand::GetName () const { return "ImportFile"; }
GS::String ImportFileCommand::GetNamespace () const { return "gisloader"; }
GS::Optional<GS::UniString> ImportFileCommand::GetSchemaDefinitions () const { return GS::NoValue; }

GS::Optional<GS::UniString> ImportFileCommand::GetInputParametersSchema () const
{
	return R"json(
		{
			"type": "object",
			"properties": {
				"path": { "type": "string", "description": "Pfad einer GLB-Datei (oder mehrere, mit ; getrennt)" },
				"name": { "type": "string" },
				"georef": { "type": "string", "description": "epsg;ox;oy;oz;lon;lat" }
			},
			"additionalProperties": false,
			"required": ["path"]
		}
	)json";
}

GS::Optional<GS::UniString> ImportFileCommand::GetResponseSchema () const
{
	return R"json(
		{
			"type": "object",
			"properties": {
				"ok": { "type": "boolean" },
				"message": { "type": "string" }
			},
			"additionalProperties": false,
			"required": ["ok", "message"]
		}
	)json";
}

static std::vector<uint8_t> ReadFile (const std::string& path)
{
	std::ifstream in (path, std::ios::binary);
	if (!in) throw std::runtime_error ("Datei nicht lesbar: " + path);
	return std::vector<uint8_t> ((std::istreambuf_iterator<char> (in)), std::istreambuf_iterator<char> ());
}

static gisloader::Georef ParseGeorefCsv (const std::string& csv)
{
	gisloader::Georef g;
	double v[6] = {0, 0, 0, 0, 0, 0};
	size_t pos = 0;
	int n = 0;
	for (; n < 6; ++n) {
		size_t next = csv.find (';', pos);
		v[n] = std::strtod (csv.substr (pos, next == std::string::npos ? std::string::npos : next - pos).c_str (), nullptr);
		if (next == std::string::npos) { ++n; break; }
		pos = next + 1;
	}
	if (n < 6) return g;
	g.epsg = static_cast<int> (v[0]);
	g.originX = v[1]; g.originY = v[2]; g.originZ = v[3];
	g.lon = v[4]; g.lat = v[5];
	g.valid = g.epsg > 0;
	return g;
}

GS::ObjectState ImportFileCommand::Execute (const GS::ObjectState& parameters, GS::ProcessControl&) const
{
	GS::UniString path, name, georef;
	parameters.Get ("path", path);
	parameters.Get ("name", name);
	parameters.Get ("georef", georef);
	GS::ObjectState response;
	try {
		gisloader::ImportSession session;
		const std::string nameUtf8 (name.ToCStr (0, MaxUSize, CC_UTF8).Get ());
		session.Begin (nameUtf8.empty () ? "Import" : nameUtf8);
		session.SetGeoref (ParseGeorefCsv (std::string (georef.ToCStr (0, MaxUSize, CC_UTF8).Get ())));
		const std::string paths (path.ToCStr (0, MaxUSize, CC_UTF8).Get ());
		size_t pos = 0;
		while (pos <= paths.size ()) {
			size_t next = paths.find (';', pos);
			std::string one = paths.substr (pos, next == std::string::npos ? std::string::npos : next - pos);
			if (!one.empty ()) session.AddGlb (ReadFile (one));
			if (next == std::string::npos) break;
			pos = next + 1;
		}
		response.Add ("ok", true);
		response.Add ("message", GS::UniString (session.Finish ().c_str (), CC_UTF8));
	} catch (const std::exception& e) {
		response.Add ("ok", false);
		response.Add ("message", GS::UniString (e.what (), CC_UTF8));
	}
	return response;
}

void ImportFileCommand::OnResponseValidationFailed (const GS::ObjectState&) const {}
