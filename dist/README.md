# LogisticsLab-Distribution bauen

`buildDist.py` baut eine Distribution, die ohne Installation läuft: Python, alle Bibliotheken, LogisticsLab, CMPL und HiGHS in einem Verzeichnis.

```bash
python3 dist/buildDist.py                      # Distribution für dieses System
python3 dist/buildDist.py --clean              # CMPL-Kern neu bauen
python3 dist/buildDist.py --help
```

Ergebnis: `dist/out/LogisticsLab-<version>-<os>-<arch>.zip` (Linux: `.tar.gz`, macOS mit `--dmg`/`--notarize` zusätzlich `.dmg`). Ausgepackt liegt sie unter `dist/build/<os>-<arch>/LogisticsLab/`:

```
LogisticsLab/
  logisticslab, logisticslab-stdio, logisticslab-server, logisticslab-keys   (Windows: .bat)
  README.md, confs/, examples/
  bin/   python/, pyLogisticsLab/, logisticsLabCore/, logisticsLabCli/, osm_data/, logisticsLabServer/, cmpl/
```

In `bin/` ist das Layout wie im Repository. pyLogisticsLab findet CMPL dort unter `bin/cmpl`. Die Startskripte setzen `LOGLAB_CONF_DIR` auf `confs/` neben sich, wenn die Variable noch nicht gesetzt ist.

## Ablauf

1. **Python:** Das Tool lädt [python-build-standalone](https://github.com/astral-sh/python-build-standalone) (Default: 3.14.8, Release `20261013`) und speichert es in `dist/cache/` zwischen.
2. **Abhängigkeiten:** Die Pakete aus `pyproject.toml` kommen als fertige Wheels hinein (`--only-binary`), einschließlich des Extras `server` (`fastapi`, `uvicorn`, ohne `httpx`). pyCmpl kommt aus der Zeile in `requirements.txt` oder mit `--pycmpl ../pyCmpl` aus dem lokalen Repository. `xlwings` ist nicht dabei.
3. **LogisticsLab:** Die Pakete `pyLogisticsLab`, `logisticsLabCore`, `logisticsLabCli`, `osm_data` und der Server `logisticsLabServer/` werden im Layout des Repositorys kopiert, dazu `confs/logisticsLab.yml`, `confs/logisticsLabServer.yml` und das Beispielszenario. `apiKeys.yml` kommt nicht mit. Eine `.pth`-Datei macht sie für das mitgelieferte Python importierbar.
4. **CMPL-Kern:** `../Cmpl2/dist/buildDist.py --core` kompiliert cmpl und legt HiGHS dazu, als `cmpl/` mit `bin/` und `Thirdparty/Highs/`. pyLogisticsLab findet es dort ohne `CMPLHOME`. Einen fertigen Kern übernimmt `--cmpl DIR`.
5. **Startskripte:** Es gibt `logisticslab`, `logisticslab-stdio`, `logisticslab-server` (uvicorn mit `--app-dir logisticsLabServer`) und `logisticslab-keys` (`manageKeys.py`), unter Windows jeweils als `.bat`. Sie starten das mitgelieferte Python mit `-I` bzw. `-E -s`, unbeeinflusst von `PYTHONPATH` und conda. Ist `LOGLAB_LOG_DIR` nicht gesetzt, setzen sie es auf ein Verzeichnis des Benutzers.
6. **Test:** Das Tool läuft in einer Umgebung ohne `CMPLHOME`, `PYTHON*` und conda.
   - Das Beispielszenario wird mit Luftlinie gelöst (TPP, WLP, Min-Cost-Flow mit CMPL/HiGHS, TSP mit OR-Tools).
   - Über die lokale Schnittstelle (JSON-RPC) läuft ein TPP.
   - Für den REST-Server legt `logisticslab-keys` einen Key in einer Kopie von `confs/` an. Dann startet der Server auf `--test-port` (Default 8124), ein TPP läuft über `/v1/tpp` und `/v1/results`, danach wird der Server beendet.

Flutter wird nicht gebraucht, Nuitka auch nicht. Die Distribution lässt sich aber nur auf dem Zielsystem bauen, denn cmpl wird dort kompiliert. Für Windows, Linux und macOS läuft das Tool also jeweils dort.

## Voraussetzungen

- Python ≥ 3.11 zum Ausführen des Tools
- `git`, weil pip pyCmpl aus GitHub holt
- Internet für Python, Wheels und HiGHS
- für den CMPL-Kern die Voraussetzungen aus `../Cmpl2/dist/README.md`:
  - Windows: MSYS2/MinGW (`g++`, `make`)
  - Linux: `g++`, `make`
  - macOS: Xcode Command Line Tools

## macOS: Signieren und Notarisieren

Ohne Signatur blockiert Gatekeeper die Programme, wenn das Archiv heruntergeladen wurde. Für den Benutzer bleibt dann nur `xattr -dr com.apple.quarantine …`. Für eine Distribution, die wirklich ohne Zutun läuft:

```bash
xcrun notarytool store-credentials logisticslab --apple-id ... --team-id ...     # einmalig
python3 dist/buildDist.py --sign "Developer ID Application: ... (TEAMID)" --notarize logisticslab
```

`--sign` signiert alle Mach-O-Dateien (Python, Erweiterungsmodule, cmpl, HiGHS) mit Hardened Runtime und den Entitlements aus `resources/entitlements.plist`. Danach läuft der Test noch einmal mit den signierten Dateien.

- **`--notarize`:** baut zusätzlich `LogisticsLab-….dmg` (signiert), schickt es an Apple (`notarytool submit --wait`) und heftet das Ticket an (`stapler staple`). Wird es abgelehnt, zeigt das Tool das Protokoll von `notarytool log`.
- **`.dmg` mit angeheftetem Ticket:** Gatekeeper braucht kein Netz.
- **Zip:** An ein Zip lässt sich kein Ticket heften, Gatekeeper fragt dann beim ersten Start online bei Apple nach. Die Notarisierung des `.dmg` gilt auch für die gleichen Dateien im Zip.
- **`--dmg` ohne `--notarize`:** baut nur das Image.

# Programm für Desktop-Apps (`buildStdio.py`)

`buildStdio.py` kompiliert die lokale Schnittstelle (`logisticsLabCore.stdio`) mit Nuitka zu einem eigenständigen Programm. Eine Desktop-App liefert es mit und startet es als Kindprozess. Python, pip und Tcl/Tk sind nicht dabei, der Code ist kompiliert.

```bash
/opt/anaconda3/envs/nuitka/bin/python dist/buildStdio.py                 # Basis-Python der Build-venv
/opt/anaconda3/envs/nuitka/bin/python dist/buildStdio.py --sign "Developer ID Application: ... (TEAMID)"
```

Ergebnis: `dist/build/<os>-<arch>/logisticsLabStdio/`, als Archiv in `dist/out/`:

```
logisticsLabStdio/
  logisticsLabStdio[.exe]      das Programm, daneben seine Bibliotheken (*.so / *.dylib bzw. *.pyd / *.dll)
  pyLogisticsLab/*.cmpl        die CMPL-Modelle
  cmpl/                        CMPL-Kern mit HiGHS
  confs/logisticsLab.yml       OSM-Server der TH Wildau
```

- **Build-Umgebung:** Das Tool legt unter `dist/build/<os>-<arch>/stdio/` eine eigene Umgebung an, mit Nuitka, den Abhängigkeiten aus `pyproject.toml` (ohne Server) und pyCmpl. Basis ist das Python, mit dem das Tool gestartet wird. Bei conda ist das ein Klon des Envs (`nuitka-env`), denn mit einer venv auf conda findet Nuitka `libpython` nicht. Sonst ist es eine venv. Die Quellen von LogisticsLab kommen direkt aus dem Repository.
- **Pfade:** Nuitka setzt `__file__` der kompilierten Module auf ihren Ort im Ergebnisverzeichnis. pyLogisticsLab findet `cmpl/`, und `paths.py` findet `confs/` dort wie im Repository. Eigene OSM-Server kommen nach `confs/logisticsLab.local.yml` oder per `--osmConfig`.
- **Solver-Prozesse:** Jedes Problem läuft in einem eigenen Prozess (`multiprocessing`, spawn). Dafür startet das Programm sich selbst noch einmal (`freeze_support()` in `resources/logisticsLabStdio.py`).
- **Test:** Das Tool startet das Programm in einer Umgebung ohne Python, conda und `CMPLHOME` im `PATH` und löst über JSON-RPC einen TPP (CMPL/HiGHS) und einen TSP (OR-Tools).
- **Nur für das eigene System:** Nuitka kompiliert nicht für andere Systeme. Unter macOS entsteht ein Programm für die Architektur des Basis-Pythons (arm64 mit dem conda-Env auf Apple Silicon). Für Intel-Macs braucht es einen Build auf einem Intel-Mac oder mit einem x86_64-Python.

## Einbinden in eine Mac-App

- **Ort im Bundle:** Das ganze Verzeichnis nach `MeineApp.app/Contents/Resources/logisticsLabStdio/` kopieren. Die App startet `Contents/Resources/logisticsLabStdio/logisticsLabStdio --logPath <~/Library/Application Support/<App>/logs>` mit `Process.start` und spricht über stdin/stdout mit ihm.
- **Signieren:** Jede Mach-O-Datei im Verzeichnis braucht eine Signatur, von innen nach außen, zuletzt die App. Das gilt auch für `cmpl` und `highs`. `--sign` erledigt das für das Verzeichnis, mit Hardened Runtime und `resources/entitlements.plist`. Danach wird die App selbst signiert (ohne `--deep`) und notarisiert.
- **Sandbox (App Store):** Die Binaries im Verzeichnis werden dann nicht mit `resources/entitlements.plist` signiert. Sie bekommen genau `com.apple.security.app-sandbox` und `com.apple.security.inherit`, dann erben `logisticsLabStdio`, die Solver-Prozesse, `cmpl` und `highs` die Sandbox der App. Die App braucht `com.apple.security.network.client` für die OSM-Server. Logs und Matrix-Cache gehören in den Container der App (`--logPath`).
- **Kein Sandbox (Developer ID):** Es reichen Hardened Runtime und Notarisierung.
