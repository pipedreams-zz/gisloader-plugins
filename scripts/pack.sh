#!/usr/bin/env bash
# Packt alle Plugins als Zips nach dist/ (gleiche Ordnerstruktur wie die Web-App)
# und schreibt dist/RELEASE.md mit der Version jedes Plugins.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
rm -f dist/*.zip dist/*.yak dist/RELEASE.md
(cd dcc/blender && zip -qr ../../dist/gisloader-blender.zip gisloader_blender -x '*/__pycache__/*')
(cd dcc/cinema4d && zip -qr ../../dist/gisloader-cinema4d.zip gisloader -x '*/__pycache__/*')
(cd dcc && zip -qr ../dist/gisloader-rhino.zip rhino -x '*/__pycache__/*' 'rhino/build/*' 'rhino/gisloader.rhproj')
cp dcc/rhino/dist/*.yak dist/ 2>/dev/null || true
if [ -d dcc/archicad/dist ]; then (cd dcc/archicad/dist && zip -qr ../../../dist/gisloader-archicad.zip .); fi

ver () { grep -oE "$2" "$1" | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "?"; }
BLENDER=$(ver dcc/blender/gisloader_blender/__init__.py 'ADDON_VERSION = "[^"]+"')
C4D=$(ver dcc/cinema4d/gisloader/gisloader_core.py 'VERSION = "[^"]+"')
RHINO=$(ver dcc/rhino/lib/gisloader_rhino/__init__.py 'VERSION = "[^"]+"')
ARCHICAD=$(ver dcc/archicad/Src/Version.hpp 'GISLOADER_ADDON_VERSION "[^"]+"')
cat > dist/RELEASE.md <<EOF
| Plugin | Version | Datei |
| --- | --- | --- |
| Blender | $BLENDER | gisloader-blender.zip |
| Cinema 4D | $C4D | gisloader-cinema4d.zip |
| Rhino 8 | $RHINO | gisloader-rhino.zip, gisloader-$RHINO+*.yak |
| Archicad 28 | $ARCHICAD | gisloader-archicad.zip (macOS-Bundle und Windows-.apx) |

Jedes Plugin zählt seine Version eigenständig; was sich geändert hat, steht in [docs/CHANGELOG.md](docs/CHANGELOG.md). Anleitungen unter docs/.
EOF
ls -l dist
cat dist/RELEASE.md
