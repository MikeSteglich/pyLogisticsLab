# logisticsLabStdio @VERSION@

Lokale Schnittstelle von LogisticsLab als eigenständiges Programm für Desktop-Apps. Sie spricht JSON-RPC 2.0 über stdin/stdout, eine Nachricht pro Zeile. CMPL @CMPL@ mit HiGHS @HIGHS@ und OR-Tools sind enthalten, Python wird nicht gebraucht.

```
logisticsLabStdio/
  logisticsLabStdio        Startskript (Windows: logisticsLabStdio.bat)
  confs/logisticsLab.yml   OSM-Server der TH Wildau
  bin/                     das Programm logisticsLabStdio, seine Bibliotheken, die CMPL-Modelle und cmpl/
```

## Start

Eine App startet das Programm direkt, ohne das Startskript. Dann beendet ein Abbruch der App auch den Prozess sicher:

```
bin/logisticsLabStdio --logPath <Support-Verzeichnis der App> [--osmConfig DATEI] [--maxProblems N] [--debug]
```

- **Konfiguration:** Das Programm liest `confs/` neben `bin/`. Ein anderes Verzeichnis legt `LOGLAB_CONF_DIR` fest, eine andere Datei `--osmConfig`. Eigene OSM-Server kommen in `confs/logisticsLab.local.yml`.
- **Logs und Matrix-Cache** liegen in `--logPath`. Ohne die Option liegen sie im Benutzerverzeichnis, ein anderer Ort geht mit `LOGLAB_LOG_DIR`.

Die Nachrichten und Ergebnisse beschreibt die Dokumentation von LogisticsLab im Abschnitt „Lokale Schnittstelle für Desktop-Apps".

## macOS

Das ganze Verzeichnis gehört in die App, z. B. nach `Contents/Resources/logisticsLabStdio/`. Jede Mach-O-Datei in `bin/` muss mit derselben Identität signiert sein wie die App, das gilt auch für `cmpl` und `highs`.
