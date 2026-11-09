# Version eines Plugins aus seinen Quellen lesen (wird von pack.sh und dem
# Release-Workflow eingebunden). Aufruf: plugin_version <git-ref|-> <plugin>;
# "-" liest die Arbeitskopie. Gibt nichts aus, wenn die Datei oder Version fehlt.
PLUGIN_IDS="blender cinema4d rhino archicad"

plugin_version () {
  local ref="$1" id="$2" file pattern
  case "$id" in
    blender)  file=dcc/blender/gisloader_blender/__init__.py; pattern='ADDON_VERSION = "[^"]+"' ;;
    cinema4d) file=dcc/cinema4d/gisloader/gisloader_core.py; pattern='VERSION = "[^"]+"' ;;
    rhino)    file=dcc/rhino/lib/gisloader_rhino/__init__.py; pattern='VERSION = "[^"]+"' ;;
    archicad) file=dcc/archicad/Src/Version.hpp; pattern='GISLOADER_ADDON_VERSION "[^"]+"' ;;
    *) return 0 ;;
  esac
  if [ "$ref" = "-" ]; then cat "$file" 2>/dev/null; else git show "$ref:$file" 2>/dev/null; fi \
    | grep -oE "$pattern" | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true
}
