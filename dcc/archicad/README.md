# gisloader-Add-on für Archicad 28 (Entwicklerhinweise)

Natives Add-on (C++, Archicad API DevKit 28). Die Benutzeranleitung steht in
`docs/dcc/archicad.md`; hier stehen Aufbau, Build und Schnittstellen.

## Aufbau

- CMake-Projekt nach dem DevKit-Beispiel `Browser_Control`: Ressourcen unter
  `RINT/` (Menü, Palette), `RFIX/` (MDID), `RFIX.mac/` (Info.plist) und
  `RFIX.win/` (Windows-Ressource); Quellen unter `Src/`.
- `GisloaderPalette`: DG-Palette mit eingebettetem Browser, lädt die Web-App
  mit `?embed=archicad` und stellt der Seite `window.gisloaderHost` bereit
  (`getInfo`, `log`, `beginImport`, `setGeoref`, `addGlb`, `finishImport`;
  jede Funktion nimmt einen String). Die Web-App zeigt im Embed-Modus den
  Knopf „In Archicad importieren“, lädt die GLB mit ihrer Sitzung und
  übergibt sie als Base64 samt Georeferenz (`epsg;ox;oy;oz;lon;lat`).
- `GlbReader`: Knoten, Transformationen, Dreiecksnetze, Linien (LINES,
  LINE_STRIP), Materialnamen, Farbfaktor und Texturkennzeichen.
- `Importer`: Morph je Netz (`ACAPI_Body_*`, in `ACAPI_CallUndoableCommand`),
  Ebenen und Oberflächen (`API_MaterialID`) nach Materialname mit den
  Farben des Exports (Anzeigefarben, keine Linear-Umrechnung; texturierte
  Netze Grün-Grau), Polylinien (`API_PolyLineID`) aus Linien, Georeferenz
  über `ACAPI_GeoLocation_SetGeoLocation`. Achsen: X = x, Y = −z, Z = y.
- Serveradresse: `GisloaderServerUrl()` liest `~/.gisloader/archicad.json`
  (`{"server": …}`), sonst `GISLOADER_DEFAULT_SERVER`.
- Protokoll: `~/Library/Logs/gisloader-archicad.log` bzw. `%TEMP%`.

## Bauen

macOS (Xcode, CMake, DevKit über `AC_API_DEVKIT_DIR`):

```bash
cd dcc/archicad
cmake -B build -G Xcode -DAC_API_DEVKIT_DIR=/Pfad/API.Development.Kit.MAC.28.4001
cmake --build build --config Release
```

Ergebnis `build/Release/gisloader.bundle` (universell). Ein Testbuild mit
`-DGISLOADER_DEBUG=ON` hat zusätzlich den JSON-Befehl `gisloader.DebugExecuteJS`
(JavaScript in der Palette ausführen); er fehlt im ausgelieferten Bundle.

Windows: der Workflow `.github/workflows/archicad-windows.yml` lädt das
Windows-DevKit 28.4001 aus dem öffentlichen Graphisoft-Release
(`GRAPHISOFT/archicad-api-devkit`), baut mit Visual Studio 2022 und Toolset
v142 und legt `gisloader.apx` als Artefakt ab. Lokal:

```bat
cmake -S dcc\archicad -B dcc\archicad\build -G "Visual Studio 17 2022" -A x64 -T v142 -DAC_API_DEVKIT_DIR=C:\Pfad\API.Development.Kit.WIN.28.4001
cmake --build dcc\archicad\build --config Release
```

Auslieferung: Bundle nach `dist/gisloader.bundle`, `.apx` nach
`dist/win/gisloader.apx` kopieren und einchecken; die Web-App packt `dist/`
als `gisloader-archicad.zip`. Beim Austausch des Bundles muss Archicad
beendet sein, ein laufendes Archicad hält die alte Fassung im Speicher.

Stolpersteine: Archicad meldet „weder Add-On noch Veraltetes“, wenn die
Info.plist andere Werte als `CFBundleVersion` 1.0 und eine Kurzversion als
Text trägt oder die `.grc` ohne BOM/ASCII vorliegen. Die Versionsnummer steht
in `Src/Version.hpp` und `CFBundleGetInfoString`.

## JSON-Befehle

An der Archicad-JSON-Schnittstelle (Port 19723, nur mit offenem Projekt):

- `gisloader.ShowPalette` (`action`: show, hide, reload)
- `gisloader.SetServer` (`url`): schreibt die Konfigurationsdatei und lädt
  die Palette neu
- `gisloader.ImportFile` (`path`, `name`, `georef`): Import einer GLB vom
  Dateisystem

```bash
curl -s -X POST http://127.0.0.1:19723 -H 'content-type: application/json' -d '{
  "command": "API.ExecuteAddOnCommand",
  "parameters": {
    "addOnCommandId": { "commandNamespace": "gisloader", "commandName": "ImportFile" },
    "addOnCommandParameters": {
      "path": "/pfad/zum/export_model.glb",
      "name": "Kiel, Rathausplatz",
      "georef": "25832;573400;6019615;7;10.1284;54.3191"
    }
  }
}'
```

Antwort: `{"ok": true, "message": "254 Morph(s), 78 Polylinie(n) angelegt, 0 übersprungen, Ebenen: 5, Oberflächen: 6"}`.

## Stand

- 11. September 2026, 0.1.14: Windows-`.apx` war kein gültiges Add-on („weder ein
      Add-On noch Veraltetes“): `RFIX.win/gisloader.rc2` band die aus den `.grc`
      erzeugten `gisloader.grc.rc2`/`gisloaderFix.grc.rc2` nicht ein, die `.apx`
      enthielt nur Icon und Manifest, kein `MDID`. Jetzt wie im DevKit-Beispiel per
      `#include`; Prüfung: die `.rsrc`-Sektion der `.apx` muss benannte
      Ressourcentypen (`MDID`, `GDLG`, `STR#` …) enthalten, nicht nur Typ 3/14/24.
      Mac-Bundle nur mit neuer Versionsnummer.
- 8. September 2026, 0.1.13: Mac-Build mit Xcode 26.6 und CMake 4.4;
     Kiel-Test 254 Morphs, 78 Polylinien, 5 Ebenen, 6 Oberflächen; Palette und
     Import aus der Web-App geprüft (Aachen, Dom: 60 Morphs, Standort
     50,774° N / 6,083° O). Windows-`.apx` aus dem CI-Build, Test in Archicad
     unter Windows offen.
- Offen: Element-ID mit gml:id, lokale Brücke aus dem normalen Browser,
  Signierung/Notarisierung (macOS), Code-Signatur (Windows).
