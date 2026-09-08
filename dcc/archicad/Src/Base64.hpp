// Base64-Dekodierung für GLB-Daten, die die Web-App über die JavaScript-Brücke übergibt.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace gisloader {

inline std::vector<uint8_t> DecodeBase64 (const std::string& in)
{
	static int table[256];
	static bool init = false;
	if (!init) {
		for (int& t : table) t = -1;
		const char* chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
		for (int k = 0; k < 64; ++k) table[static_cast<unsigned char> (chars[k])] = k;
		table[static_cast<unsigned char> ('-')] = 62;
		table[static_cast<unsigned char> ('_')] = 63;
		init = true;
	}
	std::vector<uint8_t> out;
	out.reserve (in.size () * 3 / 4);
	int val = 0, bits = -8;
	for (unsigned char c : in) {
		if (c == '=' || c == '\n' || c == '\r' || c == ' ') continue;
		int d = table[c];
		if (d < 0) continue;
		val = (val << 6) | d;
		bits += 6;
		if (bits >= 0) {
			out.push_back (static_cast<uint8_t> ((val >> bits) & 0xFF));
			bits -= 8;
		}
	}
	return out;
}

} // namespace gisloader
