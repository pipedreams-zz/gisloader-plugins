# gisloader für Archicad 28

Natives Add-on (C++, Archicad API DevKit 28). Es bringt die gisloader-Web-App
als andockbare Palette in Archicad; fertige Exporte werden von dort mit
einem Klick als Morph-Elemente auf eigenen Ebenen übernommen, der
Projektstandort bekommt die Georeferenz des Ausschnitts.

## Aufbau

- `dcc/archicad/` ist ein CMake-Projekt nach dem DevKit-Beispiel
  `Browser_Control`: Ressourcen unter `RINT/` (Menü, Palette) und `RFIX/`
  (MDID: Developer-ID 963855185, Local-ID 1830946092), Quellen unter `Src/`.
- Menü **gisloader** mit „gisloader-Palette“ (ein/aus) und „gisloader im
  Browser öffnen“. Die Palette lädt `https://gisloader.ampsrvr.xyz/?embed=archicad`
  in einem eingebetteten Browser und stellt der Seite das Objekt
  `window.gisloaderHost` bereit (`getInfo`, `beginImport`, `setGeoref`,
  `addGlb`, `finishImport`; jede Funktion nimmt einen String).
- Die Web-App erkennt den Host und zeigt unter einem fertigen Export den
  Knopf „In Archicad importieren“. Sie lädt die GLB-Dateien mit ihrer Sitzung,
  übergibt sie als Base64, dazu die Georeferenz (`epsg;ox;oy;oz;lon;lat`).
- Das Add-on liest die GLB selbst (`GlbReader`: Knoten, Transformationen,
  Dreiecksnetze, Linien, Materialnamen und -farben), legt je Netz ein
  Morph-Element an (`ACAPI_Body_*`, rückgängig machbar) und verteilt sie auf
  Ebenen: „gisloader Gelände“, „gisloader Gebäude“, „gisloader Bauwerke“,
  „gisloader Nutzung“, „gisloader Flurstücke“, „gisloader Höhenlinien“,
  „gisloader Bäume“, „gisloader Mesh“.
- Oberflächen: je glTF-Material entsteht eine Archicad-Oberfläche mit der
  Farbe des Exports („gisloader Dach“, „gisloader Wand“, „gisloader Nutzung
  Verkehr“ usw.); texturierte Netze (Gelände, Mesh) bekommen ein Grün-Grau,
  weil Archicad-Oberflächen keine Textur aus der GLB übernehmen. Vorhandene
  Oberflächen gleichen Namens werden wiederverwendet, Farbänderungen im
  Projekt bleiben also erhalten.
- Linien der GLB (Flurstücksgrenzen, Höhenlinien) werden Polylinien im
  Grundriss auf der passenden Ebene.
- Serveradresse: Vorgabe `https://gisloader.ampsrvr.xyz`; abweichend in
  `~/.gisloader/archicad.json` (Windows `%USERPROFILE%\.gisloader\archicad.json`)
  als `{"server": "https://…"}`, setzbar über den JSON-Befehl
  `gisloader.SetServer` (`url`), der die Palette neu lädt.
- Achsen: glTF ist Y-up, Archicad Z-up: X = x, Y = −z, Z = y, Meter.
  Der Projektursprung ist der Ursprung des Exports (Südwest-Ecke).
- Georeferenz: Projektstandort (Länge, Breite, Höhe) und Georeferenzdaten
  (EPSG, Rechts-/Hochwert des Ursprungs) über `ACAPI_GeoLocation_SetGeoLocation`.

## Bauen (macOS)

Voraussetzungen: Xcode, CMake, das DevKit (`AC_API_DEVKIT_DIR`, Vorgabe
`/Users/amp/Documents/coding/rtx.ai/sdk/API.Development.Kit.MAC.28.4001`).

```bash
cd dcc/archicad
cmake -B build -G Xcode
cmake --build build --config Release
```

Ergebnis: `build/Release/gisloader.bundle`. Zum Testen den Ordner nach
`/Applications/Graphisoft/Archicad 28/Add-Ons/` kopieren oder im Add-on-Manager
laden; für die Weitergabe signieren (Developer ID Application) und notarisieren.
Windows-Build (`.apx`) braucht Visual Studio 2019 auf einem Windows-Rechner.

## Bauen (Windows)

Der Workflow `.github/workflows/archicad-windows.yml` baut bei Änderungen unter
`dcc/archicad/` auf einem Windows-Runner: Er lädt das Windows-DevKit 28.4001
aus dem öffentlichen Graphisoft-Release (`GRAPHISOFT/archicad-api-devkit`),
konfiguriert mit Visual Studio 2022 und Toolset v142 (Vorgabe des DevKits für
Archicad 28) und legt `gisloader.apx` als Artefakt ab. Für die Auslieferung
wird die Datei nach `dcc/archicad/dist/win/gisloader.apx` übernommen und mit
dem nächsten Plugin-Tag eingecheckt; die Windows-Ressourcen liegen in
`RFIX.win/gisloader.rc2`. Lokal auf Windows entsprechend:

```bat
cmake -S dcc\archicad -B dcc\archicad\build -G "Visual Studio 17 2022" -A x64 -T v142 -DAC_API_DEVKIT_DIR=C:\Pfad\API.Development.Kit.WIN.28.4001
cmake --build dcc\archicad\build --config Release
```

Installation unter Windows: `gisloader.apx` in den Ordner
`C:\Program Files\Graphisoft\Archicad 28\Add-Ons\` legen (oder über den
Add-On-Manager laden); Protokoll unter `%TEMP%\gisloader-archicad.log`,
Konfiguration in `%USERPROFILE%\.gisloader\archicad.json`.

## Installation

1. Zip laden: auf der [Plugin-Seite](/plugins) oder direkt
   `https://<server>/dcc/gisloader-archicad.zip`; darin `gisloader.bundle`.
2. Bundle nach `/Applications/Graphisoft/Archicad 28/Add-Ons/` kopieren (oder
   im Add-On-Manager hinzufügen) und Archicad starten. Menü **gisloader** →
   „gisloader-Palette“.
3. Das Bundle ist bisher nur ad hoc signiert; auf einem fremden Mac verlangt
   Gatekeeper eine Freigabe (Rechtsklick → Öffnen) oder eine signierte und
   notarisierte Fassung.

## JSON-Befehle

Das Add-on registriert an der Archicad-JSON-Schnittstelle (Port 19723)
`gisloader.ShowPalette` (`action`: show, hide, reload),
`gisloader.SetServer` (`url`: Serveradresse in die Konfigurationsdatei) und
`gisloader.ImportFile`: Import einer GLB vom Dateisystem, mit Name und
Georeferenz. Ein Testbuild (`cmake -DGISLOADER_DEBUG=ON`) hat zusätzlich
`gisloader.DebugExecuteJS`, das JavaScript im eingebetteten Browser ausführt;
im ausgelieferten Bundle fehlt dieser Befehl.

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
Damit lässt sich der Import skripten und testen; die lokale Brücke „An
Archicad senden“ aus dem normalen Browser wird später darauf aufsetzen.

## Stand

- 8. September 2026: Build mit Xcode 26.6 und CMake 4.4 erfolgreich
     (universelles Bundle). Archicad 28 (Build 7006) lädt das Add-on; ein
     Import des Kieler Testexports über den JSON-Befehl legte 254 Morphs auf den
     Ebenen Gelände, Gebäude und Nutzung an, der Projektstandort steht auf
     54,319° N / 10,128° O mit Rechts-/Hochwert des Ursprungs (geprüft über
     Tapir). Maßstab und Achsen stimmen (Gelände 200 m, Dächer bei 25,9 m).
- Ladefehler „weder Add-On noch Veraltetes“: trat auf, solange die Info.plist
  `CFBundleVersion`/`CFBundleShortVersionString` mit „0.1.12“ trug und die
  Ressourcen ohne BOM und mit Umlauten vorlagen; mit `CFBundleVersion` 1.0,
  Kurzversion als Text und BOM/ASCII in den `.grc` lädt Archicad das Bundle.
  Versionsnummer steht in `CFBundleGetInfoString` und `Version.hpp`.
- Das Add-on protokolliert Laden und Fehler unter
  `~/Library/Logs/gisloader-archicad.log`.

- Palette geprüft (8. September 2026): Die Web-App läuft im eingebetteten
  Browser mit `window.gisloaderHost`; Kontoanlage, Export „Aachen, Dom“ (200 m)
  und die Übergabe über die Brücke ergaben 60 Morphs auf vier Ebenen, der
  Projektstandort steht auf 50,774° N / 6,083° O (Test per DebugExecuteJS,
  Prüfung über Tapir).

- Version 0.1.13 (8. September 2026): Oberflächen je Material mit
  Exportfarbe, Flurstücksgrenzen als Polylinien, Serveradresse per
  Konfigurationsdatei. Kiel-Test: 254 Morphs, 78 Polylinien, 5 Ebenen,
  6 Oberflächen (Farben über die JSON-Schnittstelle geprüft).
- Beim Austausch des Bundles muss Archicad beendet sein; ein laufendes
  Archicad hält die alte Fassung im Speicher.

- Windows (8. September 2026): Der CI-Workflow baute `gisloader.apx`
  (PE32+ x64, Exporte `GetExportedFuncAddrs`/`SetImportedFuncAddrs`) ohne
  Anpassungen am Code; Datei unter `dcc/archicad/dist/win/`. Ein Test in
  Archicad 28 unter Windows steht noch aus.

Offen: Test der Windows-Fassung, Element-ID mit gml:id, lokale Brücke,
Signierung/Notarisierung (macOS) bzw. Code-Signatur (Windows).
