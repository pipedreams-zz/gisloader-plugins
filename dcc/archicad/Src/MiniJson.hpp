// Kleiner JSON-Leser für den JSON-Chunk einer GLB (glTF 2.0). Keine Abhängigkeit,
// nur das, was der Reader braucht: Objekte, Arrays, Zahlen, Strings, bool, null.
#pragma once

#include <cstdlib>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace gisloader {

struct JsonValue {
	enum class Type { Null, Bool, Number, String, Array, Object };
	Type type = Type::Null;
	bool b = false;
	double num = 0.0;
	std::string str;
	std::vector<JsonValue> arr;
	std::map<std::string, JsonValue> obj;

	bool IsNull () const { return type == Type::Null; }
	bool IsObject () const { return type == Type::Object; }
	bool IsArray () const { return type == Type::Array; }
	bool Has (const std::string& key) const { return type == Type::Object && obj.find (key) != obj.end (); }
	const JsonValue& operator[] (const std::string& key) const {
		static const JsonValue empty;
		if (type != Type::Object) return empty;
		auto it = obj.find (key);
		return it == obj.end () ? empty : it->second;
	}
	const JsonValue& operator[] (size_t i) const {
		static const JsonValue empty;
		return (type == Type::Array && i < arr.size ()) ? arr[i] : empty;
	}
	size_t Size () const { return type == Type::Array ? arr.size () : 0; }
	double NumberOr (double d) const { return type == Type::Number ? num : d; }
	long IntOr (long d) const { return type == Type::Number ? static_cast<long> (num) : d; }
	std::string StringOr (const std::string& d) const { return type == Type::String ? str : d; }
};

class JsonParser {
public:
	static JsonValue Parse (const std::string& text) {
		JsonParser p (text);
		p.SkipWs ();
		JsonValue v = p.ParseValue ();
		return v;
	}

private:
	const std::string& s;
	size_t i = 0;
	explicit JsonParser (const std::string& text) : s (text) {}

	[[noreturn]] void Fail (const char* what) { throw std::runtime_error (std::string ("JSON: ") + what); }
	void SkipWs () { while (i < s.size () && (s[i] == ' ' || s[i] == '\n' || s[i] == '\r' || s[i] == '\t')) ++i; }
	bool Consume (char c) { if (i < s.size () && s[i] == c) { ++i; return true; } return false; }

	JsonValue ParseValue () {
		if (i >= s.size ()) Fail ("unerwartetes Ende");
		char c = s[i];
		if (c == '{') return ParseObject ();
		if (c == '[') return ParseArray ();
		if (c == '"') { JsonValue v; v.type = JsonValue::Type::String; v.str = ParseString (); return v; }
		if (s.compare (i, 4, "true") == 0) { i += 4; JsonValue v; v.type = JsonValue::Type::Bool; v.b = true; return v; }
		if (s.compare (i, 5, "false") == 0) { i += 5; JsonValue v; v.type = JsonValue::Type::Bool; v.b = false; return v; }
		if (s.compare (i, 4, "null") == 0) { i += 4; return JsonValue (); }
		return ParseNumber ();
	}

	JsonValue ParseNumber () {
		size_t start = i;
		while (i < s.size () && (isdigit (static_cast<unsigned char> (s[i])) || s[i] == '-' || s[i] == '+' || s[i] == '.' || s[i] == 'e' || s[i] == 'E')) ++i;
		if (start == i) Fail ("Zahl erwartet");
		JsonValue v; v.type = JsonValue::Type::Number; v.num = std::strtod (s.substr (start, i - start).c_str (), nullptr);
		return v;
	}

	static void AppendUtf8 (std::string& out, unsigned cp) {
		if (cp < 0x80) out += static_cast<char> (cp);
		else if (cp < 0x800) { out += static_cast<char> (0xC0 | (cp >> 6)); out += static_cast<char> (0x80 | (cp & 0x3F)); }
		else if (cp < 0x10000) { out += static_cast<char> (0xE0 | (cp >> 12)); out += static_cast<char> (0x80 | ((cp >> 6) & 0x3F)); out += static_cast<char> (0x80 | (cp & 0x3F)); }
		else { out += static_cast<char> (0xF0 | (cp >> 18)); out += static_cast<char> (0x80 | ((cp >> 12) & 0x3F)); out += static_cast<char> (0x80 | ((cp >> 6) & 0x3F)); out += static_cast<char> (0x80 | (cp & 0x3F)); }
	}

	std::string ParseString () {
		if (!Consume ('"')) Fail ("String erwartet");
		std::string out;
		while (i < s.size ()) {
			char c = s[i++];
			if (c == '"') return out;
			if (c != '\\') { out += c; continue; }
			if (i >= s.size ()) Fail ("String endet in Escape");
			char e = s[i++];
			switch (e) {
				case '"': out += '"'; break;
				case '\\': out += '\\'; break;
				case '/': out += '/'; break;
				case 'b': out += '\b'; break;
				case 'f': out += '\f'; break;
				case 'n': out += '\n'; break;
				case 'r': out += '\r'; break;
				case 't': out += '\t'; break;
				case 'u': {
					if (i + 4 > s.size ()) Fail ("\\u unvollständig");
					unsigned cp = static_cast<unsigned> (std::strtoul (s.substr (i, 4).c_str (), nullptr, 16)); i += 4;
					if (cp >= 0xD800 && cp <= 0xDBFF && s.compare (i, 2, "\\u") == 0) {
						unsigned lo = static_cast<unsigned> (std::strtoul (s.substr (i + 2, 4).c_str (), nullptr, 16)); i += 6;
						cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
					}
					AppendUtf8 (out, cp);
					break;
				}
				default: Fail ("unbekanntes Escape");
			}
		}
		Fail ("String nicht beendet");
	}

	JsonValue ParseArray () {
		Consume ('[');
		JsonValue v; v.type = JsonValue::Type::Array;
		SkipWs ();
		if (Consume (']')) return v;
		for (;;) {
			SkipWs ();
			v.arr.push_back (ParseValue ());
			SkipWs ();
			if (Consume (',')) continue;
			if (Consume (']')) return v;
			Fail ("',' oder ']' erwartet");
		}
	}

	JsonValue ParseObject () {
		Consume ('{');
		JsonValue v; v.type = JsonValue::Type::Object;
		SkipWs ();
		if (Consume ('}')) return v;
		for (;;) {
			SkipWs ();
			std::string key = ParseString ();
			SkipWs ();
			if (!Consume (':')) Fail ("':' erwartet");
			SkipWs ();
			v.obj[key] = ParseValue ();
			SkipWs ();
			if (Consume (',')) continue;
			if (Consume ('}')) return v;
			Fail ("',' oder '}' erwartet");
		}
	}
};

} // namespace gisloader
