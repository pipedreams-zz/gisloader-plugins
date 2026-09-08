#include "Importer.hpp"

#include <cmath>
#include <cstring>
#include <map>
#include <stdexcept>
#include <utility>

#include "GlbReader.hpp"

namespace gisloader {

namespace {

/** Anzeigename einer Oberfläche je glTF-Material. */
std::string SurfaceNameFor (const std::string& material)
{
	static const std::map<std::string, std::string> names = {
		{"terrain", "gisloader Gelände"},
		{"roof", "gisloader Dach"},
		{"wall", "gisloader Wand"},
		{"ground", "gisloader Boden"},
		{"footprint", "gisloader Grundriss"},
		{"landuse-siedlung", "gisloader Nutzung Siedlung"},
		{"landuse-verkehr", "gisloader Nutzung Verkehr"},
		{"landuse-gewaesser", "gisloader Nutzung Gewässer"},
		{"landuse-vegetation", "gisloader Nutzung Vegetation"},
		{"parcel-line", "gisloader Flurstück"},
		{"structure", "gisloader Bauwerk"},
		{"tree", "gisloader Baum"},
		{"contour", "gisloader Höhenlinie"},
	};
	auto it = names.find (material);
	return it != names.end () ? it->second : "gisloader " + (material.empty () ? std::string ("Material") : material);
}

double Clamp01 (double v)
{
	return v < 0 ? 0 : v > 1 ? 1 : v;
}

/** Oberfläche (Surface-Attribut) nach Name; legt sie mit der Farbe an, wenn sie fehlt.
 *  Der gisloader-Exporter schreibt Anzeigefarben in den glTF-Farbfaktor, deshalb keine Linear-Umrechnung. */
API_AttributeIndex EnsureSurface (const std::string& utf8Name, const double rgb[3], std::map<std::string, API_AttributeIndex>& cache)
{
	auto it = cache.find (utf8Name);
	if (it != cache.end ()) return it->second;
	const GS::UniString wanted (utf8Name.c_str (), CC_UTF8);
	API_AttributeIndex found = APIInvalidAttributeIndex;
	ACAPI_Attribute_EnumerateAttributesByType (API_MaterialID, [&] (API_Attribute& attr) {
		if (found != APIInvalidAttributeIndex) return;
		GS::UniString name = attr.header.uniStringNamePtr != nullptr ? *attr.header.uniStringNamePtr : GS::UniString (attr.header.name, CC_UTF8);
		if (name == wanted) found = attr.header.index;
	});
	if (found == APIInvalidAttributeIndex) {
		API_Attribute attr = {};
		attr.header.typeID = API_MaterialID;
		GS::UniString uniName = wanted;
		attr.header.uniStringNamePtr = &uniName;
		attr.material.mtype = APIMater_GeneralID;
		attr.material.ambientPc = 100;
		attr.material.diffusePc = 100;
		attr.material.specularPc = 5;
		attr.material.transpPc = 0;
		attr.material.shine = 10;
		attr.material.surfaceRGB.f_red = Clamp01 (rgb[0]);
		attr.material.surfaceRGB.f_green = Clamp01 (rgb[1]);
		attr.material.surfaceRGB.f_blue = Clamp01 (rgb[2]);
		attr.material.specularRGB.f_red = attr.material.specularRGB.f_green = attr.material.specularRGB.f_blue = 1.0;
		attr.material.ifill = ACAPI_CreateAttributeIndex (1);
		attr.material.fillCol = 1;
		GSErrCode err = ACAPI_Attribute_Create (&attr, nullptr);
		if (err != NoError) throw std::runtime_error ("Oberfläche konnte nicht angelegt werden: " + utf8Name);
		found = attr.header.index;
	}
	cache[utf8Name] = found;
	return found;
}

/** Ebenenname nach Material- oder Knotenname der GLB. */
std::string LayerFor (const GlbMesh& mesh)
{
	auto has = [] (const std::string& s, const char* needle) { return s.find (needle) != std::string::npos; };
	const std::string m = mesh.materialName, n = mesh.nodeName;
	if (m == "terrain" || has (n, "Gelaende") || has (n, "Gelände")) return "gisloader Gelände";
	if (m == "roof" || m == "wall" || m == "ground" || has (n, "Dach") || has (n, "Wand")) return "gisloader Gebäude";
	if (m == "footprint" || has (m, "structure")) return "gisloader Bauwerke";
	if (has (m, "landuse")) return "gisloader Nutzung";
	if (has (m, "parcel") || has (n, "Flurst")) return "gisloader Flurstücke";
	if (has (m, "contour")) return "gisloader Höhenlinien";
	if (has (m, "tree") || has (n, "Baum")) return "gisloader Bäume";
	if (has (m, "mesh") || has (n, "Mesh")) return "gisloader Mesh";
	return "gisloader Sonstiges";
}

/** Ebene nach Name; legt sie an, wenn es sie nicht gibt. */
API_AttributeIndex EnsureLayer (const std::string& utf8Name, std::map<std::string, API_AttributeIndex>& cache)
{
	auto it = cache.find (utf8Name);
	if (it != cache.end ()) return it->second;
	const GS::UniString wanted (utf8Name.c_str (), CC_UTF8);
	API_AttributeIndex found = APIInvalidAttributeIndex;
	ACAPI_Attribute_EnumerateAttributesByType (API_LayerID, [&] (API_Attribute& attr) {
		if (found != APIInvalidAttributeIndex) return;
		GS::UniString name = attr.header.uniStringNamePtr != nullptr ? *attr.header.uniStringNamePtr : GS::UniString (attr.header.name, CC_UTF8);
		if (name == wanted) found = attr.header.index;
	});
	if (found == APIInvalidAttributeIndex) {
		API_Attribute attr = {};
		attr.header.typeID = API_LayerID;
		GS::UniString uniName = wanted;
		attr.header.uniStringNamePtr = &uniName;
		GSErrCode err = ACAPI_Attribute_Create (&attr, nullptr);
		if (err != NoError) throw std::runtime_error ("Ebene konnte nicht angelegt werden: " + utf8Name);
		found = attr.header.index;
	}
	cache[utf8Name] = found;
	return found;
}

struct EdgeKey {
	UInt32 a, b;
	bool operator< (const EdgeKey& o) const { return a < o.a || (a == o.a && b < o.b); }
};

/** Ein Morph aus einem Dreiecksnetz; Achsen glTF (Y-up) → Archicad (Z-up): x, -z, y. */
GSErrCode CreateMorph (const GlbMesh& mesh, API_AttributeIndex layer, API_AttributeIndex surface, const GS::UniString& label)
{
	API_Element element = {};
	element.header.type = API_MorphID;
	GSErrCode err = ACAPI_Element_GetDefaults (&element, nullptr);
	if (err != NoError) return err;
	element.header.layer = layer;
	double* tmx = element.morph.tranmat.tmx;
	for (int i = 0; i < 12; ++i) tmx[i] = 0.0;
	tmx[0] = 1.0; tmx[5] = 1.0; tmx[10] = 1.0;

	void* body = nullptr;
	err = ACAPI_Body_Create (nullptr, nullptr, &body);
	if (err != NoError) return err;

	const size_t nVerts = mesh.positions.size () / 3;
	std::vector<UInt32> verts (nVerts);
	for (size_t i = 0; i < nVerts; ++i) {
		API_Coord3D c;
		c.x = mesh.positions[i * 3];
		c.y = -mesh.positions[i * 3 + 2];
		c.z = mesh.positions[i * 3 + 1];
		ACAPI_Body_AddVertex (body, c, verts[i]);
	}
	std::map<EdgeKey, Int32> edges;
	auto edgeOf = [&] (UInt32 v1, UInt32 v2) -> Int32 {
		const bool forward = v1 < v2;
		EdgeKey key { forward ? v1 : v2, forward ? v2 : v1 };
		auto it = edges.find (key);
		Int32 idx;
		if (it == edges.end ()) {
			ACAPI_Body_AddEdge (body, verts[key.a], verts[key.b], idx);
			edges[key] = idx;
		} else {
			idx = it->second;
		}
		return forward ? idx : -idx;
	};
	API_OverriddenAttribute material;
	material = surface;
	UInt32 polyIndex;
	for (size_t t = 0; t + 2 < mesh.indices.size (); t += 3) {
		const UInt32 a = mesh.indices[t], b = mesh.indices[t + 1], c = mesh.indices[t + 2];
		if (a >= nVerts || b >= nVerts || c >= nVerts || a == b || b == c || a == c) continue;
		ACAPI_Body_AddPolygon (body, { edgeOf (a, b), edgeOf (b, c), edgeOf (c, a) }, 0, material, polyIndex);
	}
	API_ElementMemo memo = {};
	ACAPI_Body_Finish (body, &memo.morphBody, &memo.morphMaterialMapTable);
	ACAPI_Body_Dispose (&body);
	err = ACAPI_Element_Create (&element, &memo);
	ACAPI_DisposeElemMemoHdls (&memo);
	(void) label;  // Element-ID: Setter im DevKit 28 nicht gefunden; kommt über Eigenschaften nach
	return err;
}

/** Linienzug als Polylinie im Grundriss (x = Ost, y = Nord); z entfällt. */
GSErrCode CreatePolyline (const std::vector<double>& xyz, API_AttributeIndex layer)
{
	const Int32 n = static_cast<Int32> (xyz.size () / 3);
	if (n < 2) return NoError;
	API_Element element = {};
	element.header.type = API_PolyLineID;
	GSErrCode err = ACAPI_Element_GetDefaults (&element, nullptr);
	if (err != NoError) return err;
	element.header.layer = layer;
	element.polyLine.poly.nCoords = n;
	element.polyLine.poly.nSubPolys = 1;
	element.polyLine.poly.nArcs = 0;
	API_ElementMemo memo = {};
	memo.coords = reinterpret_cast<API_Coord**> (BMAllocateHandle ((n + 1) * sizeof (API_Coord), ALLOCATE_CLEAR, 0));
	memo.pends = reinterpret_cast<Int32**> (BMAllocateHandle (2 * sizeof (Int32), ALLOCATE_CLEAR, 0));
	if (memo.coords == nullptr || memo.pends == nullptr) { ACAPI_DisposeElemMemoHdls (&memo); return APIERR_MEMFULL; }
	(*memo.coords)[0].x = -1.0;
	(*memo.coords)[0].y = 0.0;
	for (Int32 i = 0; i < n; ++i) {
		(*memo.coords)[i + 1].x = xyz[static_cast<size_t> (i) * 3];
		(*memo.coords)[i + 1].y = -xyz[static_cast<size_t> (i) * 3 + 2];
	}
	(*memo.pends)[0] = 0;
	(*memo.pends)[1] = n;
	err = ACAPI_Element_Create (&element, &memo);
	ACAPI_DisposeElemMemoHdls (&memo);
	return err;
}

void ApplyGeoref (const Georef& g, const std::string& name)
{
	if (!g.valid) return;
	API_GeoLocation loc = {};
	if (ACAPI_GeoLocation_GetGeoLocation (&loc) != NoError) return;
	loc.placeInfo.longitude = g.lon;
	loc.placeInfo.latitude = g.lat;
	loc.placeInfo.altitude = g.originZ;
	loc.geoReferenceData.name = GS::UniString (("gisloader · " + name).c_str (), CC_UTF8);
	loc.geoReferenceData.mapProjection = GS::UniString (("EPSG:" + std::to_string (g.epsg)).c_str (), CC_UTF8);
	loc.geoReferenceData.eastings = g.originX;
	loc.geoReferenceData.northings = g.originY;
	loc.geoReferenceData.orthogonalHeight = g.originZ;
	loc.geoReferenceData.xAxisAbscissa = 1.0;
	loc.geoReferenceData.xAxisOrdinate = 0.0;
	loc.geoReferenceData.scale = 1.0;
	ACAPI_GeoLocation_SetGeoLocation (&loc);
}

} // namespace

void ImportSession::Begin (const std::string& n)
{
	active = true;
	name = n;
	georef = Georef ();
	glbs.clear ();
}

void ImportSession::SetGeoref (const Georef& g) { georef = g; }

void ImportSession::AddGlb (std::vector<uint8_t>&& bytes) { glbs.push_back (std::move (bytes)); }

std::string ImportSession::Finish ()
{
	if (!active) throw std::runtime_error ("kein Import begonnen");
	active = false;
	std::vector<GlbModel> models;
	for (const auto& bytes : glbs) models.push_back (ReadGlb (bytes));
	glbs.clear ();

	size_t created = 0, skipped = 0, lines = 0;
	std::map<std::string, API_AttributeIndex> layers;
	std::map<std::string, API_AttributeIndex> surfaces;
	GSErrCode err = ACAPI_CallUndoableCommand (GS::UniString (("gisloader: " + name).c_str (), CC_UTF8), [&] () -> GSErrCode {
		for (const GlbModel& model : models) {
			for (const GlbMesh& mesh : model.meshes) {
				if (mesh.indices.size () < 3) { ++skipped; continue; }
				API_AttributeIndex layer = EnsureLayer (LayerFor (mesh), layers);
				// Texturierte Flächen (Gelände, Mesh) tragen Weiß als Grundfarbe; Archicad bekommt dafür ein Grün-Grau.
				double rgb[3] = {mesh.color[0], mesh.color[1], mesh.color[2]};
				if (mesh.textured) { rgb[0] = 0.56; rgb[1] = 0.62; rgb[2] = 0.50; }
				API_AttributeIndex surface = EnsureSurface (SurfaceNameFor (mesh.materialName), rgb, surfaces);
				GS::UniString label (mesh.nodeName.c_str (), CC_UTF8);
				if (CreateMorph (mesh, layer, surface, label) == NoError) ++created; else ++skipped;
			}
			for (const GlbLine& line : model.lines) {
				GlbMesh probe;
				probe.materialName = line.materialName;
				probe.nodeName = line.nodeName;
				API_AttributeIndex layer = EnsureLayer (LayerFor (probe), layers);
				for (const auto& poly : line.polylines) {
					if (CreatePolyline (poly, layer) == NoError) ++lines; else ++skipped;
				}
			}
		}
		return NoError;
	});
	if (err != NoError) throw std::runtime_error ("Archicad hat den Import abgelehnt (Fehler " + std::to_string (err) + ")");
	ApplyGeoref (georef, name);
	return std::to_string (created) + " Morph(s), " + std::to_string (lines) + " Polylinie(n) angelegt, " + std::to_string (skipped) + " übersprungen, Ebenen: " + std::to_string (layers.size ()) + ", Oberflächen: " + std::to_string (surfaces.size ());
}

} // namespace gisloader
