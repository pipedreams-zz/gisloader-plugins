# gisloader für Archicad 28

Das Add-on bringt die gisloader-Web-App als Palette in Archicad. Fertige
Exporte übernimmst du von dort mit einem Klick als Morph-Elemente auf eigenen
Ebenen, mit passenden Oberflächen; der Projektstandort bekommt die
Georeferenz des Ausschnitts.

## Benutzung

- Menü **gisloader › gisloader-Palette** öffnet die Palette mit der Web-App.
  Dort meldest du dich mit deinem gisloader-Konto an, wählst den Ausschnitt
  und startest den Export wie im Browser. Die Palette lässt sich andocken.
- Unter einem fertigen Export erscheint „In Archicad importieren“. Archicad
  lädt die Dateien und legt die Elemente im aktiven Geschoss an; der Import
  lässt sich mit Rückgängig zurücknehmen.
- **gisloader im Browser öffnen** startet die Web-App im Standardbrowser,
  etwa für Konto und Abrechnung.

### Was entsteht

- Je Netz des Exports ein Morph-Element. Ebenen: „gisloader Gelände“,
  „gisloader Gebäude“, „gisloader Bauwerke“, „gisloader Nutzung“,
  „gisloader Flurstücke“, „gisloader Höhenlinien“, „gisloader Bäume“,
  „gisloader Mesh“.
- Oberflächen je Materialart mit der Farbe des Exports: „gisloader Dach“,
  „gisloader Wand“, „gisloader Boden“, „gisloader Nutzung Verkehr“ usw.
  Gelände und photorealistisches Mesh bekommen ein Grün-Grau, weil
  Archicad-Oberflächen die Luftbildtextur nicht übernehmen. Bestehende
  Oberflächen gleichen Namens bleiben unverändert, eigene Farbanpassungen
  gehen bei weiteren Importen also nicht verloren.
- Flurstücksgrenzen und Höhenlinien als Polylinien im Grundriss.
- „ALKIS Detail“ (NRW) auf je einer Ebene pro Abschnitt, etwa „gisloader ALKIS
  Gebäudedetail“ oder „gisloader ALKIS Grundstück“: Flächen als Morphs, Linien
  als Polylinien, Punkte (Grenzpunkte, Einzelbäume) als Hotspots auf
  Geländehöhe. Grenzpunkte tragen ihre Punktnummer als Text daneben: nur die
  letzten fünf Stellen der Punktkennung ohne führende Nullen (aus
  322945628227552 wird 27552). Die volle 15-stellige Punktkennung steht im
  Export (Attribut `punktkennung` in der GLB); Hotspots haben in Archicad keine
  Element-ID, die sie aufnehmen könnte.
- Mit der Export-Option „2D-Ebenen zusätzlich auf der Nullebene“ kommt eine
  flache Fassung auf eigene Ebenen „gisloader 2D …“: Flächen als Schraffuren
  mit ihren Löchern, Linien als Polylinien, Punkte als Hotspots auf Höhe 0.
  So lässt sich der Lageplan getrennt vom Geländemodell ein- und ausblenden.
  Die Schraffuren sind vollflächig in der aufgehellten Farbe ihres Abschnitts
  gefüllt und haben eine Kontur im Stift, der der dunkleren Farbe am nächsten
  kommt: Gebäude kräftig, Straßenraum hell, Vegetation grün; Rechte bleiben
  ungefüllt, damit sie nichts verdecken. Gebäude liegen über Straßen und
  Vegetation. Linien bekommen den Stift ihrer Farbe.
- Nach dem Import zoomt der Grundriss auf den Ausschnitt.

### Georeferenz

- Der Projektursprung liegt auf dem Ursprung des Exports (Südwest-Ecke,
  tiefster Punkt). X = Ost, Y = Nord, Z = Höhe, in Metern.
- Projektstandort (Länge, Breite, Höhe) und Georeferenzdaten (Koordinatensystem,
  Rechts- und Hochwert des Ursprungs) werden gesetzt; sie stehen unter
  Optionen › Projekteinstellungen › Standort.

### Hinweise

- Eine abweichende Serveradresse steht in `~/.gisloader/archicad.json`
  (Windows `%USERPROFILE%\.gisloader\archicad.json`) als
  `{"server": "https://…"}`; Vorgabe ist die gisloader-Web-App.
- Meldungen des Add-ons landen in `~/Library/Logs/gisloader-archicad.log`
  (Windows `%TEMP%\gisloader-archicad.log`).
- Für Skripte gibt es JSON-Befehle an der Archicad-Schnittstelle; siehe die
  Entwicklerhinweise im Quellordner des Add-ons.

## Installation

Voraussetzung: Archicad 28 (macOS universell, Windows x64). Die Zip enthält
`gisloader.bundle` für macOS und `win/gisloader.apx` für Windows.

1. Zip von der [Plugin-Seite](/plugins) laden und entpacken.
2. macOS: `gisloader.bundle` nach
   `/Applications/Graphisoft/Archicad 28/Add-Ons/` kopieren. Windows:
   `gisloader.apx` nach `C:\Program Files\Graphisoft\Archicad 28\Add-Ons\`.
   Alternativ in Archicad unter Optionen › Add-On-Manager hinzufügen.
3. Archicad starten. Menü **gisloader › gisloader-Palette**.

Das macOS-Bundle ist bisher nicht notarisiert; verlangt Gatekeeper eine
Freigabe, hilft Rechtsklick › Öffnen. Update: Archicad beenden, Datei
ersetzen, Archicad starten.
