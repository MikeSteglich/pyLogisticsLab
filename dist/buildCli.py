#!/usr/bin/env python3
#
# Baut das Kommandozeilen-Tool logisticslab (logisticsLabCli) mit Nuitka zu einer
# eigenstaendigen Distribution ohne Python - siehe buildStdio.py, das auch dieses
# Programm baut.
#
# Ergebnis: dist/build/<os>-<arch>/logisticslab-cli/      (nicht logisticslab/ - siehe PROGRAMS)
#             logisticslab[.bat]   Startskript
#             README.md, confs/, examples/
#             bin/                 das Programm logisticslab[.exe], Bibliotheken, CMPL-Modelle, cmpl/
#
# Aufruf:  python3 dist/buildCli.py [Optionen]      (Optionen: --help)
#          z.B. /opt/anaconda3/envs/nuitka/bin/python dist/buildCli.py

import buildStdio

if __name__ == "__main__":
    buildStdio.run_main("cli")
