# gisloader für Rhino 8

Das Skript holt Exporte deines gisloader-Kontos nach Rhino 8 (Windows und
macOS, Python 3): jede GLB wird importiert, die Objekte landen auf einer
Ebene „gisloader · Ort“, die Georeferenz steht als Dokumenttexte und als
EarthAnchorPoint.

## Installation

Das Plugin gibt es als Rhino-Paket (`.yak`) mit den Befehlen `gisloader`
(Fenster öffnen) und `gisloaderBridge` (nur die Brücke starten).

1. Zip laden: auf der [Plugin-Seite](/plugins) der Web-App oder direkt
   `https://<server>/dcc/gisloader-rhino.zip`. Darin liegt unter `dist/` die
   Paketdatei `gisloader-<version>-rh8-any.yak`.
2. Installieren: die `.yak`-Datei in das Rhino-Fenster ziehen, oder
   `_PackageManager` öffnen und die Datei wählen, oder im Terminal
   `"/Applications/Rhino 8.app/Contents/Resources/bin/yak" install <Datei>.yak`
   (Windows: `"C:\Program Files\Rhino 8\System\Yak.exe" install <Datei>.yak`).
   Rhino neu starten.
3. Befehl `gisloader` eingeben. Für die Brücke ab Start: Optionen › Allgemein ›
   „Befehle beim Start ausführen“ → `_gisloaderBridge`.

Ohne Paket geht es weiterhin als Skript: `_-RunPythonScript
"<Pfad>/gisloader-rhino/gisloader/gisloader.py"` (lädt die Bibliothek aus
`lib/` daneben).

Das Paket entsteht aus dem Skriptprojekt `gisloader.rhproj` mit
`rhinocode project build`; dieselbe Datei lässt sich mit `yak push` auf den
McNeel-Paketserver stellen (dann erscheint es im Package Manager) und bei
food4Rhino als App hochladen.

## Benutzung

- Server (Vorgabe `https://gisloader.ampsrvr.xyz`), E-Mail und Passwort
  eintragen, „Anmelden“. Die Sitzung bleibt als Token in
  `~/.gisloader/rhino.json`.
- Zeitraum links neben der Liste: diese Woche, dieser Monat (Vorgabe), dieses
  Jahr, alle. „Exporte aktualisieren“ lädt die Liste, „Importieren“ holt den
  gewählten Export in das aktive Dokument.
- Speicherordner (Vorgabe `~/Downloads/gisloader`, „…“ öffnet die Auswahl);
  „Beim Import fragen“ zeigt vor jedem Import einen Ordnerdialog. Jeder
  Export bekommt einen Unterordner `<Ort>_<ID>` mit GLB, Texturen,
  Provenienz und README.
- Brücke: Das Skript lauscht auf dem ersten freien Port von
  `127.0.0.1:47820` bis 47829. „An Rhino senden“ in der Web-App schickt die
  Export-ID dorthin, der Import läuft im UI-Thread von Rhino; die Brücke
  bleibt aktiv, auch wenn das Fenster geschlossen ist.

## Georeferenz

- Rhino ist Z-up und dreht glTF (Y-up) beim Import: X = Ost, Y = Nord,
  Z = Höhe. Die GLB ist in Metern; Rhino rechnet beim Import in die
  Dokumenteinheit um (in einem Zentimeter-Dokument also Faktor 100, geprüft).
  Die Ursprungswerte in den Dokumenttexten bleiben Meter.
- Ursprung und CRS stehen als Dokumenttexte (`gisloader:crs`,
  `gisloader:origin_x/y/z`, `_DocumentText` oder `_-DocumentText`), bei
  UTM-Systemen (EPSG:25832, 25833) zusätzlich als EarthAnchorPoint mit
  Breite und Länge des Ursprungs, Norden = +Y. Damit setzen `_EarthAnchorPoint`
  und Export nach KML/DWG die Weltkoordinaten richtig.
- Objektattribute (gml:id, Höhe, Dachform) landen je nach Importer als
  Benutzertexte an den Objekten; die Quellenangabe steht als Benutzertext
  `attribution`.

## Texturen

Rhino bettet Bilder aus glTF in das Dokument ein. Die Geländetextur liegt
zusätzlich als JPEG im Exportordner; das Skript kopiert sie nach `tex/` und
setzt sie als Bitmap-Textur des Materials „terrain“ mit absolutem Pfad. Die
Texturen des photorealistischen Meshes bleiben eingebettet.

## Störungen

- Fehler beim Öffnen des Fensters landen in `~/.gisloader/rhino.log` und in
  der Rhino-Kommandozeile.
- „CERTIFICATE_VERIFY_FAILED“: Das Skript nutzt certifi (falls vorhanden) und
  die Systemzertifikate; unter Windows liest Python den Zertifikatspeicher.
- Brücke „aus“ trotz Häkchen: alle Ports 47820–47829 belegt oder eine
  Firewall blockiert 127.0.0.1; Häkchen aus- und wieder einschalten.
