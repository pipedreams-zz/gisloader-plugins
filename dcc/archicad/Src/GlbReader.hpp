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
	double color[3] = {0.8, 0.8, 0.8};  // baseColorFactor (linear), 0..1
	bool textured = false;
	std::vector<double> positions;   // x,y,z je Vertex, glTF-Achsen (Y-up), Meter, Weltkoordinaten
	std::vector<uint32_t> indices;   // 3 je Dreieck
};

/** Linienzüge (glTF LINES / LINE_STRIP), z. B. Flurstücksgrenzen und Höhenlinien. */
struct GlbLine {
	std::string nodeName;
	std::string materialName;
	double color[3] = {0.5, 0.5, 0.5};
	std::vector<std::vector<double>> polylines;  // je Linienzug x,y,z,… (glTF-Achsen)
};

struct GlbModel {
	std::vector<GlbMesh> meshes;
	std::vector<GlbLine> lines;
	std::string attribution;
};

/** Wirft std::runtime_error mit deutscher Meldung, wenn die Datei nicht lesbar ist. */
GlbModel ReadGlb (const std::vector<uint8_t>& bytes);

} // namespace gisloader
