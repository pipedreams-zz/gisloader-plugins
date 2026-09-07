# gisloader für Cinema 4D 2025/2026

Das Plugin holt Exporte deines gisloader-Kontos nach Cinema 4D: jede GLB
kommt unter ein Null-Objekt „gisloader · Ort“, die Georeferenz (CRS,
Ursprung) steht als User Data an diesem Null.

## Installation

1. Zip laden: auf der [Plugin-Seite](/plugins) der Web-App oder direkt
   `https://<server>/dcc/gisloader-cinema4d.zip`.
2. Entpacken und den Ordner `gisloader` in den Plugin-Ordner legen:
   macOS `~/Library/Preferences/Maxon/Maxon Cinema 4D 2026_<ID>/plugins/`,
   Windows `%APPDATA%\Maxon\Maxon Cinema 4D 2026_<ID>\plugins\`. Alternativ
   in Edit › Preferences › Plugins einen eigenen Pfad eintragen.
3. Cinema 4D neu starten. Menü **Extensions › gisloader**.

Für ein Update den Ordner `gisloader` durch den neuen ersetzen und Cinema 4D
neu starten.

## Benutzung

- Server (Vorgabe `https://gisloader.ampsrvr.xyz`), E-Mail und Passwort
  eintragen, „Anmelden“. Die Sitzung bleibt als Token in
  `gisloader.json` im Prefs-Ordner.
- Zeitraum links neben der Liste: diese Woche, dieser Monat (Vorgabe), dieses
  Jahr, alle. „Exporte aktualisieren“ lädt die Liste, „Importieren“ holt den
  gewählten Export in das aktive Dokument. „gisloader im Browser“ öffnet die
  Web-App.
- Brücke: Das Plugin lauscht auf dem ersten freien Port von `127.0.0.1:47810`
  bis 47819 (Häkchen im Dialog zeigt den Port). Der Knopf „An Cinema 4D
  senden“ in der Web-App schickt die Export-ID dorthin, der Import läuft im
  Hauptthread von Cinema 4D. Blender nutzt den Bereich ab 47800, beide
  Programme laufen nebeneinander.

## Georeferenz

- Cinema 4D und glTF sind Y-up: X = Ost, Y = Höhe, Z = −Nord. Dokumenteinheit
  ist Zentimeter; der glTF-Import rechnet Meter um.
- Weltkoordinate (Meter) = lokale Koordinate / 100 + `origin_x/y/z` im System
  `crs`, dabei gilt Nord = −Z.
- Objektattribute (gml:id, Höhe, Dachform, Flurstückskennzeichen) landen je
  nach Importer-Version als User Data an den Objekten; die Quellenangabe steht
  in `attribution` am Null.

## Störungen

- „CERTIFICATE_VERIFY_FAILED … unable to get local issuer certificate“: Das
  Python in Cinema 4D bringt kein Zertifikatsbündel mit. Ab Version 0.1.1
  nutzt das Plugin certifi (falls vorhanden) und die Systemzertifikate
  (macOS `/etc/ssl/cert.pem`, Linux `ca-certificates`; Windows liest den
  Zertifikatspeicher des Systems). Erscheint der Fehler weiterhin, fehlt auf
  dem Rechner das Systembündel.
- Die Plugin-IDs stammen aus dem Testbereich von Maxon. Für eine Weitergabe
  außerhalb des Hauses eigene IDs unter plugincafe.maxon.net registrieren.
