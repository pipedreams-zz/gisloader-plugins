#! python 3
"""gisloader für Rhino 8 ohne Plugin: lädt die Bibliothek aus lib/ neben dieser Datei."""
import os
import sys

here = os.path.dirname(__file__.replace("file://", ""))
lib = os.path.join(os.path.dirname(here), "lib")
if lib not in sys.path:
    sys.path.insert(0, lib)

import gisloader_rhino  # noqa: E402

gisloader_rhino.main()
