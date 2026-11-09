#!/usr/bin/env bash
# Packt alle Plugins als Zips nach dist/ (gleiche Ordnerstruktur wie die Web-App)
# und schreibt dist/RELEASE.md mit der Version jedes Plugins.
# Dateiname: gisloader_<plugin>-<zielprogramm>_v<version>_<releasedatum>.zip,
# Zielprogramm und Releasedatum aus dcc/release.json.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
rm -f dist/*.zip dist/*.yak dist/RELEASE.md

# shellcheck source=versions.sh
source scripts/versions.sh
DATE=$(python3 -c 'import json; print(json.load(open("dcc/release.json"))["date"])')
target () { python3 -c 'import json,sys; print(json.load(open("dcc/release.json"))["plugins"][sys.argv[1]]["target"])' "$1"; }
name () { echo "gisloader_$1-$(target "$1")_v$2_${DATE}.zip"; }

BLENDER=$(plugin_version - blender)
C4D=$(plugin_version - cinema4d)
RHINO=$(plugin_version - rhino)
ARCHICAD=$(plugin_version - archicad)
F_BLENDER=$(name blender "$BLENDER")
F_C4D=$(name cinema4d "$C4D")
F_RHINO=$(name rhino "$RHINO")
F_ARCHICAD=$(name archicad "$ARCHICAD")

(cd dcc/blender && zip -qr "../../dist/$F_BLENDER" gisloader_blender -x '*/__pycache__/*')
(cd dcc/cinema4d && zip -qr "../../dist/$F_C4D" gisloader -x '*/__pycache__/*')
(cd dcc && zip -qr "../dist/$F_RHINO" rhino -x '*/__pycache__/*' 'rhino/build/*' 'rhino/gisloader.rhproj')
cp dcc/rhino/dist/*.yak dist/ 2>/dev/null || true
if [ -d dcc/archicad/dist ]; then (cd dcc/archicad/dist && zip -qr "../../../dist/$F_ARCHICAD" .); fi

cat > dist/RELEASE.md <<EOF
Release vom ${DATE}.

| Plugin | Version | Tag | Datei |
| --- | --- | --- | --- |
| Blender | $BLENDER | blender-v$BLENDER | $F_BLENDER |
| Cinema 4D | $C4D | cinema4d-v$C4D | $F_C4D |
| Rhino 8 | $RHINO | rhino-v$RHINO | $F_RHINO, gisloader-$RHINO+*.yak |
| Archicad 28 | $ARCHICAD | archicad-v$ARCHICAD | $F_ARCHICAD (macOS-Bundle und Windows-.apx) |

Jedes Plugin zählt seine Version eigenständig; der Tag \`<plugin>-v<version>\` zeigt auf das erste Release mit dieser Version. Was sich geändert hat, steht in [docs/CHANGELOG.md](docs/CHANGELOG.md). Anleitungen unter docs/.
EOF
ls -l dist
cat dist/RELEASE.md
