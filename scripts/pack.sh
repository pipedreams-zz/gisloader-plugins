#!/usr/bin/env bash
# Packt beide Plugins als Zips nach dist/ (gleiche Ordnerstruktur wie die Web-App).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
rm -f dist/*.zip
(cd dcc/blender && zip -qr ../../dist/gisloader-blender.zip gisloader_blender -x '*/__pycache__/*')
(cd dcc/cinema4d && zip -qr ../../dist/gisloader-cinema4d.zip gisloader -x '*/__pycache__/*')
(cd dcc/rhino && zip -qr ../../dist/gisloader-rhino.zip gisloader -x '*/__pycache__/*')
ls -l dist
