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
  Dreiecksnetze, Materialnamen), legt je Netz ein Morph-Element an
  (`ACAPI_Body_*`, rückgängig machbar) und verteilt sie auf Ebenen:
  „gisloader Gelände“, „gisloader Gebäude“, „gisloader Nutzung“,
  „gisloader Flurstücke“, „gisloader Mesh“. Die gml:id wird Element-ID.
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

## Stand

Skelett vom 8. September 2026, noch nicht kompiliert (Xcode/CMake fehlten).
Offen: Serveradresse in den Einstellungen, Oberflächen (Materialien) je
Ebenenart statt Standardmaterial, Linien der Flurstücke als Polylinien, lokale
Brücke „An Archicad senden“ aus dem normalen Browser, Windows-Build.
