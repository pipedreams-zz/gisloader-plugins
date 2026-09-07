# gisloader für Blender

Das Add-on holt Exporte deines gisloader-Kontos direkt nach Blender: jede
Datei wird als eigene Collection importiert, die Georeferenz (CRS, Ursprung)
hängt als Custom Properties an der Collection und, falls noch keine gesetzt
ist, an der Szene in der Form von BlenderGIS (`crs`, `crsx`, `crsy`).

## Installation

1. Zip laden: auf der [Plugin-Seite](/plugins) der Web-App oder direkt
   `https://<server>/dcc/gisloader-blender.zip`.
2. Blender 4.2 und neuer: Einstellungen › Add-ons › Pfeil oben rechts ›
   „Install from Disk…“, Zip wählen. Blender 3.6 bis 4.1: Einstellungen ›
   Add-ons › „Install…“. Danach das Häkchen bei „gisloader“ setzen.
3. In den Einstellungen des Add-ons Server (Vorgabe `https://gisloader.ampsrvr.xyz`)
   und E-Mail eintragen, „Anmelden“ klicken und das Passwort eingeben. Die
   Sitzung bleibt als Token in den Einstellungen gespeichert.

Ein Update installierst du genauso über die neue Zip; Blender ersetzt die
alte Fassung. Danach Blender neu starten, damit die Brücke sauber neu bindet.

## Benutzung

- 3D-Ansicht › Seitenleiste (N) › Reiter „gisloader“: „Exporte aktualisieren“
  lädt die Liste des Kontos, „Importieren“ holt den markierten Export.
- Zeitraum über der Liste: diese Woche, dieser Monat (Vorgabe), dieses Jahr,
  alle. Der Filter wirkt sofort, ohne neuen Abruf.
- Knopf „An Blender senden“ in der Web-App: Das Add-on lauscht auf
  `127.0.0.1:47800` (Brücke, in den Einstellungen abschaltbar). Die Web-App
  schickt die Export-ID dorthin, Blender lädt die Dateien mit dem eigenen
  Token und importiert sie. Der Export muss dem angemeldeten Konto gehören
  oder anonym sein.
- Mehrere Blender-Instanzen (etwa 5.1 und 5.2 nebeneinander) nehmen je den
  nächsten freien Port von 47800 bis 47809; das Panel zeigt den tatsächlichen
  Port, die Web-App bietet je Instanz einen eigenen Knopf mit Versionsnummer.
- „gisloader im Browser“ öffnet die Web-App mit dem eingestellten Server.

## Speicherordner und Texturen

- In den Add-on-Einstellungen steht der Speicherordner (Vorgabe
  `~/Downloads/gisloader`). Jeder Export bekommt darin einen Unterordner
  `<Ort>_<ID>` mit GLB, Texturen (JPEG), Provenienz und README.
- „Beim Import nach dem Ordner fragen“ (Vorgabe an) öffnet vor jedem Import,
  auch über die Brücke, einen Ordnerdialog, vorbelegt mit dem Speicherordner.
  Ohne Häkchen landet alles direkt im Speicherordner. Lässt sich der Ordner
  nicht anlegen, weicht das Add-on auf `~/Downloads/gisloader` aus.
- Eingebettete Texturen der GLB werden nach dem Import als Dateien unter
  `tex/` im Exportordner abgelegt und absolut verknüpft, damit sie beim
  Speichern der Blend-Datei und in Renderfarmen als Dateien vorliegen; der
  Pfad steht auch in `gisloader_folder` an der Collection.

## Georeferenz

- GLB ist Y-up, Blender dreht beim Import nach Z-up: X = Ost, Y = Nord, Z = Höhe.
- Koordinaten sind um den Ursprung verschoben (Südwest-Ecke des Ausschnitts,
  tiefster Punkt). Weltkoordinate = lokale Koordinate + `origin_x/y/z` im
  System `crs` (z. B. `EPSG:25832`).
- Attribute der Objekte (gml:id, Höhe, Dachform, Flurstückskennzeichen) kommen
  als Custom Properties mit, die Quellenangabe steht in `attribution`.

## Störungen

- „CERTIFICATE_VERIFY_FAILED“: Das Add-on prüft das Serverzertifikat mit dem
  certifi-Bündel von Blender und den Systemzertifikaten (macOS
  `/etc/ssl/cert.pem`). Fehlt beides, hilft ein Blender-Update.
- Brücke „aus“ trotz Häkchen: alle Ports 47800–47809 belegt oder eine
  Firewall blockiert 127.0.0.1. „Brücke neu starten“ im Panel versucht es
  erneut.
