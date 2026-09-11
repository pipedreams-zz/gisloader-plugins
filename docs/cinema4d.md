# gisloader für Cinema 4D 2025/2026

Das Plugin holt Exporte deines gisloader-Kontos nach Cinema 4D: der Export
kommt unter ein Null-Objekt „gisloader · Ort“, die Georeferenz (CRS,
Ursprung) steht als User Data an diesem Null. Importiert wird die OBJ des
Exports (Materialien aus der MTL, Höhenlinien als Splines); fehlt sie, die GLB.

## Benutzung

- Menü **Extensions › gisloader** öffnet den Dialog; die Versionsnummer steht
  im Titel.
- E-Mail und Passwort eintragen, „Anmelden“. Die Sitzung bleibt gespeichert;
  beim Öffnen prüft das Plugin sie und lädt die Liste. Ist sie abgelaufen,
  steht „Sitzung abgelaufen“ im Status, dann neu anmelden.
- Konto: „Alle Konten“ (Vorgabe) zeigt persönliche Exporte und die aller
  Teams, in denen du Mitglied bist, mit Team und Ersteller je Zeile; sonst
  ein einzelnes Konto. So kann ein Teammitglied exportieren und ein anderes
  den Export im Plugin laden.
- Zeitraum: diese Woche, dieser Monat (Vorgabe), dieses Jahr, alle.
  „Exporte aktualisieren“ lädt die Liste, „Importieren“ holt den gewählten
  Export in das aktive Dokument. „gisloader im Browser“ öffnet die Web-App.
- „Protokoll“ zeigt `gisloader.log` im Prefs-Ordner (Importe, Brücke,
  Fehler); die Datei hilft bei Rückfragen.
- Brücke: Das Plugin lauscht auf dem ersten freien Port von `127.0.0.1:47810`
  bis 47819 (Häkchen im Dialog zeigt den Port). Der Knopf „An Cinema 4D
  senden“ in der Web-App (im Exportpanel und in der Exportliste des Kontos)
  schickt die Export-ID dorthin, der Import läuft im Hauptthread von
  Cinema 4D. Die Web-App wartet auf das Ergebnis und zeigt es an; schlägt der
  Import fehl, meldet Cinema 4D es zusätzlich in einem Dialog. Blender nutzt
  den Bereich ab 47800, Rhino ab 47820, alle laufen nebeneinander.

### OBJ oder GLB

- „Über OBJ importieren“ (Vorgabe an): Das Plugin nimmt die OBJ des Exports
  (Häkchen „OBJ + MTL“ beim Export, seit 0.1.14 vorbelegt). Der OBJ-Importer
  von Cinema 4D bekommt dafür feste Einstellungen: Meter als Einheit,
  Materialien aus der MTL (Farbe `Kd`, Textur `map_Kd` als Bitmap-Shader),
  ein Objekt je Ebene und Gebäudeteil, Höhenlinien und Flurstücksgrenzen als
  Splines. Eine Z-up-OBJ wird beim Import gedreht (Y und Z tauschen), eine
  Y-up-OBJ nicht; das Ergebnis ist in beiden Fällen X = Ost, Y = Höhe,
  Z = −Nord wie bei glTF. Die Importer-Einstellungen werden danach
  zurückgesetzt.
- Ohne OBJ im Export (oder ohne Häkchen) kommt die GLB über den
  glTF-Importer. Eingebettete Texturen liegen dann auf einer Ramdisk des
  Importers, das Plugin sichert sie nach `tex/`; Node-Materialien mit
  Ramdisk-Pfaden sind der Grund, die OBJ zu bevorzugen.

### Speicherordner und Texturen

- Im Dialog steht der Speicherordner (Vorgabe `~/Downloads/gisloader`), „…“
  öffnet die Ordnerwahl. Jeder Export bekommt darin einen Unterordner
  `<Ort>_<ID>` mit GLB, Texturen (JPEG), Provenienz und README.
- „Beim Import fragen“ (Vorgabe an) zeigt vor jedem Import, auch über die
  Brücke, einen Ordnerdialog, vorbelegt mit dem Speicherordner; Abbrechen
  bricht den Import ab. Ohne Häkchen landet alles direkt im Speicherordner.
- Nach dem Import werden die Bitmap-Shader der neuen Materialien auf absolute
  Pfade unter `tex/` im Exportordner gesetzt. Eingebettete Texturen legt der
  glTF-Importer auf einer virtuellen Ramdisk ab; das Plugin speichert sie von
  dort als Datei nach `tex/`. Das gilt für klassische Bitmap-Shader und für
  Node-Materialien (Standard- und Redshift-Node-Space). Der Ordner steht als
  User Data `gisloader_folder` am Null-Objekt.

### Corona Renderer

Ist Corona installiert, lässt sich im Dialog „Corona-Materialien erzeugen“
einschalten. Nach dem Import legt das Plugin je importiertem Material ein
Corona Physical Material an (Basisschicht: Farbe aus dem Farbkanal des
Standardmaterials, Textur aus `tex/` im Corona-Bitmap-Shader; bei GLB-Import
Farbe aus dem glTF-Material), hängt die Texture-Tags um und entfernt die vom
Importer erzeugten Materialien. Geprüft mit Corona 13 in Cinema 4D 2026
(Parameter Base layer › Color/Texture, Bitmap-Shader › File); was das Plugin
je Material gefunden hat, steht im Protokoll.

### Georeferenz

- Cinema 4D und glTF sind Y-up: X = Ost, Y = Höhe, Z = −Nord. Dokumenteinheit
  ist Zentimeter; der glTF-Import rechnet Meter um.
- Weltkoordinate (Meter) = lokale Koordinate / 100 + `origin_x/y/z` im System
  `crs`, dabei gilt Nord = −Z.
- Objektattribute (gml:id, Höhe, Dachform, Flurstückskennzeichen) landen bei
  GLB-Import als User Data an den Objekten; bei OBJ-Import steht die gml:id im
  Objektnamen (`Gebaeude_<gml:id>_Wand`). Die Quellenangabe steht in
  `attribution` am Null, die Importquelle in `gisloader_source`.

### Störungen

- „CERTIFICATE_VERIFY_FAILED … unable to get local issuer certificate“: Das
  Python in Cinema 4D bringt kein Zertifikatsbündel mit. Das Plugin nutzt
  certifi (falls vorhanden) und die Systemzertifikate. Erscheint der Fehler
  weiterhin, fehlt auf dem Rechner das Systembündel.
- Corona-Materialien ohne Farbe oder Textur: `gisloader.log` (Knopf
  „Protokoll“) nennt je Material Farbe und Texturdatei; fehlt die Textur,
  liegt sie nicht unter `tex/` (Export ohne OBJ, Textur nicht sicherbar).
- Brücke: „An Cinema 4D senden“ in der Web-App meldet das Ergebnis des
  Imports. Kommt nichts an, im Dialog prüfen, ob die Brücke läuft (Häkchen
  mit Port), ob der Server im Plugin der Web-App entspricht, und ins
  Protokoll schauen.

## Installation

Voraussetzung: Cinema 4D 2025 oder 2026.

1. Zip von der [Plugin-Seite](/plugins) laden.
2. Entpacken und den Ordner `gisloader` in den Plugin-Ordner legen:
   macOS `~/Library/Preferences/Maxon/Maxon Cinema 4D 2026_<ID>/plugins/`,
   Windows `%APPDATA%\Maxon\Maxon Cinema 4D 2026_<ID>\plugins\`. Alternativ
   in Edit › Preferences › Plugins einen eigenen Pfad eintragen.
3. Cinema 4D neu starten. Menü **Extensions › gisloader** (mit dem
   gisloader-Symbol, auch für Paletten).

Update: den Ordner `gisloader` durch den neuen ersetzen und Cinema 4D neu
starten.
