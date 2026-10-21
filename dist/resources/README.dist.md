# LogisticsLab @VERSION@

Logistische Optimierungsprobleme (TSP, Transportproblem, Standortprobleme, Tourenplanung, Netzwerkflüsse …) lösen, mit Distanzen und Fahrzeiten von OpenStreetMap.

Die Distribution läuft ohne Installation. Python, alle Bibliotheken, CMPL und der Solver HiGHS sind enthalten. Einfach auspacken und starten.

## Kommandozeilen-Tool

```bash
./logisticslab show  examples/brandenburg.llab        # Windows: logisticslab show examples\brandenburg.llab
./logisticslab solve examples/brandenburg.llab
./logisticslab solve SZENARIO.llab --out              # Lösungen als SZENARIO.llsol
./logisticslab convert ALTE_DATEI.TPPX                # alte LogisticsLab-Dateien umwandeln
./logisticslab --help
```

Wer das Verzeichnis in den `PATH` aufnimmt, kann `logisticslab` von überall aufrufen.

## Lokale Schnittstelle für Desktop-Apps

`logisticslab-stdio` spricht JSON-RPC 2.0 über stdin/stdout (eine Nachricht pro Zeile). Eine Desktop-App startet sie als Kindprozess:

```
logisticslab-stdio --logPath <Support-Verzeichnis der App>
```

Unter Windows sollte eine App direkt `bin\python\python.exe -I -m logisticsLabCore.stdio --osmConfig confs\logisticsLab.yml …` starten, nicht `logisticslab-stdio.bat`. Dann beendet ein Abbruch der App auch den Prozess sicher. Unter Linux und macOS entspricht das `bin/python/bin/python3 -I -m logisticsLabCore.stdio …`. Ohne Startskript ist `LOGLAB_CONF_DIR` nicht gesetzt, deshalb gibt die App `--osmConfig` an oder setzt die Variable selbst auf `confs/`.

## REST-Server

```bash
./logisticslab-keys add mein-client                   # API-Key anlegen, wird nur einmal angezeigt
./logisticslab-server                                 # http://127.0.0.1:8000
./logisticslab-server --host 0.0.0.0 --port 5000      # Optionen von uvicorn
./logisticslab-keys list | disable NAME | enable NAME | remove NAME
```

Die Anfragen beschreibt die Dokumentation von LogisticsLab (`/v1/solve`, `/v1/results` …). Die Einstellungen stehen in `confs/logisticsLabServer.yml`, die Keys in `confs/apiKeys.yml`. Ist das Programmverzeichnis schreibgeschützt (z. B. unter `/opt`), legt `LOGLAB_CONF_DIR` ein anderes Konfigurationsverzeichnis fest. Dorthin gehören dann auch `logisticsLab.yml` und `logisticsLabServer.yml` aus `confs/`.

Im Internet gehört der Server hinter einen Reverse-Proxy (z. B. nginx) für TLS und Rate-Limits.

## Konfiguration und Logs

- **OSM-Server:** `confs/logisticsLab.yml` enthält die Server der TH Wildau. Eigene Server oder ein ORS-API-Key kommen in `confs/logisticsLab.local.yml`, Vorlage ist `confs/logisticsLab.local.example.yml`.
- **Logs und Matrix-Cache** liegen im Benutzerverzeichnis. Mit `LOGLAB_LOG_DIR` lässt sich ein anderer Ort festlegen.
  - Windows: `%LOCALAPPDATA%\LogisticsLab\logs`
  - macOS: `~/Library/Logs/LogisticsLab`
  - Linux: `~/.local/state/logisticsLab`
- **Andere Konfiguration:** `LOGLAB_CONF_DIR` legt ein anderes Konfigurationsverzeichnis fest. Ohne die Variable setzen die Startskripte sie auf `confs/` neben sich.

## macOS

Ist die Distribution nicht signiert und notarisiert, blockiert macOS beim ersten Start die Programme aus einem heruntergeladenen Archiv. Dann einmal im Terminal ausführen:

```bash
xattr -dr com.apple.quarantine <Pfad zu LogisticsLab>
```

## Inhalt

| | |
|---|---|
| `logisticslab`, `logisticslab-stdio`, `logisticslab-server`, `logisticslab-keys` (`.bat` unter Windows) | Startskripte |
| `confs/` | Konfiguration |
| `examples/` | Beispielszenario |
| `bin/python/` | Python @PYTHON@ mit numpy, OR-Tools, pydantic, pyCmpl, FastAPI, uvicorn … |
| `bin/pyLogisticsLab/`, `bin/logisticsLabCore/`, `bin/logisticsLabCli/`, `bin/osm_data/`, `bin/logisticsLabServer/` | LogisticsLab |
| `bin/cmpl/` | CMPL @CMPL@ mit HiGHS @HIGHS@ |

LogisticsLab ist ein Projekt der Technischen Hochschule Wildau (LGPL-3.0). CMPL steht unter der GPL-3.0, HiGHS unter der MIT-Lizenz, Python unter der PSF-Lizenz.
