# logisticslab @VERSION@

Kommandozeilen-Tool von LogisticsLab als eigenständiges Programm, ohne Installation und ohne Python. Es löst Szenarien (`.llab`), zeigt sie an und wandelt alte LogisticsLab-Dateien um. CMPL @CMPL@ mit HiGHS @HIGHS@ und OR-Tools sind enthalten.

```
logisticslab-cli/
  logisticslab             Startskript (Windows: logisticslab.bat)
  confs/                   Konfiguration der OSM-Server
  examples/                Beispielszenario
  bin/                     das Programm logisticslab, seine Bibliotheken, die CMPL-Modelle und cmpl/
```

## Aufruf

```bash
./logisticslab show  examples/brandenburg.llab           # Windows: logisticslab show examples\brandenburg.llab
./logisticslab solve examples/brandenburg.llab           # alle Probleme, Ausgabe am Bildschirm
./logisticslab solve SZENARIO.llab --problem "Touren ab Wildau" --set maxSolvingTime=30
./logisticslab solve SZENARIO.llab --out                 # Lösungen als SZENARIO.llsol
./logisticslab solve SZENARIO.llab --json                # Lösungsdokumente am Bildschirm
./logisticslab solve SZENARIO.llab --server https://…/v1/ --apiKey …     # auf einem LogisticsLab-Server
./logisticslab convert ALTE_DATEI.TPPX                   # alte LogisticsLab-Datei -> Szenario
./logisticslab --help
```

Wer das Verzeichnis in den `PATH` aufnimmt, kann `logisticslab` von überall aufrufen. `bin/logisticslab` lässt sich auch direkt starten.

## Konfiguration und Logs

- **OSM-Server:** `confs/logisticsLab.yml` enthält die Server der TH Wildau. Eigene Server oder ein ORS-API-Key kommen in `confs/logisticsLab.local.yml`, Vorlage ist `confs/logisticsLab.local.example.yml`. Einen anderen Ort legt `LOGLAB_CONF_DIR` oder `--osmConfig` fest.
- **Logs und Matrix-Cache** liegen im Benutzerverzeichnis unter `cli/`, ein anderer Ort geht mit `--logPath` oder `LOGLAB_LOG_DIR`.
  - Windows: `%LOCALAPPDATA%\LogisticsLab\logs`
  - macOS: `~/Library/Logs/LogisticsLab`
  - Linux: `~/.local/state/logisticsLab`

## macOS

Ist die Distribution nicht signiert und notarisiert, blockiert macOS beim ersten Start die Programme aus einem heruntergeladenen Archiv. Dann einmal im Terminal ausführen:

```bash
xattr -dr com.apple.quarantine <Pfad zu logisticslab-cli>
```

LogisticsLab ist ein Projekt der Technischen Hochschule Wildau (LGPL-3.0). CMPL steht unter der GPL-3.0, HiGHS unter der MIT-Lizenz.
