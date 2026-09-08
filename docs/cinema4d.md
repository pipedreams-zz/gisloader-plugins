# gisloader für Cinema 4D 2025/2026

Das Plugin holt Exporte deines gisloader-Kontos nach Cinema 4D: jede GLB
kommt unter ein Null-Objekt „gisloader · Ort“, die Georeferenz (CRS,
Ursprung) steht als User Data an diesem Null.

## Benutzung

- Menü **Extensions › gisloader** öffnet den Dialog; die Versionsnummer steht
  im Titel.
- E-Mail und Passwort eintragen, „Anmelden“. Die Sitzung bleibt gespeichert.
- Zeitraum links neben der Liste: diese Woche, dieser Monat (Vorgabe), dieses
  Jahr, alle. „Exporte aktualisieren“ lädt die Liste, „Importieren“ holt den
  gewählten Export in das aktive Dokument. „gisloader im Browser“ öffnet die
  Web-App.
- Brücke: Das Plugin lauscht auf dem ersten freien Port von `127.0.0.1:47810`
  bis 47819 (Häkchen im Dialog zeigt den Port). Der Knopf „An Cinema 4D
  senden“ in der Web-App schickt die Export-ID dorthin, der Import läuft im
  Hauptthread von Cinema 4D. Blender nutzt den Bereich ab 47800, beide
  Programme laufen nebeneinander.

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
einschalten. Nach dem Import legt das Plugin je Material der GLB ein Corona
Physical Material an (Grundfarbe aus dem glTF-Material, Textur aus `tex/`
im Corona-Bitmap-Shader), hängt die Texture-Tags um und entfernt die vom
Importer erzeugten Materialien.

### Georeferenz

- Cinema 4D und glTF sind Y-up: X = Ost, Y = Höhe, Z = −Nord. Dokumenteinheit
  ist Zentimeter; der glTF-Import rechnet Meter um.
- Weltkoordinate (Meter) = lokale Koordinate / 100 + `origin_x/y/z` im System
  `crs`, dabei gilt Nord = −Z.
- Objektattribute (gml:id, Höhe, Dachform, Flurstückskennzeichen) landen als
  User Data an den Objekten; die Quellenangabe steht in `attribution` am Null.

### Störungen

- „CERTIFICATE_VERIFY_FAILED … unable to get local issuer certificate“: Das
  Python in Cinema 4D bringt kein Zertifikatsbündel mit. Das Plugin nutzt
  certifi (falls vorhanden) und die Systemzertifikate. Erscheint der Fehler
  weiterhin, fehlt auf dem Rechner das Systembündel.
- Findet das Plugin bei Corona keinen Textur-Slot, steht in der
  Python-Konsole die Liste der Kandidaten.

## Installation

Voraussetzung: Cinema 4D 2025 oder 2026.

1. Zip von der [Plugin-Seite](/plugins) laden.
2. Entpacken und den Ordner `gisloader` in den Plugin-Ordner legen:
   macOS `~/Library/Preferences/Maxon/Maxon Cinema 4D 2026_<ID>/plugins/`,
   Windows `%APPDATA%\Maxon\Maxon Cinema 4D 2026_<ID>\plugins\`. Alternativ
   in Edit › Preferences › Plugins einen eigenen Pfad eintragen.
3. Cinema 4D neu starten. Menü **Extensions › gisloader**.

Update: den Ordner `gisloader` durch den neuen ersetzen und Cinema 4D neu
starten.
