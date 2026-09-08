// Protokoll für die Fehlersuche: ~/Library/Logs/gisloader-archicad.log (macOS) bzw. %TEMP% (Windows).
#pragma once

#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <string>

#include "Version.hpp"

inline void GisloaderLog (const std::string& line)
{
#if defined (macintosh)
	const char* home = std::getenv ("HOME");
	const std::string path = std::string (home ? home : "/tmp") + "/Library/Logs/gisloader-archicad.log";
#else
	const char* tmp = std::getenv ("TEMP");
	const std::string path = std::string (tmp ? tmp : ".") + "\\gisloader-archicad.log";
#endif
	if (FILE* f = std::fopen (path.c_str (), "a")) {
		std::time_t now = std::time (nullptr);
		char stamp[32];
		std::strftime (stamp, sizeof stamp, "%Y-%m-%d %H:%M:%S", std::localtime (&now));
		std::fprintf (f, "%s [gisloader %s] %s\n", stamp, GISLOADER_ADDON_VERSION, line.c_str ());
		std::fclose (f);
	}
}
