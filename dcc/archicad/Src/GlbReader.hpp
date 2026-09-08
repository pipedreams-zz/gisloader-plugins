// GLB (glTF 2.0, binär) lesen: Knoten mit Transformation, Dreiecksnetze mit
// Materialname. Reicht für die Exporte von gisloader (Positionen, Indizes,
// eingebettete Puffer); Texturen und Normalen werden übersprungen.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace gisloader {

struct GlbMesh {
	std::string nodeName;
	std::string meshName;
	std::string materialName;
	std::vector<double> positions;   // x,y,z je Vertex, glTF-Achsen (Y-up), Meter, Weltkoordinaten
	std::vector<uint32_t> indices;   // 3 je Dreieck
};

struct GlbModel {
	std::vector<GlbMesh> meshes;
	std::string attribution;
};

/** Wirft std::runtime_error mit deutscher Meldung, wenn die Datei nicht lesbar ist. */
GlbModel ReadGlb (const std::vector<uint8_t>& bytes);

} // namespace gisloader
