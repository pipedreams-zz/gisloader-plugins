# Versionshistorie der Plugins

Jedes Plugin zählt seine Version eigenständig und wird nur hochgezählt, wenn
sich sein Code ändert. Releases im Plugin-Repo tragen ein Datum und nennen
die enthaltenen Plugin-Versionen.

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
