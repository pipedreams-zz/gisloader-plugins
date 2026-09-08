// Import eines gisloader-Exports in das laufende Archicad-Projekt: je Netz ein
// Morph-Element auf einer Ebene je Ebenenart, Georeferenz als Projektstandort.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "APIEnvir.h"
#include "ACAPinc.h"

namespace gisloader {

struct Georef {
	bool valid = false;
	int epsg = 0;
	double originX = 0, originY = 0, originZ = 0;  // Ursprung im Arbeitssystem (Meter)
	double lon = 0, lat = 0;                       // WGS84 des Ursprungs
};

class ImportSession {
public:
	void Begin (const std::string& name);
	void SetGeoref (const Georef& georef);
	void AddGlb (std::vector<uint8_t>&& bytes);
	/** Führt den Import aus (rückgängig machbar) und liefert eine Zusammenfassung oder wirft. */
	std::string Finish ();
	bool IsActive () const { return active; }

private:
	bool active = false;
	std::string name;
	Georef georef;
	std::vector<std::vector<uint8_t>> glbs;
};

} // namespace gisloader
