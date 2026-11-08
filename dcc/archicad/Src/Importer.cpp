#include "Importer.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <map>
#include <set>
#include <stdexcept>
#include <utility>

#include "GlbReader.hpp"

namespace gisloader {

namespace {

/** Abschnitte von „ALKIS Detail“: Kennung im Material (alkis-<kennung>-…) und Knotenname. */
struct DetailSection { const char* id; const char* node; const char* label; };
const DetailSection kDetailSections[] = {
	{"gebaeude", "Gebaeudedetail", "Gebäudedetail"},
	{"grundstueck", "Grundstueck", "Grundstück"},
	{"umgebung", "Umgebung", "Umgebung"},
	{"strassenraum", "Strassenraum", "Straßenraum"},
	{"vegetation", "Vegetation", "Vegetation"},
	{"recht", "Recht", "Recht"},
};

std::string DetailLabelForNode (const std::string& node)
{
	for (const auto& s : kDetailSections) if (node == s.node) return s.label;
	return node;
}

/** Anzeigename einer Oberfläche je glTF-Material. */
std::string SurfaceNameFor (const std::string& material)
{
	for (const auto& s : kDetailSections)
		if (material.rfind (std::string ("alkis-") + s.id + "-", 0) == 0) return std::string ("gisloader ALKIS ") + s.label;
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

/** Wurzelknoten der flachen 2D-Fassung (Export-Option „2D-Ebenen auf der Nullebene“). */
const char* const kPlan2dRoot = "Plan_2D";

/**
 * Ebene aus dem Knotenpfad: „ALKIS Detail“ je Abschnitt („gisloader ALKIS Grundstück“),
 * sonst wie bisher nach Material- und Knotenname. Die flache Fassung unter „Plan_2D“
 * bekommt eigene Ebenen („gisloader 2D …“), damit sie sich getrennt schalten lässt.
 */
std::string LayerForPath (const std::vector<std::string>& path, const std::string& material, const std::string& node, bool& plan2d)
{
	size_t at = 0;
	plan2d = !path.empty () && path[0] == kPlan2dRoot;
	if (plan2d) at = 1;
	std::string layer;
	if (path.size () > at + 1 && path[at] == "ALKIS_Detail") {
		layer = "gisloader ALKIS " + DetailLabelForNode (path[at + 1]);
	} else {
		GlbMesh probe;
		probe.materialName = material;
		probe.nodeName = path.size () > at ? path[at] + "/" + node : node;
		layer = LayerFor (probe);
	}
	if (plan2d && layer.rfind ("gisloader ", 0) == 0) layer = "gisloader 2D " + layer.substr (10);
	return layer;
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
GSErrCode CreatePolyline (const std::vector<double>& xyz, API_AttributeIndex layer, short pen = 0)
{
	const Int32 n = static_cast<Int32> (xyz.size () / 3);
	if (n < 2) return NoError;
	API_Element element = {};
	element.header.type = API_PolyLineID;
	GSErrCode err = ACAPI_Element_GetDefaults (&element, nullptr);
	if (err != NoError) return err;
	element.header.layer = layer;
	if (pen > 0) element.polyLine.linePen.Set (pen, 0);
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


/** Stifte der aktiven Stiftpalette, einmal je Import gelesen. */
struct PenPalette {
	std::vector<API_Pen> pens;
	void Load ()
	{
		pens.clear ();
		UInt32 n = 0;
		if (ACAPI_Attribute_GetPenNum (n) != NoError) return;
		for (UInt32 i = 1; i <= n && i < 256; ++i) {
			API_Pen pen = {};
			pen.index = static_cast<short> (i);
			if (ACAPI_Attribute_GetPen (pen) == NoError) pens.push_back (pen);
		}
	}
	/** Stift mit der nächstliegenden Farbe; 0, wenn keine Palette da ist (Archicad nimmt dann den Standard). */
	short Nearest (const double rgb[3]) const
	{
		short best = 0;
		double bestD = 1e9;
		for (const API_Pen& p : pens) {
			const double dr = p.rgb.f_red - rgb[0], dg = p.rgb.f_green - rgb[1], db = p.rgb.f_blue - rgb[2];
			const double d = dr * dr + dg * dg + db * db;
			if (d < bestD) { bestD = d; best = p.index; }
		}
		return best;
	}
};

/** Erste Füllung einer Art, die für Schraffuren taugt (Vollfläche, Leer). */
API_AttributeIndex FindFill (API_FillSubtype subType)
{
	API_AttributeIndex found = APIInvalidAttributeIndex;
	ACAPI_Attribute_EnumerateAttributesByType (API_FilltypeID, [&] (API_Attribute& attr) {
		if (found != APIInvalidAttributeIndex) return;
		if (attr.filltype.subType == subType && (attr.header.flags & APIFill_ForPoly) != 0) found = attr.header.index;
	});
	return found;
}

/**
 * Darstellung einer Fläche im Lageplan: Füllfarbe (zur Exportfarbe aufgehellt),
 * Konturstift (abgedunkelt) und Rang für die Zeichenreihenfolge (höher liegt oben).
 * Rechte überlagern alles und bleiben deshalb ungefüllt.
 */
struct HatchStyle {
	double fill[3] = {0.8, 0.8, 0.8};
	double contour[3] = {0.3, 0.3, 0.3};
	bool filled = true;
	int rank = 25;
};

HatchStyle HatchStyleFor (const std::string& material, const double color[3])
{
	auto starts = [&] (const char* prefix) { return material.rfind (prefix, 0) == 0; };
	double lighten = 0.5;
	HatchStyle st;
	if (starts ("alkis-gebaeude-")) { lighten = 0.2; st.rank = 40; }
	else if (starts ("alkis-umgebung-")) { lighten = 0.45; st.rank = 30; }
	else if (starts ("alkis-vegetation-")) { lighten = 0.5; st.rank = 20; }
	else if (starts ("alkis-strassenraum-")) { lighten = 0.65; st.rank = 10; }
	else if (starts ("alkis-recht-")) { st.filled = false; st.rank = 50; }
	else if (starts ("landuse-")) { lighten = 0.6; st.rank = 5; }
	else if (material == "footprint" || material.find ("structure") != std::string::npos) { lighten = 0.3; st.rank = 35; }
	for (int i = 0; i < 3; ++i) {
		const double c = Clamp01 (color[i]);
		st.fill[i] = c + (1.0 - c) * lighten;
		st.contour[i] = c * 0.55;
	}
	return st;
}

/** Was die Schraffuren eines Imports gemeinsam brauchen. */
struct HatchContext {
	PenPalette palette;
	API_AttributeIndex solidFill = APIInvalidAttributeIndex;
	API_AttributeIndex emptyFill = APIInvalidAttributeIndex;
	void Load ()
	{
		palette.Load ();
		solidFill = FindFill (APIFill_Solid);
		emptyFill = FindFill (APIFill_Empty);
	}
};

using Pt = std::pair<double, double>;

double RingArea (const std::vector<Pt>& r)
{
	double a = 0;
	for (size_t i = 0, n = r.size (); i < n; ++i) {
		const Pt& p = r[i];
		const Pt& q = r[(i + 1) % n];
		a += p.first * q.second - q.first * p.second;
	}
	return a / 2;
}

bool InRing (double x, double y, const std::vector<Pt>& r)
{
	bool in = false;
	for (size_t i = 0, j = r.size () - 1; i < r.size (); j = i++) {
		const Pt& a = r[i];
		const Pt& b = r[j];
		if ((a.second > y) != (b.second > y) && x < (b.first - a.first) * (y - a.second) / (b.second - a.second) + a.first) in = !in;
	}
	return in;
}

/**
 * Umrisse eines flachen Dreiecksnetzes im Grundriss (x = Ost, y = Nord): Kanten, die nur
 * ein Dreieck berühren, zu Ringen verkettet. Gleiche Lagen (auf mm gerundet) gelten als
 * ein Punkt, damit getrennte Vertices desselben Umrisses zusammenfinden.
 */
std::vector<std::vector<Pt>> BoundaryRings (const GlbMesh& mesh)
{
	const size_t n = mesh.positions.size () / 3;
	std::map<std::pair<long long, long long>, size_t> keyOf;
	std::vector<size_t> id (n);
	std::vector<Pt> pts;
	for (size_t i = 0; i < n; ++i) {
		const double x = mesh.positions[i * 3], y = -mesh.positions[i * 3 + 2];
		const auto key = std::make_pair (std::llround (x * 1000), std::llround (y * 1000));
		auto it = keyOf.find (key);
		if (it == keyOf.end ()) { it = keyOf.emplace (key, pts.size ()).first; pts.push_back ({x, y}); }
		id[i] = it->second;
	}
	std::map<std::pair<size_t, size_t>, int> count;
	auto undirected = [] (size_t a, size_t b) { return a < b ? std::make_pair (a, b) : std::make_pair (b, a); };
	std::vector<std::pair<size_t, size_t>> directed;
	for (size_t t = 0; t + 2 < mesh.indices.size (); t += 3) {
		const size_t a = id[mesh.indices[t]], b = id[mesh.indices[t + 1]], c = id[mesh.indices[t + 2]];
		if (a == b || b == c || a == c) continue;
		for (auto e : {std::make_pair (a, b), std::make_pair (b, c), std::make_pair (c, a)}) {
			++count[undirected (e.first, e.second)];
			directed.push_back (e);
		}
	}
	std::multimap<size_t, size_t> next;
	for (const auto& e : directed)
		if (count[undirected (e.first, e.second)] == 1) next.emplace (e.first, e.second);
	std::vector<std::vector<Pt>> rings;
	while (!next.empty ()) {
		auto it = next.begin ();
		const size_t start = it->first;
		size_t cur = it->second;
		next.erase (it);
		std::vector<Pt> ring {pts[start]};
		while (cur != start) {
			ring.push_back (pts[cur]);
			auto nx = next.find (cur);
			if (nx == next.end ()) break;
			cur = nx->second;
			next.erase (nx);
		}
		if (cur == start && ring.size () >= 3 && std::fabs (RingArea (ring)) > 1e-6) rings.push_back (std::move (ring));
	}
	return rings;
}

/** Schraffur aus Außenring und Löchern (Archicad: erster Teilring außen, Ringe geschlossen). */
GSErrCode CreateHatch (const std::vector<const std::vector<Pt>*>& rings, API_AttributeIndex layer, const HatchStyle& style, const HatchContext& ctx)
{
	API_Element element = {};
	element.header.type = API_HatchID;
	GSErrCode err = ACAPI_Element_GetDefaults (&element, nullptr);
	if (err != NoError) return err;
	element.header.layer = layer;
	element.hatch.hatchType = API_FillHatch;
	element.hatch.showArea = false;
	// Kontur im nächstliegenden Stift, Füllung als Vollfläche in RGB (Rechte: leer, nur Kontur).
	const short contour = ctx.palette.Nearest (style.contour);
	if (contour > 0) element.hatch.contPen.Set (contour, 0);
	const API_AttributeIndex fill = style.filled ? ctx.solidFill : ctx.emptyFill;
	if (fill != APIInvalidAttributeIndex) element.hatch.fillInd = fill;
	if (style.filled) {
		const short fillPen = ctx.palette.Nearest (style.fill);
		if (fillPen > 0) element.hatch.fillPen.Set (fillPen, 0);
		element.hatch.hatchFlags |= APIHatch_HasFgRGBColor;
		element.hatch.foregroundRGB.f_red = style.fill[0];
		element.hatch.foregroundRGB.f_green = style.fill[1];
		element.hatch.foregroundRGB.f_blue = style.fill[2];
	}
	Int32 nCoords = 0;
	for (const auto* r : rings) nCoords += static_cast<Int32> (r->size ()) + 1;
	element.hatch.poly.nCoords = nCoords;
	element.hatch.poly.nSubPolys = static_cast<Int32> (rings.size ());
	element.hatch.poly.nArcs = 0;
	API_ElementMemo memo = {};
	memo.coords = reinterpret_cast<API_Coord**> (BMAllocateHandle ((nCoords + 1) * sizeof (API_Coord), ALLOCATE_CLEAR, 0));
	memo.pends = reinterpret_cast<Int32**> (BMAllocateHandle ((static_cast<Int32> (rings.size ()) + 1) * sizeof (Int32), ALLOCATE_CLEAR, 0));
	if (memo.coords == nullptr || memo.pends == nullptr) { ACAPI_DisposeElemMemoHdls (&memo); return APIERR_MEMFULL; }
	Int32 k = 1;
	(*memo.pends)[0] = 0;
	for (size_t ri = 0; ri < rings.size (); ++ri) {
		std::vector<Pt> r = *rings[ri];
		// Außenring gegen den Uhrzeigersinn, Löcher im Uhrzeigersinn
		if ((RingArea (r) > 0) != (ri == 0)) std::reverse (r.begin (), r.end ());
		for (const Pt& p : r) { (*memo.coords)[k].x = p.first; (*memo.coords)[k].y = p.second; ++k; }
		(*memo.coords)[k] = (*memo.coords)[k - static_cast<Int32> (r.size ())];
		++k;
		(*memo.pends)[ri + 1] = k - 1;
	}
	err = ACAPI_Element_Create (&element, &memo);
	ACAPI_DisposeElemMemoHdls (&memo);
	return err;
}

/** Flache Fläche (Plan_2D) als Schraffuren: je Außenring eine, mit den Löchern darin. */
size_t CreateHatches (const GlbMesh& mesh, API_AttributeIndex layer, const HatchContext& ctx, size_t& failed)
{
	const HatchStyle style = HatchStyleFor (mesh.materialName, mesh.color);
	std::vector<std::vector<Pt>> rings = BoundaryRings (mesh);
	std::sort (rings.begin (), rings.end (), [] (const std::vector<Pt>& a, const std::vector<Pt>& b) { return std::fabs (RingArea (a)) > std::fabs (RingArea (b)); });
	// Tiefe je Ring = Zahl der größeren Ringe, die ihn enthalten; gerade = außen, ungerade = Loch des nächsten.
	std::vector<int> depth (rings.size (), 0);
	std::vector<long> parent (rings.size (), -1);
	for (size_t i = 0; i < rings.size (); ++i) {
		const Pt& a = rings[i][0];
		const Pt& b = rings[i][1];
		const double mx = (a.first + b.first) / 2, my = (a.second + b.second) / 2;
		for (size_t j = 0; j < i; ++j)
			if (InRing (mx, my, rings[j])) { ++depth[i]; parent[i] = static_cast<long> (j); }
	}
	size_t created = 0;
	for (size_t i = 0; i < rings.size (); ++i) {
		if (depth[i] % 2 != 0) continue;
		std::vector<const std::vector<Pt>*> group {&rings[i]};
		for (size_t j = i + 1; j < rings.size (); ++j)
			if (depth[j] == depth[i] + 1 && parent[j] == static_cast<long> (i)) group.push_back (&rings[j]);
		if (CreateHatch (group, layer, style, ctx) == NoError) ++created; else ++failed;
	}
	return created;
}

/**
 * Kurze Grenzpunktnummer aus der 15-stelligen ALKIS-Punktkennung: Nummerierungsbezirk (9),
 * Punktart (1), Punktnummer (5). Im Plan steht nur die Punktnummer ohne führende Nullen;
 * andere Formen bleiben unverändert.
 */
std::string ShortPointNumber (const std::string& kennung)
{
	if (kennung.size () != 15 || kennung.find_first_not_of ("0123456789") != std::string::npos) return kennung;
	const std::string number = kennung.substr (10);
	const size_t first = number.find_first_not_of ('0');
	return first == std::string::npos ? "0" : number.substr (first);
}

/** Punkt als Hotspot (Lage x = Ost, y = Nord, Höhe aus der GLB). */
GSErrCode CreateHotspot (double x, double y, double z, API_AttributeIndex layer)
{
	API_Element element = {};
	element.header.type = API_HotspotID;
	GSErrCode err = ACAPI_Element_GetDefaults (&element, nullptr);
	if (err != NoError) return err;
	element.header.layer = layer;
	element.hotspot.pos.x = x;
	element.hotspot.pos.y = y;
	element.hotspot.height = z;
	return ACAPI_Element_Create (&element, nullptr);
}

/** Einzeiliger Text links unten am Punkt (Grenzpunktnummer). */
GSErrCode CreateLabel (double x, double y, const std::string& utf8, API_AttributeIndex layer)
{
	API_Element element = {};
	element.header.type = API_TextID;
	GSErrCode err = ACAPI_Element_GetDefaults (&element, nullptr);
	if (err != NoError) return err;
	element.header.layer = layer;
	element.text.anchor = APIAnc_LB;
	element.text.just = APIJust_Left;
	element.text.loc.x = x + 0.15;
	element.text.loc.y = y + 0.15;
	element.text.nonBreaking = true;
	element.text.nLine = 1;
	API_ElementMemo memo = {};
	memo.textContent = new GS::UniString (utf8.c_str (), CC_UTF8);
	err = ACAPI_Element_Create (&element, &memo);
	ACAPI_DisposeElemMemoHdls (&memo);
	return err;
}

/** Grundriss auf den importierten Ausschnitt zoomen (nur, wenn ein Grundriss vorne liegt). */
void ZoomToModels (const std::vector<GlbModel>& models)
{
	API_DatabaseInfo db = {};
	if (ACAPI_Database_GetCurrentDatabase (&db) != NoError || db.typeID != APIWind_FloorPlanID) return;
	double xMin = 1e300, yMin = 1e300, xMax = -1e300, yMax = -1e300;
	auto add = [&] (const std::vector<double>& pos) {
		for (size_t i = 0; i + 2 < pos.size (); i += 3) {
			const double x = pos[i], y = -pos[i + 2];
			xMin = std::min (xMin, x); xMax = std::max (xMax, x);
			yMin = std::min (yMin, y); yMax = std::max (yMax, y);
		}
	};
	for (const GlbModel& m : models) {
		for (const GlbMesh& mesh : m.meshes) add (mesh.positions);
		for (const GlbPoints& pts : m.points) add (pts.positions);
	}
	if (xMin > xMax) return;
	const double margin = 0.05 * std::max (xMax - xMin, yMax - yMin);
	API_Box box = {};
	box.xMin = xMin - margin; box.yMin = yMin - margin;
	box.xMax = xMax + margin; box.yMax = yMax + margin;
	ACAPI_View_Zoom (&box);
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

	size_t created = 0, skipped = 0, lines = 0, hatches = 0, hotspots = 0, labels = 0;
	std::map<std::string, API_AttributeIndex> layers;
	std::map<std::string, API_AttributeIndex> surfaces;
	GSErrCode err = ACAPI_CallUndoableCommand (GS::UniString (("gisloader: " + name).c_str (), CC_UTF8), [&] () -> GSErrCode {
		HatchContext hatchCtx;
		hatchCtx.Load ();
		for (const GlbModel& model : models) {
			// Flächen des Lageplans nach Rang anlegen: was später entsteht, liegt oben (Gebäude über Straßen).
			std::vector<std::pair<const GlbMesh*, API_AttributeIndex>> planMeshes;
			for (const GlbMesh& mesh : model.meshes) {
				if (mesh.indices.size () < 3) { ++skipped; continue; }
				bool plan2d = false;
				API_AttributeIndex layer = EnsureLayer (LayerForPath (mesh.path, mesh.materialName, mesh.nodeName, plan2d), layers);
				if (plan2d) {
					planMeshes.emplace_back (&mesh, layer);
					continue;
				}
				// Texturierte Flächen (Gelände, Mesh) tragen Weiß als Grundfarbe; Archicad bekommt dafür ein Grün-Grau.
				double rgb[3] = {mesh.color[0], mesh.color[1], mesh.color[2]};
				if (mesh.textured) { rgb[0] = 0.56; rgb[1] = 0.62; rgb[2] = 0.50; }
				API_AttributeIndex surface = EnsureSurface (SurfaceNameFor (mesh.materialName), rgb, surfaces);
				GS::UniString label (mesh.nodeName.c_str (), CC_UTF8);
				if (CreateMorph (mesh, layer, surface, label) == NoError) ++created; else ++skipped;
			}
			std::stable_sort (planMeshes.begin (), planMeshes.end (), [] (const auto& a, const auto& b) {
				return HatchStyleFor (a.first->materialName, a.first->color).rank < HatchStyleFor (b.first->materialName, b.first->color).rank;
			});
			for (const auto& [mesh, layer] : planMeshes) hatches += CreateHatches (*mesh, layer, hatchCtx, skipped);
			for (const GlbLine& line : model.lines) {
				bool plan2d = false;
				API_AttributeIndex layer = EnsureLayer (LayerForPath (line.path, line.materialName, line.nodeName, plan2d), layers);
				// Linien im Stift ihrer Exportfarbe (abgedunkelt wie die Konturen der Flächen).
				double dark[3];
				for (int i = 0; i < 3; ++i) dark[i] = Clamp01 (line.color[i]) * 0.7;
				const short pen = hatchCtx.palette.Nearest (dark);
				for (const auto& poly : line.polylines) {
					if (CreatePolyline (poly, layer, pen) == NoError) ++lines; else ++skipped;
				}
			}
			for (const GlbPoints& pts : model.points) {
				bool plan2d = false;
				API_AttributeIndex layer = EnsureLayer (LayerForPath (pts.path, pts.materialName, pts.nodeName, plan2d), layers);
				auto number = pts.attributes.find ("punktkennung");
				for (size_t i = 0; i + 2 < pts.positions.size (); i += 3) {
					const double x = pts.positions[i], y = -pts.positions[i + 2], z = pts.positions[i + 1];
					// Im Plan nur die kurze Punktnummer; die volle Punktkennung bleibt Attribut des Exports
					// (Hotspots haben in Archicad keine Element-ID: APIERR_BADELEMENTTYPE).
					if (CreateHotspot (x, y, z, layer) == NoError) ++hotspots; else ++skipped;
					if (number != pts.attributes.end () && !number->second.empty ()) {
						if (CreateLabel (x, y, ShortPointNumber (number->second), layer) == NoError) ++labels; else ++skipped;
					}
				}
			}
		}
		return NoError;
	});
	if (err != NoError) throw std::runtime_error ("Archicad hat den Import abgelehnt (Fehler " + std::to_string (err) + ")");
	ApplyGeoref (georef, name);
	ZoomToModels (models);
	std::string summary = std::to_string (created) + " Morph(s), " + std::to_string (lines) + " Polylinie(n)";
	if (hatches) summary += ", " + std::to_string (hatches) + " Schraffur(en)";
	if (hotspots) summary += ", " + std::to_string (hotspots) + " Hotspot(s)";
	if (labels) summary += ", " + std::to_string (labels) + " Nummer(n)";
	return summary + " angelegt, " + std::to_string (skipped) + " übersprungen, Ebenen: " + std::to_string (layers.size ()) + ", Oberflächen: " + std::to_string (surfaces.size ());
}

} // namespace gisloader
