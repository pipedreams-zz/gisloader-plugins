# gisloader-Plugins

Plugins für **Blender**, **Cinema 4D 2025/2026** und **Rhino 8**, die fertige Exporte von
[gisloader](https://gisloader.ampsrvr.xyz) direkt ins 3D-Programm holen: mit
Georeferenz (CRS und Ursprung), Ebenen als Collections beziehungsweise
Null-Objekte und einer lokalen Brücke für den Knopf „An Blender senden“ /
„An Cinema 4D senden“ in der Web-App.

## Download

Fertige Zips liegen unter [Releases](../../releases). Die jeweils aktuelle
Fassung gibt es auch auf der [Plugin-Seite](https://gisloader.ampsrvr.xyz/plugins)
der Web-App.

| Plugin    | Ordner         | Voraussetzung                               | Brücke      |
| --------- | -------------- | ------------------------------------------- | ----------- |
| Blender   | `dcc/blender`  | Blender 3.6 oder neuer (Erweiterung ab 4.2) | 47800–47809 |
| Cinema 4D | `dcc/cinema4d` | Cinema 4D 2025 oder 2026                    | 47810–47819 |

## Anleitungen

- [Blender](docs/blender.md)
- [Cinema 4D](docs/cinema4d.md)
- [Rhino](docs/rhino.md)

## Herkunft

Dieses Repository ist ein automatischer Spiegel des Plugin-Teils von
gisloader; Änderungen entstehen dort und werden mit jedem Release hierher
übertragen. Fehler und Wünsche bitte als Issue hier melden.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
