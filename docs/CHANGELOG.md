# Versionshistorie der Plugins

Jedes Plugin zählt seine Version eigenständig und wird nur hochgezählt, wenn
sich sein Code ändert. Releases im Plugin-Repo tragen ein Datum und nennen
die enthaltenen Plugin-Versionen; jede Version hat dort den Tag
`<plugin>-v<version>`. Die Zips heißen nach Plugin, Zielprogramm, Version und
Releasedatum, etwa `gisloader_archicad-28_v0.1.15_2026-11-08.zip`.

## 6. November 2026

Alle Plugins verstehen die neue Export-Ebene „ALKIS Detail“ (NRW) und die
Option „2D-Ebenen zusätzlich auf der Nullebene“ (Knoten `Plan_2D`).

- Archicad 0.1.15: Ebenen je Abschnitt („gisloader ALKIS Gebäudedetail“,
  „… Grundstück“ usw.), Flächen als Morphs, Linien als Polylinien, Punkte als
  Hotspots; Grenzpunkte bekommen ihre kurze Punktnummer als Text daneben (die
  volle Punktkennung bleibt Attribut des Exports). Die flache
  Fassung landet auf eigenen Ebenen „gisloader 2D …“: Flächen als Schraffuren
  (Umriss mit Löchern, vollflächig in der Farbe des Abschnitts und mit Kontur;
  Gebäude über Straßen), Linien als Polylinien im Stift ihrer Farbe, Punkte als
  Hotspots. Nach dem Import zoomt der Grundriss auf den Ausschnitt. Bau unter
  Xcode 27 (Zielversion macOS 12).
- Blender 0.1.16: Einzelpunkte (Grenzpunkte, Einzelbäume) werden zu Empties
  mit allen Attributen; Blender zeigte die Punktnetze nur im Bearbeitungsmodus.
  Attribute stehen wie bisher als Eigenschaften am Objekt.
- Rhino 0.1.16: Attribute aus der GLB als Benutzertexte (der glTF-Importer von
  Rhino übernimmt sie nicht), Einzelpunkte als Punkte statt Punktwolken. Behoben:
  die `gml_id` der LoD2-Gebäude kam seit 0.1.11 nicht am Objekt an.
- Cinema 4D 0.1.16: ALKIS Detail und `Plan_2D` als Null-Gruppen nach Abschnitt
  und Objektart, Objekte nach gml:id benannt, Attribute als User Data;
  Punkte (der OBJ-Importer liefert sie leer) als Null-Objekte an der Punktlage.

## 16. September 2026

- Blender, Cinema 4D, Rhino 0.1.15: Filter „Heute“ in der Exportliste;
  „An … senden“ aus der Web-App funktioniert auch, wenn das Plugin mit einem
  anderen Konto angemeldet ist als der Browser (die Web-App schickt ein
  einstündiges Freigabe-Token mit; bisher „HTTP 404: Job unbekannt“). Ohne
  Token nennt die API den Grund („gehört einem anderen Konto, angemeldet als …“).
- Cinema 4D 0.1.15: OBJ-Import ohne Spiegelung (nur Y und Z tauschen; Cinema 4D
  ist linkshändig, „Flip Z“ spiegelte das Modell an der blauen Achse);
  Corona-Materialien bekommen wieder Farbe und Textur (die Parameter-IDs
  20227/20228 waren die Kantenfarbe, richtig sind Base layer › Color 20201 und
  Texture 20202, per c4dpy aus der Beschreibung gelesen).

## 11. September 2026

- Blender, Cinema 4D, Rhino 0.1.14: Kontoauswahl „Alle Konten | Persönlich |
  Team …“ (Exporte aller Teams mit Ersteller je Zeile; die Liste war leer,
  wenn die Exporte auf dem Teamkonto lagen und das Plugin nur das persönliche
  Konto sah), Sitzungsprüfung beim Öffnen mit klarer Meldung statt leerer
  Liste, Rückmeldung der Brücke an die Web-App (Ergebnis des Imports in
  `/ping`), Logo als Symbol (Cinema-4D-Menü, Blender-Panel, Rhino-Werkzeugleiste).
- Cinema 4D 0.1.14: Import über die OBJ des Exports (Materialien aus der
  MTL, Höhenlinien als Splines, Achsen wie glTF), GLB nur noch als Rückfall;
  Corona-Materialien mit festen Parameter-IDs (Base layer › Color/Texture,
  Corona-Bitmap › File), geprüft mit Corona 13; Protokolldatei
  `gisloader.log` und Knopf „Protokoll“; Fehler der Brücke als Dialog.
- Rhino 0.1.14: Werkzeugleiste mit gisloader-Symbolen (hell/dunkel).
- Archicad 0.1.14: Windows-Fassung (`.apx`) ließ sich nicht laden („weder ein
  Add-On noch Veraltetes“), weil der Windows-Ressourcendatei die Einbindung
  der Add-on-Ressourcen (Kennung, Menü, Palette) fehlte; behoben. macOS
  unverändert, nur neue Versionsnummer.

## 8. September 2026

- Archicad 0.1.13: Oberflächen je Materialart mit den Farben des Exports,
  Flurstücksgrenzen und Höhenlinien als Polylinien, Serveradresse über
  Konfigurationsdatei; Windows-Fassung (`.apx`).
- Blender, Cinema 4D, Rhino 0.1.13: nur Versionsnummer, keine Änderung.
- Archicad 0.1.12: erstes Add-on. Palette mit eingebetteter Web-App, Import
  als Morph-Elemente auf Ebenen, Projektstandort und Georeferenz.
- Rhino 0.1.11: Gebäude-Ebenen je Bauteilart (Dach, Wand, Boden, Grundriss)
  statt je Gebäude, gml:id als Benutzertext, Fenster mit Icons und stabilem
  Layout, Passwort-Platzhalter bei bestehender Sitzung.
- Rhino 0.1.10: als Rhino-Paket (`.yak`) mit den Befehlen `gisloader` und
  `gisloaderBridge`. Blender und Cinema 4D 0.1.10: Versionsnummer im Panel
  beziehungsweise Dialogtitel.
- Rhino 0.1.7 bis 0.1.9: neues Plugin. Fenster mit Zeitraumfilter,
  Speicherordner, Georeferenz mit EarthAnchorPoint, Brücke auf 47820 bis
  47829, Fehlerprotokoll, leeres Dokument auf Meter.

## 7. September 2026

- Cinema 4D 0.1.6: optional Corona-Materialien aus den GLB-Materialien.
- Cinema 4D 0.1.5: Node-Materialien (Standard, Redshift) auf Texturdateien
  unter `tex/` umgelegt.
- Cinema 4D 0.1.4: Texturen von der Ramdisk des glTF-Importers als Dateien
  gesichert.
- Blender und Cinema 4D 0.1.2 und 0.1.3: Speicherordner mit Ordnerdialog,
  Texturen als Dateien unter `tex/` absolut verknüpft; Cinema 4D mit eigener
  Plugin-ID für die Brücke.
- Blender und Cinema 4D 0.1.1: Zertifikatsprüfung in Cinema 4D behoben,
  Zeitraumfilter (Woche, Monat, Jahr, alle), getrennte Portbereiche für
  mehrere Instanzen.

## 6. September 2026

- Blender und Cinema 4D 0.1.0: erste Fassung mit Kontoanmeldung, Exportliste,
  Georeferenz und lokaler Brücke für „An … senden“ aus der Web-App.
