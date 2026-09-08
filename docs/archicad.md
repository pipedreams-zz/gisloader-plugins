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
`gisloader.ShowPalette` (`action`: show, hide, reload) und
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

Antwort: `{"ok": true, "message": "254 Morph(s) angelegt, 0 übersprungen, Ebenen: 3"}`.
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

Offen: Serveradresse in den Einstellungen, Oberflächen je Ebenenart statt Standardmaterial, Flurstücke als
Polylinien, Element-ID mit gml:id, lokale Brücke, Signierung/Notarisierung,
Windows-Build.
