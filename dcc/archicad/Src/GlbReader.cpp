#include "GlbReader.hpp"

#include <cmath>
#include <cstring>
#include <functional>
#include <stdexcept>

#include "MiniJson.hpp"

namespace gisloader {

namespace {

struct Mat4 {
	double m[16];  // spaltenweise wie glTF
	static Mat4 Identity () { Mat4 r; for (int i = 0; i < 16; ++i) r.m[i] = (i % 5 == 0) ? 1.0 : 0.0; return r; }
	Mat4 operator* (const Mat4& o) const {
		Mat4 r;
		for (int c = 0; c < 4; ++c)
			for (int rr = 0; rr < 4; ++rr) {
				double s = 0;
				for (int k = 0; k < 4; ++k) s += m[k * 4 + rr] * o.m[c * 4 + k];
				r.m[c * 4 + rr] = s;
			}
		return r;
	}
	void Apply (double& x, double& y, double& z) const {
		double nx = m[0] * x + m[4] * y + m[8] * z + m[12];
		double ny = m[1] * x + m[5] * y + m[9] * z + m[13];
		double nz = m[2] * x + m[6] * y + m[10] * z + m[14];
		x = nx; y = ny; z = nz;
	}
};

Mat4 NodeMatrix (const JsonValue& node)
{
	if (node.Has ("matrix") && node["matrix"].Size () == 16) {
		Mat4 r;
		for (size_t i = 0; i < 16; ++i) r.m[i] = node["matrix"][i].NumberOr (0.0);
		return r;
	}
	double t[3] = {0, 0, 0}, s[3] = {1, 1, 1}, q[4] = {0, 0, 0, 1};
	for (size_t i = 0; i < 3; ++i) {
		if (node.Has ("translation")) t[i] = node["translation"][i].NumberOr (0.0);
		if (node.Has ("scale")) s[i] = node["scale"][i].NumberOr (1.0);
	}
	for (size_t i = 0; i < 4; ++i)
		if (node.Has ("rotation")) q[i] = node["rotation"][i].NumberOr (i == 3 ? 1.0 : 0.0);
	const double x = q[0], y = q[1], z = q[2], w = q[3];
	Mat4 r = Mat4::Identity ();
	r.m[0] = (1 - 2 * (y * y + z * z)) * s[0];
	r.m[1] = (2 * (x * y + z * w)) * s[0];
	r.m[2] = (2 * (x * z - y * w)) * s[0];
	r.m[4] = (2 * (x * y - z * w)) * s[1];
	r.m[5] = (1 - 2 * (x * x + z * z)) * s[1];
	r.m[6] = (2 * (y * z + x * w)) * s[1];
	r.m[8] = (2 * (x * z + y * w)) * s[2];
	r.m[9] = (2 * (y * z - x * w)) * s[2];
	r.m[10] = (1 - 2 * (x * x + y * y)) * s[2];
	r.m[12] = t[0]; r.m[13] = t[1]; r.m[14] = t[2];
	return r;
}

struct AccessorView {
	const uint8_t* data = nullptr;
	size_t count = 0;
	size_t stride = 0;
	int componentType = 0;
	int components = 1;
};

AccessorView ViewOf (const JsonValue& gltf, const uint8_t* bin, size_t binLen, long accessorIndex)
{
	const JsonValue& acc = gltf["accessors"][static_cast<size_t> (accessorIndex)];
	if (acc.IsNull ()) throw std::runtime_error ("GLB: Accessor fehlt");
	const JsonValue& bv = gltf["bufferViews"][static_cast<size_t> (acc["bufferView"].IntOr (-1))];
	if (bv.IsNull ()) throw std::runtime_error ("GLB: BufferView fehlt (externe Puffer werden nicht unterstützt)");
	if (bv["buffer"].IntOr (0) != 0) throw std::runtime_error ("GLB: nur der eingebettete Puffer 0 wird gelesen");
	AccessorView v;
	v.componentType = static_cast<int> (acc["componentType"].IntOr (5126));
	v.count = static_cast<size_t> (acc["count"].IntOr (0));
	const std::string type = acc["type"].StringOr ("SCALAR");
	v.components = type == "VEC3" ? 3 : type == "VEC2" ? 2 : type == "VEC4" ? 4 : 1;
	size_t compSize = (v.componentType == 5126 || v.componentType == 5125) ? 4 : (v.componentType == 5123 || v.componentType == 5122) ? 2 : 1;
	size_t offset = static_cast<size_t> (bv["byteOffset"].IntOr (0)) + static_cast<size_t> (acc["byteOffset"].IntOr (0));
	v.stride = static_cast<size_t> (bv["byteStride"].IntOr (0));
	if (v.stride == 0) v.stride = compSize * static_cast<size_t> (v.components);
	if (offset + (v.count ? (v.count - 1) * v.stride + compSize * v.components : 0) > binLen)
		throw std::runtime_error ("GLB: Accessor zeigt über den Puffer hinaus");
	v.data = bin + offset;
	return v;
}

} // namespace

GlbModel ReadGlb (const std::vector<uint8_t>& bytes)
{
	if (bytes.size () < 20) throw std::runtime_error ("GLB: Datei zu kurz");
	auto u32 = [&] (size_t at) { uint32_t v; std::memcpy (&v, bytes.data () + at, 4); return v; };
	if (u32 (0) != 0x46546C67u) throw std::runtime_error ("GLB: keine glTF-Binärdatei");
	const uint32_t jsonLen = u32 (12);
	if (u32 (16) != 0x4E4F534Au || 20 + jsonLen > bytes.size ()) throw std::runtime_error ("GLB: JSON-Chunk fehlt");
	const std::string jsonText (reinterpret_cast<const char*> (bytes.data () + 20), jsonLen);
	const uint8_t* bin = nullptr;
	size_t binLen = 0;
	size_t binHeader = 20 + jsonLen;
	if (binHeader + 8 <= bytes.size () && u32 (binHeader + 4) == 0x004E4942u) {
		binLen = u32 (binHeader);
		bin = bytes.data () + binHeader + 8;
		if (binHeader + 8 + binLen > bytes.size ()) throw std::runtime_error ("GLB: Binär-Chunk unvollständig");
	}
	const JsonValue gltf = JsonParser::Parse (jsonText);
	GlbModel model;
	model.attribution = gltf["scenes"][0]["extras"]["attribution"].StringOr (gltf["asset"]["copyright"].StringOr (""));

	std::function<void (long, const Mat4&, const std::string&)> visit = [&] (long nodeIndex, const Mat4& parent, const std::string& parentName) {
		const JsonValue& node = gltf["nodes"][static_cast<size_t> (nodeIndex)];
		if (node.IsNull ()) return;
		const Mat4 world = parent * NodeMatrix (node);
		const std::string name = node["name"].StringOr (parentName);
		if (node.Has ("mesh")) {
			const JsonValue& mesh = gltf["meshes"][static_cast<size_t> (node["mesh"].IntOr (-1))];
			for (size_t p = 0; p < mesh["primitives"].Size (); ++p) {
				const JsonValue& prim = mesh["primitives"][p];
				const long mode = prim["mode"].IntOr (4);
				if (mode != 4) continue;  // nur Dreiecke; Linien (Flurstücke) kommen später als Polylinien
				if (!prim["attributes"].Has ("POSITION") || bin == nullptr) continue;
				GlbMesh out;
				out.nodeName = name;
				out.meshName = mesh["name"].StringOr (name);
				out.materialName = gltf["materials"][static_cast<size_t> (prim["material"].IntOr (-1))]["name"].StringOr ("");
				AccessorView pos = ViewOf (gltf, bin, binLen, prim["attributes"]["POSITION"].IntOr (-1));
				if (pos.componentType != 5126 || pos.components != 3) throw std::runtime_error ("GLB: POSITION muss float vec3 sein");
				out.positions.resize (pos.count * 3);
				for (size_t i = 0; i < pos.count; ++i) {
					float f[3];
					std::memcpy (f, pos.data + i * pos.stride, 12);
					double x = f[0], y = f[1], z = f[2];
					world.Apply (x, y, z);
					out.positions[i * 3] = x; out.positions[i * 3 + 1] = y; out.positions[i * 3 + 2] = z;
				}
				if (prim.Has ("indices")) {
					AccessorView idx = ViewOf (gltf, bin, binLen, prim["indices"].IntOr (-1));
					out.indices.resize (idx.count);
					for (size_t i = 0; i < idx.count; ++i) {
						const uint8_t* at = idx.data + i * idx.stride;
						if (idx.componentType == 5125) { uint32_t v; std::memcpy (&v, at, 4); out.indices[i] = v; }
						else if (idx.componentType == 5123) { uint16_t v; std::memcpy (&v, at, 2); out.indices[i] = v; }
						else out.indices[i] = *at;
					}
				} else {
					out.indices.resize (pos.count);
					for (size_t i = 0; i < pos.count; ++i) out.indices[i] = static_cast<uint32_t> (i);
				}
				out.indices.resize (out.indices.size () - out.indices.size () % 3);
				if (!out.indices.empty ()) model.meshes.push_back (std::move (out));
			}
		}
		for (size_t c = 0; c < node["children"].Size (); ++c)
			visit (node["children"][c].IntOr (-1), world, name);
	};

	const JsonValue& scene = gltf["scenes"][static_cast<size_t> (gltf["scene"].IntOr (0))];
	if (scene.IsNull ()) {
		for (size_t n = 0; n < gltf["nodes"].Size (); ++n) visit (static_cast<long> (n), Mat4::Identity (), "");
	} else {
		for (size_t n = 0; n < scene["nodes"].Size (); ++n) visit (scene["nodes"][n].IntOr (-1), Mat4::Identity (), "");
	}
	return model;
}

} // namespace gisloader
