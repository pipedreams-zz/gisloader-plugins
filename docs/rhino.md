# gisloader für Rhino 8

Das Plugin holt Exporte deines gisloader-Kontos nach Rhino 8 (Windows und
macOS): jede GLB wird importiert, die Objekte landen auf einer Ebene
„gisloader · Ort“, die Georeferenz steht als Dokumenttexte und als
EarthAnchorPoint.

## Benutzung

- Befehl `gisloader` öffnet das Fenster (Versionsnummer im Titel);
  `gisloaderBridge` startet nur die Brücke, etwa beim Rhino-Start.
- E-Mail und Passwort eintragen, „Anmelden“. Die Sitzung bleibt gespeichert;
  ist das Plugin angemeldet, zeigt das Passwortfeld Platzhalter. Beim Öffnen
  prüft das Plugin die Sitzung und lädt die Liste; „Sitzung abgelaufen“ im
  Status heißt neu anmelden.
- Konto: „Alle Konten“ (Vorgabe) zeigt persönliche Exporte und die aller
  Teams, in denen du Mitglied bist, mit Team und Ersteller je Zeile; sonst
  ein einzelnes Konto. So exportiert ein Teammitglied, ein anderes lädt im
  Plugin.
- Zeitraum: diese Woche, dieser Monat (Vorgabe), dieses Jahr, alle.
  „Exporte aktualisieren“ lädt die Liste, „Importieren“ holt den gewählten
  Export in das aktive Dokument.
- Speicherordner (Vorgabe `~/Downloads/gisloader`, „…“ öffnet die Auswahl);
  „Beim Import fragen“ zeigt vor jedem Import einen Ordnerdialog. Jeder
  Export bekommt einen Unterordner `<Ort>_<ID>` mit GLB, Texturen,
  Provenienz und README.
- Brücke: Das Plugin lauscht auf dem ersten freien Port von
  `127.0.0.1:47820` bis 47829. „An Rhino senden“ in der Web-App (Exportpanel
  und Exportliste des Kontos) schickt die Export-ID dorthin; die Web-App
  wartet auf das Ergebnis und zeigt es an. Die Brücke bleibt aktiv, auch wenn
  das Fenster geschlossen ist.
- Werkzeugleiste: Das Paket bringt eine Leiste „gisloader“ mit zwei Knöpfen
  (Fenster, Brücke) und dem gisloader-Symbol mit; sie erscheint nach der
  Installation, sonst über Optionen › Werkzeugleisten › `gisloader.rui`.

### Ebenen

Jeder Export bekommt eine Ebene „gisloader · Ort“. Darunter liegen die Ebenen
des Importers (Nutzung mit Unterebenen, Flurstücke, Bauwerke) und „Gebaeude“
mit je einer Ebene pro Bauteilart (Dach, Wand, Boden, Grundriss); die gml:id
jedes Gebäudes steht als Benutzertext `gml_id` am Objekt.

### Georeferenz

- Rhino ist Z-up und dreht glTF (Y-up) beim Import: X = Ost, Y = Nord,
  Z = Höhe. Die GLB ist in Metern; Rhino rechnet beim Import in die
  Dokumenteinheit um, ein Zentimeter-Dokument bekommt also Faktor 100. Die
  Ursprungswerte in den Dokumenttexten bleiben Meter.
- Ursprung und CRS stehen als Dokumenttexte (`gisloader:crs`,
  `gisloader:origin_x/y/z`, abrufbar mit `_DocumentText`), bei
  UTM-Systemen (EPSG:25832, 25833) zusätzlich als EarthAnchorPoint mit
  Breite und Länge des Ursprungs, Norden = +Y. Damit setzen `_EarthAnchorPoint`
  und Export nach KML/DWG die Weltkoordinaten richtig.
- Objektattribute (gml:id, Höhe, Dachform) landen als Benutzertexte an den
  Objekten; die Quellenangabe steht als Benutzertext `attribution`.

### Texturen

Rhino bettet Bilder aus glTF in das Dokument ein. Die Geländetextur liegt
zusätzlich als JPEG im Exportordner; das Plugin kopiert sie nach `tex/` und
setzt sie als Bitmap-Textur des Materials „terrain“ mit absolutem Pfad. Die
Texturen des photorealistischen Meshes bleiben eingebettet.

### Störungen

- Fehler beim Öffnen des Fensters landen in `~/.gisloader/rhino.log` und in
  der Rhino-Kommandozeile.
- „CERTIFICATE_VERIFY_FAILED“: Das Plugin nutzt certifi (falls vorhanden) und
  die Systemzertifikate; unter Windows liest Python den Zertifikatspeicher.
- Brücke „aus“ trotz Häkchen: alle Ports 47820–47829 belegt oder eine
  Firewall blockiert 127.0.0.1; Häkchen aus- und wieder einschalten.

## Installation

Voraussetzung: Rhino 8 (Python 3). Das Plugin ist ein Rhino-Paket (`.yak`).

1. Paketdatei `gisloader-<version>-rh8-any.yak` von der
   [Plugin-Seite](/plugins) laden (sie liegt auch in der Zip unter `dist/`).
2. Installieren: die `.yak`-Datei in das Rhino-Fenster ziehen, oder
   `_PackageManager` öffnen und die Datei wählen. Rhino neu starten.
3. Befehl `gisloader` eingeben. Für die Brücke ab Start: Optionen › Allgemein ›
   „Befehle beim Start ausführen“ → `_gisloaderBridge`.

Ohne Paket geht es weiterhin als Skript: `_-RunPythonScript` mit
`gisloader-rhino/gisloader/gisloader.py` aus der Zip.

Update: neue `.yak` genauso installieren, Rhino neu starten.
