# pyLogisticsLab

Python-Bibliothek und REST-Server für logistische Optimierungsprobleme (TSP, Transportproblem, Standortprobleme, Tourenplanung …) mit Anbindung an OpenStreetMap-Dienste für Distanzmatrizen, Routing und Geocoding. Neben dem REST-Server gibt es eine lokale Schnittstelle für Desktop-Apps.

```
        Flutter-App (Desktop, Web, Mobil)
           │                       │
   REST + API-Key            JSON-RPC über stdin/stdout
           │                   (nur Desktop)
  logisticsLabServer        logisticsLabCore.stdio
           └──────────┬────────────┘
               logisticsLabCore         Prüfung der Daten, Jobs, Solver-Prozesse, Abbruch
                      │
          pyLogisticsLab · osm_data     Modelle (CMPL, OR-Tools) · OSM-Server der TH Wildau
```

Ein Projekt der Technischen Hochschule Wildau, LGPL-3.0.

## Inhalt

| Verzeichnis | Inhalt |
|---|---|
| `pyLogisticsLab/` | Bibliothek mit den Modellen: `TspMaster`, `Tpp`, `Wlp`, `PMedian`, `PCentre`, die kontinuierlichen `ContPMedian`, `ContPCentre` (`contLocation.py`), `Scp`, `Mcp`, `Cpp`, `Vrp` und den Netzwerkflüssen `MinCostFlow`, `MaxFlow`, `MultiCommodityFlow`, `MultiModalFlow` (`nwf.py`) |
| `logisticsLabCore/` | Kern ohne Transportschicht: Datenmodelle (Items), Handler, Jobverwaltung mit Solver-Prozessen, lokale stdio-Schnittstelle |
| `logisticsLabServer/` | REST-Server (FastAPI) auf Basis des Kerns, mit API-Keys und Limits |
| `osm_data/` | Zugriff auf OpenRouteService/OSRM (Matrix, Routing) und Photon/Nominatim (Geocoding) |
| `cmpl/` | CMPL-Installation dieses Rechners (`bin/cmpl`, `Thirdparty/…`), nicht versioniert – siehe unten |
| `confs/` | Konfigurationen für die OSM-Server |
| `tests/` | Beispiel- und Testskripte für Bibliothek (`tests/pyCmpl`) und Server (`tests/serverTests`) |

## Installation

```bash
conda create -n pyLogisticsLab python=3.14
conda activate pyLogisticsLab
pip install -r requirements.txt
export PYTHONPATH=$PYTHONPATH:/pfad/zu/pyLogisticsLab
```

**pyCmpl** ist ein eigenes Repository ([MikeSteglich/pyCmpl](https://github.com/MikeSteglich/pyCmpl)) und wird über `requirements.txt` in einer festen Version installiert (Git-Tag, z. B. `v2.1.0`). Derselbe Stand wird auch von der CMPL-Distribution und der CMPL-IDE verwendet.
- **Neue Version übernehmen:** In pyCmpl einen neuen Tag setzen, in `requirements.txt` eintragen und neu installieren.
- **pyCmpl gleichzeitig weiterentwickeln:** pyCmpl neben pyLogisticsLab klonen und mit `pip install -e ../pyCmpl` einbinden. Änderungen wirken dann sofort.
- **pyCmpl ändern:** nur in `../pyCmpl`, nicht in einer Kopie. Den ganzen Ablauf (Entwickeln, Version und Tag, Projekte aktualisieren, CMPL-IDE neu bauen) beschreibt der Abschnitt „Changing pyCmpl“ in der README von pyCmpl.
- **Privates Repository:** Auf einem Server braucht pip Lesezugriff, z. B. über einen Deploy-Key (SSH) oder ein Token mit Leserecht.

**CMPL-Binärdateien:** Sie sind nicht im Repository. pyCmpl sucht CMPL unter `$CMPLHOME/bin/cmpl` (unter Windows `cmpl.exe`). Ist `CMPLHOME` nicht gesetzt, setzt `pyLogisticsLab` die Variable auf `<Projekt>/cmpl`, sofern es dort ein `bin/` gibt. Das Verzeichnis hat das Layout einer CMPL-Installation:

```
cmpl/
  bin/cmpl, bin/cmpl.opt, bin/modules.opt, bin/solversel.opt, bin/cmplstd.cmpl
  Thirdparty/Highs/highs
```

Die Pfade zu den Solvern in `bin/cmpl.opt` sind relativ zu `bin/` (`../Thirdparty/Highs/highs`). Ohne CMPL laufen nur TSP und VRP, die OR-Tools nutzen. Für den Linux-Server wird eine CMPL-Distribution für Linux gebraucht.

**Konfiguration mit Zugangsdaten:** Dateien mit Zugangsdaten sind nicht versioniert. Für sie gibt es Vorlagen:

| Vorlage | kopieren nach | Inhalt |
|---|---|---|
| `confs/logisticsLab.example.yml` | `confs/logisticsLab.yml` | OSM-Server, ORS-API-Key |
| `tests/osmTests/logisticsLab.example.yml` | `tests/osmTests/logisticsLab.yml` | dasselbe für die OSM-Tests |
| `checkserver/checkServer.example.opt` | `checkserver/checkServer.opt` | Mailzugang der Serverüberwachung |
| `logisticsLabServer/apiKeys.example.yml` | – | nur zur Ansicht, die echte Datei erzeugt `manageKeys.py` |

## Bibliothek

Die Modelle bekommen ihre Daten direkt als Listen bzw. Matrizen:

```python
import pyLogisticsLab as ll

m = ll.Tpp(varCosts=[[3, 2, 7], [7, 5, 2]], supplies=[50, 60], demands=[40, 30, 40],
           objSense='min', maxSolvingTime=60)
m.solve()
print(m.getObjValue(), m.getFlows())
```

Weitere Beispiele stehen in `tests/pyCmpl/`. Wer pyCmpl ohne `pyLogisticsLab` direkt nutzt, muss `CMPLHOME` selbst setzen. Fehler werden als `ll.LogLabException` gemeldet. Fortschrittsmeldungen gehen über das `logging`-Modul (Logger `pyLogisticsLab.*`) und nicht über `print`. Wer sie sehen will, ruft `logging.basicConfig(level=logging.INFO)` auf.

## Server

Der Server liegt in `logisticsLabServer/` und muss **aus diesem Verzeichnis** gestartet werden, weil er `logisticsLabServer.yml` und `logisticsLab.yml` dort liest.

```bash
cd logisticsLabServer
python manageKeys.py add mein-test          # Key einmalig anlegen und notieren
uvicorn main:app --host 127.0.0.1 --port 8000
```

Zum Entwickeln geht auch `fastapi dev main.py` (lädt bei Änderungen neu). `fastapi dev` ist nicht für den Betrieb gedacht.

### Ablauf einer Anfrage

Optimierungsprobleme laufen asynchron. Der Client reicht das Problem ein, bekommt eine `id` und fragt das Ergebnis ab, bis der Status `solution`, `noSolution`, `error` oder `cancelled` ist. Jedes Problem wird in einem eigenen Solver-Prozess gelöst, deshalb kann es über `/v1/cancel` abgebrochen werden, auch während es läuft.

```bash
KEY=...   # aus manageKeys.py
curl -s -X POST http://127.0.0.1:8000/v1/tpp -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
     -d '{"varCosts": [[3,2],[1,4]], "supplies": [10,10], "demands": [8,8]}'
# {"id": "6f1c…", "status": "waiting", "message": "Problem is waiting in queue"}

curl -s -X POST http://127.0.0.1:8000/v1/results -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
     -d '{"id": "6f1c…"}'
# {"id": "6f1c…", "status": "solution", "message": "...", "results": {"objVal": 24.0, "solvingTime": 0.04, ...}}
```

Ein abgeholtes Endergebnis wird gelöscht. Ergebnisse, die nicht abgeholt werden, löscht der Server nach `maxInactivityTime`.

Ein Service-Thread räumt außerdem regelmäßig auf (alle `serviceIntervall` Sekunden):

- **Verlassene Probleme:** Fragt ein Client länger als `maxPollingPause` nicht nach dem Status eines wartenden oder laufenden Problems, wird es abgebrochen (`cancelled`). Clients müssen also mindestens alle `maxPollingPause` Sekunden `/v1/results` aufrufen.
- **Hängende Solver:** Ein Watchdog beendet jedes Problem, das länger rechnet als `maxSolvingTime` + `runTimeGrace`. Ohne `maxSolvingTime` gilt `defaultMaxRunTime` + `runTimeGrace`, oder `maxRunTime` des Problemtyps, wenn gesetzt. Das Problem endet dann mit `error` und HTTP-Status 504.

### Endpoints

Alle Endpoints sind `POST` und erwarten JSON. Unbekannte Felder werden mit 422 abgelehnt.

| Endpoint | Zweck | Dienst für Key-Rechte |
|---|---|---|
| `/v1/tsp` | Traveling Salesman: `distances` oder `coordinates` | `tsp` |
| `/v1/tpp` | Transportproblem: `varCosts` oder `sourceCoordinates` + `destinationCoordinates`, dazu `supplies`, `demands`; optional Fixkosten, Kapazitäten, Bereiche, `objSense` (`min`/`max`/`minimax`), Single Source, Blocking | `tpp` |
| `/v1/wlp` | Warehouse Location: `varCosts` (Kostensatz je Nachfrageeinheit) oder Koordinaten, `fixedCosts`, `demands`; mit `isCapacitated` auch `supplies` | `wlp` |
| `/v1/pmedian` | p-Median: `p`, `varCosts` oder Koordinaten; optional `demands`, `supplies`, `isDemandWeighted`, `isCapacitated` | `pmedian` |
| `/v1/pcentre` | p-Center (minimiert die größte Entfernung): Felder wie p-Median | `pcentre` |
| `/v1/contpmedian` | kontinuierlicher p-Median (Standorte frei wählbar, Großkreisdistanz in km): `p`, `coordinates` der Kunden, optional `demands`, `capacities` (Zahl oder p Zahlen; ohne: unkapazitiert), `isSingleSource` (Standard `true`), `nrOfStarts` (Standard 20) | `contpmedian` |
| `/v1/contpcentre` | kontinuierliches p-Center: Felder wie `contpmedian` | `contpcentre` |
| `/v1/scp` | Set Covering: `distances` oder Koordinaten, `radius`; optional `fixedCosts` (Standard 1, also möglichst wenige Standorte) | `scp` |
| `/v1/mcp` | Maximal Covering: `distances` oder Koordinaten, `radius`, `demands`, `maxSrcCost` (Budget für die Fixkosten der Standorte; mit `fixedCosts` 1 die Anzahl) | `mcp` |
| `/v1/cpp` | Chinese Postman: `edges` (`[[i, j], ...]`), `edgeWeights`, `startNode`; optional `edgeTypes` (0 gerichtet, 1 ungerichtet, Standard 1) | `cpp` |
| `/v1/vrp` | Tourenplanung: `distances` oder `coordinates` (alle Knoten mit Depot), `demands`, `capacities` (je Fahrzeug), `depot`; optional `times`, `timeWindows`, `serviceTimes`, `maxTime`, `maxDist`, `maxWaitingTime`, `maxSolvingTime` | `vrp` |
| `/v1/mincostflow` | Min-Cost-Flow: `edges`, `costs` je Kante, `supplies`, optional `demands`, `minCaps`, `maxCaps` | `mincostflow` |
| `/v1/maxflow` | maximaler Fluss: `edges`, `source`, `sink`, `maxCaps`, optional `minCaps`, `nrOfNodes` | `maxflow` |
| `/v1/multicommodity` | Multi-Commodity-Flow: `edges`, `costs` [Kanten × Güter], `supplies`/`demands` [Knoten × Güter], optional gemeinsame `minCaps`/`maxCaps` je Kante, `capacityFactors` [Kanten × Güter] | `multicommodity` |
| `/v1/multimodal` | multimodaler Fluss: `edges`, `costs` [Kanten × Verkehrsträger] (`null`: Verkehrsträger auf dieser Kante nicht verfügbar), `supplies`, optional `demands`, `fixedCosts`, `minCaps` (Mindestmenge, wenn genutzt), `maxCaps` | `multimodal` |
| `/v1/solve` | beliebiges Problem, ausgewählt über das Feld `type` (`"tsp"`, `"tpp"`, `"wlp"`, `"pmedian"`, `"pcentre"`, `"contpmedian"`, `"contpcentre"`, `"scp"`, `"mcp"`, `"cpp"`, `"vrp"`, `"mincostflow"`, `"maxflow"`, `"multicommodity"`, `"multimodal"`) | je nach `type` |
| `/v1/results` | Status bzw. Ergebnis zu einer `id` | – |
| `/v1/cancel` | wartendes oder laufendes Problem abbrechen (`{"id": ...}`); der Status wechselt kurz danach zu `cancelled` | – |
| `/v1/matrix` | Distanz- und/oder Zeitmatrix aus Koordinaten | `matrix` |
| `/v1/routing` | Route über mehrere Koordinaten | `routing` |
| `/v1/coordinates`, `/v1/search`, `/v1/reverse` | Geocoding | `geocoding` |

Die Ergebnisse aller Probleme beginnen mit `objVal` und `solvingTime`, danach folgen die problemspezifischen Felder. Koordinaten werden als `[lat, lon]` übergeben. Alle Indizes sind **0-basiert**, also Position in der übergebenen Liste bzw. Zeile der Matrix. `-1` bedeutet „keine“.

| Typ | Ergebnisfelder |
|---|---|
| `tsp` | `route` (Knotenfolge) |
| `tpp` | `flows` (Matrix), `totalCosts`, `totalVarCosts`, `totalFixedCosts`, `totalFlow`, `sourceFlows`, `destinationFlows`, `minCostRate`, `maxCostRate` |
| `wlp`, `pmedian`, `pcentre` | `activeSources` (0/1 je Quelle), `assignments` (versorgende Quelle je Senke) |
| `contpmedian`, `contpcentre` | `locations` (`[lat, lon]` je Standort), `assignments` (Standort mit dem größten Fluss je Kunde), `customerDistances` (km, bei Aufteilung zum entferntesten liefernden Standort), mit `isSingleSource: false` auch `flows` [Standorte × Kunden] |
| `scp`, `mcp` | `activeSources`, `coveringSources` (alle geöffneten Quellen im Radius je Senke), `assignments` (nächste davon; bei `mcp` `-1` für nicht überdeckte Senken) |
| `cpp` | `eulerTour` (Knotenfolge), `edgeUsages` (Nutzungen je übergebener Kante) |
| `vrp` | `routes`, `routeLoads`, `routeDistances` je Fahrzeug, mit Zeitfenstern auch `routeTimes`; unbenutzte Fahrzeuge haben die Route `[depot, depot]` |
| `mincostflow`, `maxflow` | `flows` je Kante; bei `maxflow` ist `objVal` der maximale Fluss |
| `multicommodity` | `flows` [Kanten × Güter] |
| `multimodal` | `flows` und `usages` (0/1) [Kanten × Verkehrsträger], `totalVarCosts`, `totalFixedCosts` |

Für die Netzwerkflüsse gilt:
- **Knoten und Kanten:** Knoten sind Indizes ab 0, Kanten Paare `[i, j]`.
- **Unbegrenzte Kapazitäten:** `null` oder `"M"`.
- **Ausgleich:** Gesamtangebot und Gesamtnachfrage müssen gleich sein, bei `multicommodity` je Gut. Sonst kommt 400. Einen Überschuss gleicht man mit einem Dummy-Knoten aus.
- **Parallele Kanten:** Keines der Flussmodelle erlaubt parallele Kanten zwischen denselben Knoten. Mehrere Verkehrswege bildet man über `multimodal` mit Verkehrsträgern ab.
- **Solver:** Alle vier laufen über CMPL und HiGHS (`minCostFlow.cmpl`, `maxFlow.cmpl`, `multiCommodity.cmpl`, `multimodal.cmpl` in `pyLogisticsLab/`).
- **Unbeschränkter Max-Flow:** Gibt es einen Weg von `source` nach `sink` nur über unbegrenzte Kanten, kommt 400.

Für die kontinuierlichen Standortprobleme gilt:
- **Distanz:** Großkreisdistanz in km, nicht das Straßennetz. Die Kunden müssen auf einer Halbkugel liegen.
- **Zielfunktion:** `contpmedian` minimiert die Summe Bedarf × Distanz, `contpcentre` die größte Distanz eines Kunden zu einem liefernden Standort. Beim unkapazitierten `contpcentre` zählen die Bedarfe nicht.
- **Kapazitäten:** Mit `capacities` sind `demands` Pflicht. `isSingleSource: true` ordnet jeden Kunden genau einem Standort zu, `false` erlaubt die Aufteilung seines Bedarfs.
- **Verfahren:** heuristisch, nicht beweisbar optimal. Start ist das diskrete `pmedian`/`pcentre` mit den Kunden als Kandidaten, danach abwechselnd Standortwahl (sphärischer Weiszfeld bzw. kleinste umschließende Kugelkappe) und Zuordnung (nächster Standort bzw. `Tpp.cmpl` mit Kapazitäten), dann weitere Zufallsstarts im Rahmen von `nrOfStarts` und `maxSolvingTime`.

Wird die Matrix aus Koordinaten berechnet, steht sie zusätzlich im Ergebnis (`varCosts`, `distances` bzw. bei `vrp` `distances` und `times`). Bei `vrp` werden alle Zahlen gerundet, weil OR-Tools ganze Zahlen verlangt. Aus Koordinaten lädt `vrp` die Fahrzeiten nur, wenn `timeWindows` oder `maxTime` gesetzt sind.

Wenn `docs: True` gesetzt ist, steht die vollständige Beschreibung aller Felder unter `/docs`.

### Zugang mit API-Keys

Jede Anfrage braucht den Header `X-API-Key`. Die Keys verwaltet `manageKeys.py` im Serververzeichnis:

```bash
python manageKeys.py add DSS-WS2026 --expires 2027-03-31 --allowed tsp,tpp --maxOpenProblems 3
python manageKeys.py list
python manageKeys.py disable DSS-WS2026     # sperren
python manageKeys.py enable DSS-WS2026
python manageKeys.py remove DSS-WS2026
```

- `add` zeigt den Key **nur einmal** an. In `apiKeys.yml` steht nur sein SHA-256-Hash. Die Datei wird mit den Rechten `600` angelegt und ist nicht versioniert.
- Der Server lädt `apiKeys.yml` automatisch neu, wenn sie sich ändert. Sperren und neue Keys wirken also ohne Neustart.
- Ein Key gehört zu einem Namen, z. B. Kurs oder Person. Der Name steht im Log, und nur der Key, der ein Problem eingereicht hat, kann dessen Ergebnis abholen.
- Ohne `--allowed` darf ein Key alle Dienste nutzen: die Problemtypen (`tsp`, `tpp`, `wlp`, `pmedian`, `pcentre`, `contpmedian`, `contpcentre`, `scp`, `mcp`, `cpp`, `vrp`, `mincostflow`, `maxflow`, `multicommodity`, `multimodal`) und `matrix`, `routing`, `geocoding`. Keys mit eigener `--allowed`-Liste bekommen neue Dienste nicht automatisch.
- Mit `authentication: False` ist der Server ohne Key offen. Das ist nur für die lokale Entwicklung gedacht.

### Antworten bei Ablehnung

| Status | Bedeutung |
|---|---|
| 401 | Key fehlt, ist falsch, abgelaufen oder gesperrt |
| 403 | Key darf diesen Dienst nicht nutzen |
| 422 | Anfrage passt nicht zum Schema (Feld fehlt, falscher Typ, unbekanntes Feld) |
| 429 | Key hat schon `maxOpenProblems` wartende oder laufende Probleme – erst Ergebnisse abholen |
| 503 | Queue ist voll (`maxQueueSize`) – später erneut versuchen |
| 400 | Daten passen nicht (z. B. falsche Matrixgröße) oder `id` unbekannt |
| 404 | Problem wurde gelöst, hat aber keine zulässige Lösung (`noSolution`) |
| 504 | Problem hat die Zeitgrenze des Watchdogs überschritten und wurde beendet |

### Konfiguration (`logisticsLabServer.yml`)

| Option | Standard | Bedeutung |
|---|---|---|
| `maxProblems` | 4 | Solver-Prozesse, d. h. gleichzeitig gelöste Probleme |
| `maxQueueSize` | 50 | wartende und laufende Probleme aller Keys zusammen |
| `maxOpenProblemsPerKey` | 3 | Standard für Keys ohne eigenes `maxOpenProblems` |
| `maxInactivityTime` | 3600 | Sekunden, nach denen nicht abgeholte Ergebnisse gelöscht werden |
| `maxPollingPause` | 600 | Sekunden ohne Statusabfrage, nach denen ein offenes Problem abgebrochen wird (0: aus) |
| `serviceIntervall` | 30 | Sekunden zwischen zwei Aufräumläufen |
| `runTimeGrace` | 60 | Puffer in Sekunden auf `maxSolvingTime` für den Watchdog |
| `defaultMaxRunTime` | 600 | Zeitgrenze des Watchdogs in Sekunden für Probleme ohne `maxSolvingTime` (z. B. TSP), zuzüglich `runTimeGrace` |
| `authentication` | True | API-Keys erforderlich |
| `apiKeyFile` | `apiKeys.yml` im Serververzeichnis | Pfad zur Key-Datei |
| `docs` | False | `/docs`, `/redoc` und `/openapi.json` anbieten |
| `logging`, `debugging` | True, True | Log-Stufen INFO/WARNING/ERROR bzw. zusätzlich DEBUG |
| `logPath` | Serververzeichnis | Verzeichnis für alle Logdateien |
| `logMaxBytes`, `logBackupCount` | 5 MB, 5 | Rotation von `logisticsLabServer.log` |
| `<typ>.maxNodes` | tsp/vrp 100, tpp/wlp/pmedian/pcentre/contpmedian/contpcentre 200, scp/mcp/cpp/multimodal 300, multicommodity 500, mincostflow/maxflow 2000 | maximale Problemgröße: Quellen + Senken, bei den übrigen Typen die Knoten |
| `<typ>.maxSolvingTime` | 300, vrp 60, mincostflow/maxflow 120 | Obergrenze in Sekunden für die vom Client gewünschte Lösungszeit (bei `vrp` die Suchzeit von OR-Tools) |
| `<typ>.maxRunTime` | – | feste Zeitgrenze des Watchdogs für diesen Problemtyp (ersetzt die Berechnung oben) |

`port` wird derzeit nicht ausgewertet. Den Port legt der Startbefehl von uvicorn fest.

### Logdateien

Alle Logdateien landen in `logPath`:

- `logisticsLabServer.log`: Anfragen, Ergebnisse (eine Zeile pro Problem mit Größe, Status, Zielwert und Laufzeit), Ablehnungen und Fehler, jeweils mit Key-Namen
- `logisticsLab.log`: Zugriffe auf die OSM-Server (CSV)
- `HiGHS.log`: Ausgabe des Solvers. `logPath` ist zugleich das Arbeitsverzeichnis der Solver-Prozesse, deshalb landen auch alle anderen Dateien von CMPL und den Solvern dort.

Für den Betrieb `debugging: False` setzen, sonst wird auch jede Statusabfrage während des Wartens geloggt.

## Lokale Schnittstelle für Desktop-Apps

Eine Desktop-App (z. B. Flutter unter Windows, macOS oder Linux) kann ohne Server lokal rechnen. Sie startet dafür die lokale Schnittstelle als Kindprozess und spricht über stdin/stdout mit ihr ([JSON-RPC 2.0](https://www.jsonrpc.org/specification), eine Nachricht pro Zeile, UTF-8). Es gibt keinen Port, keine Firewall-Abfrage und keine API-Keys. Der Prozess lebt so lange wie die App.

```bash
python -m logisticsLabCore.stdio [--logPath DIR] [--osmConfig FILE] [--maxProblems N] [--debug]
```

- **`--logPath`:** Verzeichnis für Logdateien und `HiGHS.log`. Standard ist `logisticsLab` im Temp-Verzeichnis. Die App sollte ihr Support-Verzeichnis übergeben.
- **`--osmConfig`:** OSM-Server. Standard sind die Server der TH Wildau (`logisticsLabCore/logisticsLab.yml`).
- **Ende:** Der Prozess endet, wenn stdin geschlossen wird oder nach `shutdown`. Laufende Solver werden dabei mit beendet.
- **Aufräumen:** Der Watchdog für hängende Solver ist auch lokal aktiv. Nicht abgeholte Ergebnisse werden nach 12 Stunden gelöscht. Verlassene Probleme werden lokal nicht abgebrochen, denn wenn die App endet, endet auch der Prozess.
- **stdout gehört nur dem Protokoll.** Alle anderen Ausgaben, auch die von CMPL und HiGHS, gehen auf stderr.

Datenformate und Ergebnisse sind dieselben wie beim REST-Server. Die Methoden entsprechen den Endpoints:

| Methode | Parameter | Ergebnis |
|---|---|---|
| `solve` | Problem mit `type` (alle Typen von `/v1/solve`), wie bei `/v1/solve` | `{id, status, message}` |
| `status` | `{id}` | `{id, status, message}` |
| `result` | `{id}` | wie `/v1/results`; ein fertiges Problem wird danach gelöscht |
| `cancel` | `{id}` | `{id, status, message}` |
| `matrix`, `routing`, `coordinates`, `search`, `reverse` | wie die REST-Endpoints | `{message, ...}` |
| `version` | `{}` | `{version, protocol}` |
| `shutdown` | `{}` | `{}` |

Der Prozess schickt außerdem von sich aus Nachrichten. Ein Abfragen in Schleife wie beim REST-Server ist nicht nötig.

| Benachrichtigung | Parameter | wann |
|---|---|---|
| `ready` | `{version, protocol}` | nach dem Start, ab dann werden Anfragen angenommen |
| `jobStatus` | `{id, status, message}` | bei jedem Statuswechsel: `waiting` → `running` → `solution` / `noSolution` / `error` / `cancelled` |

```json
→ {"jsonrpc":"2.0","id":1,"method":"solve","params":{"type":"tpp","varCosts":[[3,2],[1,4]],"supplies":[10,10],"demands":[8,8]}}
← {"jsonrpc":"2.0","id":1,"result":{"id":"6f1c…","status":"waiting","message":"Problem is waiting in queue"}}
← {"jsonrpc":"2.0","method":"jobStatus","params":{"id":"6f1c…","status":"running","message":"Problem is running"}}
← {"jsonrpc":"2.0","method":"jobStatus","params":{"id":"6f1c…","status":"solution","message":"Solution has been found"}}
→ {"jsonrpc":"2.0","id":2,"method":"result","params":{"id":"6f1c…"}}
← {"jsonrpc":"2.0","id":2,"result":{"id":"6f1c…","status":"solution","message":"…","results":{"objVal":24.0,…}}}
```

Fehler kommen als JSON-RPC-Fehler. `data.httpStatus` entspricht dem Status, den der REST-Server liefern würde. Die App kann beide Wege also gleich behandeln:

| Code | Bedeutung | `data` |
|---|---|---|
| -32700 / -32600 | keine gültige JSON- bzw. JSON-RPC-Nachricht | – |
| -32601 | unbekannte Methode | – |
| -32602 | Parameter passen nicht zum Schema | `{httpStatus: 422, errors: [...]}` |
| -32000 | Fehler bei Problem oder Geo-Dienst, z. B. unbekannte `id` | `{httpStatus: 400, ...}` |
| -32603 | interner Fehler | – |

### Hinweise für die Flutter-App

- **Gemeinsame Schnittstelle:** In Dart eine abstrakte Klasse (z. B. `LogisticsLabBackend` mit `submit`, `status`, `result`, `cancel`) mit zwei Implementierungen anlegen. `LocalBackend` startet den Prozess mit `Process.start` aus `dart:io` und liest stdout zeilenweise (`utf8.decoder` + `LineSplitter`). `RemoteBackend` spricht per HTTP mit dem Server und schickt den API-Key mit. Web und Mobil nutzen nur `RemoteBackend`, denn dort lassen sich keine Prozesse starten.
- **Datenmodelle:** `python -m logisticsLabCore.schema > logisticsLab.schema.json` erzeugt das JSON Schema aller Items. Daraus lassen sich die Dart-Modelle generieren, z. B. mit `quicktype --lang dart`. Server und lokale Schnittstelle verwenden dieselben Items.
- **Paketierung:** Die lokale Schnittstelle lässt sich mit PyInstaller im Modus `--onedir` zu einem Programm bündeln (`onefile` entpackt bei jedem Start). Die CMPL-Installation der Zielplattform (`cmpl/` mit `bin/` und `Thirdparty/`) muss mit hinein, und das Programm setzt `CMPLHOME` auf ihren Ort im Paket, bevor es den Kern startet. Unter macOS muss jede mitgelieferte ausführbare Datei signiert sein, auch `cmpl` und HiGHS. Für eine App in der Sandbox braucht der Kindprozess außerdem die Entitlements `com.apple.security.inherit` und `com.apple.security.network.client`.

## Betrieb unter Linux mit nginx

nginx übernimmt TLS, Rate-Limit und die Größenbegrenzung. uvicorn ist nur lokal erreichbar. Die Pfade unten sind Beispiele.

**Wichtig:** uvicorn mit **genau einem** Worker-Prozess starten. Queue und Ergebnisse liegen im Speicher des Prozesses. Bei mehreren Workern würde `/results` die `id` oft nicht finden. Für Parallelität sorgt `maxProblems`.

### systemd (`/etc/systemd/system/logisticslab.service`)

```ini
[Unit]
Description=LogisticsLab Server
After=network.target

[Service]
User=loglab
Group=loglab
WorkingDirectory=/opt/pyLogisticsLab/logisticsLabServer
Environment=PYTHONPATH=/opt/pyLogisticsLab
Environment=CMPLHOME=/opt/pyLogisticsLab/cmpl
ExecStart=/opt/conda/envs/pyLogisticsLab/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now logisticslab
journalctl -u logisticslab -f
```

### nginx (`/etc/nginx/conf.d/logisticslab.conf`)

```nginx
# 10 Anfragen/s pro IP – reicht für die Abfrage des Ergebnisses alle 0,2 s
limit_req_zone $binary_remote_addr zone=loglab:10m rate=10r/s;

server {
    listen 80;
    server_name logisticslab.example.org;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;
    server_name logisticslab.example.org;

    ssl_certificate     /etc/letsencrypt/live/logisticslab.example.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/logisticslab.example.org/privkey.pem;

    client_max_body_size 2m;       # große Matrizen begrenzen

    location /v1/ {
        limit_req zone=loglab burst=20 nodelay;
        limit_req_status 429;

        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;   # Matrix- und Routing-Anfragen laufen synchron
    }

    location / {
        return 404;
    }
}
```

Das Zertifikat bekommt man z. B. mit `certbot --nginx -d logisticslab.example.org`. Von außen müssen nur die Ports 80/443 (und 22) offen sein. Port 8000 bleibt zu.

## Tests

- `tests/pyCmpl/find*.py`: rufen die Bibliothek direkt auf
- `tests/serverTests/*.py`: Clients für einen laufenden Server. Der Key wird aus `LOGLAB_API_KEY` gelesen:

```bash
export LOGLAB_API_KEY=...
python tests/serverTests/findTppServer.py
```

Die Server-Adresse steht oben im jeweiligen Skript (`url = ...`).
