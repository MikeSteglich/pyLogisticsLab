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
| `logisticsLabCore/` | Kern ohne Transportschicht: Datenmodelle (Items), Handler, Jobverwaltung mit Solver-Prozessen, lokale stdio-Schnittstelle, Szenario-Format (`scenario.py`) |
| `logisticsLabServer/` | REST-Server (FastAPI) auf Basis des Kerns, mit API-Keys und Limits |
| `osm_data/` | Zugriff auf OpenRouteService/OSRM (Matrix, Routing) und Photon/Nominatim (Geocoding) |
| `cmpl/` | CMPL-Installation dieses Rechners (`bin/cmpl`, `Thirdparty/…`), nicht versioniert – siehe unten |
| `confs/` | Konfigurationen für die OSM-Server |
| `logisticsLabCli/` | Kommandozeilen-Tool `logisticslab`: Szenarien lösen und anzeigen, alte LogisticsLab-Dateien (TPPX, TSPX, CLPX, DLPX, NWFX, VRPX) umwandeln |
| `tests/` | Beispiel- und Testskripte für Bibliothek (`tests/pyCmpl`) und Server (`tests/serverTests`), Beispielszenario (`tests/scenarios`) |

## Installation

```bash
conda create -n pyLogisticsLab python=3.14
conda activate pyLogisticsLab
pip install -r requirements.txt          # pyCmpl aus GitHub und die übrigen Pakete
pip install -e .                         # Arbeitsplatz und Desktop-App
pip install -e ".[server]"               # REST-Server: zusätzlich fastapi, uvicorn, httpx
```

`pip install -e .` installiert das Projekt aus `pyproject.toml` im Entwicklungsmodus. Danach lassen sich `pyLogisticsLab`, `logisticsLabCore`, `logisticsLabCli` und `osm_data` von überall importieren, ohne `PYTHONPATH`. Änderungen an den Quellen wirken sofort.
- **Befehle:** Die Installation legt zwei Befehle an: `logisticslab` (Kommandozeilen-Tool, siehe unten) und `logisticslab-stdio` (lokale Schnittstelle für Desktop-Apps, gleich `python -m logisticsLabCore.stdio`).
- **Nur im Entwicklungsmodus (`-e`):** `pyLogisticsLab` findet die CMPL-Installation unter `<Projekt>/cmpl` über den Ort seiner Quellen. Bei einer normalen Installation müsste `CMPLHOME` gesetzt sein.
- **pyCmpl ist keine Abhängigkeit in `pyproject.toml`:** Sonst würde pip ein mit `pip install -e ../pyCmpl` eingebundenes pyCmpl durch die Fassung aus GitHub ersetzen. Wer pyCmpl lokal weiterentwickelt, installiert es zuerst mit `pip install -e ../pyCmpl` und dann `pip install -e . --no-deps`, falls die übrigen Pakete schon da sind.
- **Der REST-Server** (`logisticsLabServer/`) ist kein Paket, sondern wird aus seinem Verzeichnis gestartet. Den Kern findet er über die Installation.

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
| `/v1/mincostflow` | Min-Cost-Flow: `edges`, `costs` je Kante, `supplies`, optional `demands`, `minCaps`, `maxCaps`, `fixedCosts` je Kante (fallen an, wenn die Kante Fluss trägt; macht das Problem zum MIP, mit `mipGap`) | `mincostflow` |
| `/v1/maxflow` | maximaler Fluss: `edges`, `source`, `sink`, `maxCaps`, optional `minCaps`, `nrOfNodes` | `maxflow` |
| `/v1/multicommodity` | Multi-Commodity-Flow: `edges`, `costs` [Kanten × Güter], `supplies`/`demands` [Knoten × Güter], optional gemeinsame `minCaps`/`maxCaps` je Kante, `capacityFactors` [Kanten × Güter] | `multicommodity` |
| `/v1/multimodal` | multimodaler Fluss: `edges`, `costs` [Kanten × Verkehrsträger] (`null`: Verkehrsträger auf dieser Kante nicht verfügbar), `supplies`, optional `demands`, `fixedCosts`, `minCaps` (Mindestmenge, wenn genutzt), `maxCaps` | `multimodal` |
| `/v1/solve` | beliebiges Problem, ausgewählt über das Feld `type` (`"tsp"`, `"tpp"`, `"wlp"`, `"pmedian"`, `"pcentre"`, `"contpmedian"`, `"contpcentre"`, `"scp"`, `"mcp"`, `"cpp"`, `"vrp"`, `"mincostflow"`, `"maxflow"`, `"multicommodity"`, `"multimodal"`) | je nach `type` |
| `/v1/results` | Status bzw. Ergebnis zu einer `id` | – |
| `/v1/cancel` | wartendes oder laufendes Problem abbrechen (`{"id": ...}`); der Status wechselt kurz danach zu `cancelled` | – |
| `/v1/matrix` | Matrix aus Koordinaten: `matrixMode` `distances` (m), `durations` (s), `costs`, `both` (Distanzen und Zeiten) oder `all`, optional `sources`, `destinations`, `rounded` und die Matrix-Optionen (siehe unten) | `matrix` |
| `/v1/routing` | Route über mehrere Koordinaten | `routing` |
| `/v1/coordinates` | Koordinaten `[lat, lon]` zu `adresses`, optional `limit` (Treffer je Adresse, 1–10), `countrycodes` (z. B. `["DE"]`), `near` (`[lat, lon]`, nahe Treffer zuerst). Antwort: `coordinates` (erster Treffer, `null` ohne Treffer) und `hits` (je Adresse eine Liste mit `coordinates`, `name`, `street`, `postcode`, `city`, `country`, `countrycode`, `server`) | `geocoding` |
| `/v1/search`, `/v1/reverse` | Treffer zu einer Adresse (`adress`) bzw. Adresse zu einer Koordinate (`coordinate`), `results` ist ohne Treffer leer | `geocoding` |

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
| `mincostflow`, `maxflow` | `flows` je Kante; bei `maxflow` ist `objVal` der maximale Fluss; `mincostflow` mit `fixedCosts` zusätzlich `usages` (0/1 je Kante), `totalVarCosts`, `totalFixedCosts` |
| `multicommodity` | `flows` [Kanten × Güter] |
| `multimodal` | `flows` und `usages` (0/1) [Kanten × Verkehrsträger], `totalVarCosts`, `totalFixedCosts` |

Für die Netzwerkflüsse gilt:
- **Knoten und Kanten:** Knoten sind Indizes ab 0, Kanten Paare `[i, j]`.
- **Unbegrenzte Kapazitäten:** `null` oder `"M"`.
- **Ausgleich (`balance`):**
  - `"auto"` (Standard): wie bei TPP. Bei Angebotsüberschuss bleibt Angebot an den Quellen ungenutzt. Bei Nachfrageüberschuss wird das ganze Angebot geliefert, und ein Teil der Nachfrage bleibt offen. `shortageCosts` legt je Knoten Kosten pro nicht gelieferter Einheit fest, Standard 0. Gilt für alle Flüsse außer `maxflow`.
  - `"exact"`: Gesamtangebot und Gesamtnachfrage müssen gleich sein, bei `multicommodity` je Gut. Sonst kommt 400.
- **Knotenkapazitäten:** `nodeMinCaps`/`nodeMaxCaps` begrenzen den Fluss durch jeden Knoten, einschließlich eigenem Angebot und eigener Nachfrage, z. B. an einem Umschlagpunkt. Bei `multicommodity` gilt die Grenze gemeinsam für alle Güter. Bei `multimodal` gibt es nur `nodeMaxCaps`, denn Mindestmengen gelten dort nur für genutzte Verkehrsträger.
- **Umsetzung:** Intern teilt die Bibliothek einen Knoten mit Kapazität in einen Eingangs- und einen Ausgangsknoten. Dummy-Knoten nehmen den Überschuss auf. Die Ergebnisse beziehen sich nur auf die ursprünglichen Knoten und Kanten.
- **Ergebnisse dazu:** mit Knotenkapazitäten `nodeFlows`. Wurde ein Überschuss ausgeglichen, kommen `unusedSupplies`, `unmetDemands` und `totalShortageCosts` hinzu, jeweils je Knoten, bei `multicommodity` je Knoten und Gut.
- **Parallele Kanten:** Keines der Flussmodelle erlaubt parallele Kanten zwischen denselben Knoten. Mehrere Verkehrswege bildet man über `multimodal` mit Verkehrsträgern ab.
- **Solver:** Alle vier laufen über CMPL und HiGHS (`minCostFlow.cmpl`, mit Fixkosten `minCostFlowFixed.cmpl`, `maxFlow.cmpl`, `multiCommodity.cmpl`, `multimodal.cmpl` in `pyLogisticsLab/`).
- **Fixkosten:** Bei `mincostflow` bleibt `minCaps` eine feste Mindestmenge. Eine Kante mit `minCaps > 0` wird also immer genutzt und kostet ihre Fixkosten. Bei `multimodal` gilt die Mindestmenge dagegen nur, wenn der Verkehrsträger genutzt wird.
- **Unbeschränkter Max-Flow:** Gibt es einen Weg von `source` nach `sink` nur über unbegrenzte Kanten, kommt 400.

Für die kontinuierlichen Standortprobleme gilt:
- **Distanz:** Großkreisdistanz in km, nicht das Straßennetz. Die Kunden müssen auf einer Halbkugel liegen.
- **Zielfunktion:** `contpmedian` minimiert die Summe Bedarf × Distanz, `contpcentre` die größte Distanz eines Kunden zu einem liefernden Standort. Beim unkapazitierten `contpcentre` zählen die Bedarfe nicht.
- **Kapazitäten:** Mit `capacities` sind `demands` Pflicht. `isSingleSource: true` ordnet jeden Kunden genau einem Standort zu, `false` erlaubt die Aufteilung seines Bedarfs.
- **Verfahren:** heuristisch, nicht beweisbar optimal. Start ist das diskrete `pmedian`/`pcentre` mit den Kunden als Kandidaten, danach abwechselnd Standortwahl (sphärischer Weiszfeld bzw. kleinste umschließende Kugelkappe) und Zuordnung (nächster Standort bzw. `Tpp.cmpl` mit Kapazitäten), dann weitere Zufallsstarts im Rahmen von `nrOfStarts` und `maxSolvingTime`.

Zum Geocoding:
- **Kein Treffer:** `null` bzw. eine leere Liste, nie `[0, 0]`. Das wäre ein gültiger Punkt im Atlantik und würde still in Matrizen eingehen.
- **`countrycodes`:** Nominatim filtert auf dem Server. Photon kennt keinen Länderfilter, dort wird unter den abgerufenen Treffern (höchstens 10) gefiltert. Gibt es darunter keinen im Land, ist die Liste leer.
- **`near`:** bevorzugt Treffer in der Nähe, ohne die Relevanz zu ersetzen. Photon gewichtet sie selbst, mit einem Radius von einigen 10 km (`zoom=10`), bei Nominatim gilt ein bevorzugter Kartenausschnitt von etwa 50 km um den Punkt (`viewbox`). Weiter entfernte Treffer bleiben möglich. Für einen harten Ausschluss sind `countrycodes` gedacht.

### Matrizen aus Koordinaten

Alle Probleme mit Koordinaten (`tsp`, `tpp`, `wlp`, `pmedian`, `pcentre`, `scp`, `mcp`, `vrp`) und `/v1/matrix` berechnen ihre Matrix an einer Stelle (`logisticsLabCore/matrixService.py`). Der Client braucht keine Matrizen zu verwalten.

| Feld | Standard | Bedeutung |
|---|---|---|
| `matrixMode` | `distances` | `distances` (m), `times` (s) oder `costs`; bei `vrp` immer Distanzen, mit `timeWindows`/`maxTime` auch Zeiten |
| `travelmode` | `car` | `car`, `foot`, `wheelchair`. Die OSM-Server der TH Wildau bieten derzeit nur `car` an. |
| `matrixSource` | `osm` | `osm`: Straßennetz der OSM-Server. `beeline`: Luftlinie × `detourFactor`, ganz ohne OSM-Server |
| `detourFactor` | 1,3 | nur `beeline`, typisch für Straßen sind 1,2–1,4 |
| `averageSpeed` | car 50, foot 5, wheelchair 4 | km/h, nur `beeline`, für die Fahrzeiten |
| `timeFactor` | 1,0 | Faktor auf alle Fahrzeiten, z. B. 1,2 für Lkw |
| `costPerKm`, `costPerHour` | – | für `matrixMode: costs`: Kosten = km × `costPerKm` + h × `timeFactor` × `costPerHour`; mindestens einer ist nötig |
| `noCache` | false | `true` lädt die Matrix neu von den OSM-Servern und erneuert den Cache-Eintrag |

- **Rundung:** Distanzen und Zeiten werden auf ganze Zahlen gerundet, Kosten auf 2 Nachkommastellen. Bei `/v1/matrix` passiert das nur mit `rounded: true`.
- **Cache:** Die Rohdaten der OSM-Server (Meter und Sekunden) liegen in einer SQLite-Datei. Die Faktoren werden erst danach angewendet. Ein Eintrag gilt also für alle Kostensätze und Zeitfaktoren, und andere Faktoren lösen keine neue OSM-Anfrage aus.
  - **Datenstand:** Der Schlüssel eines Eintrags enthält den Datenstand der ORS-Server (`graph_build_date` aus `/ors/v2/status`). Ihn fragt jeder Prozess höchstens einmal pro Stunde ab. Nach einem Update der Server werden alte Einträge nicht mehr verwendet und nach und nach verdrängt. Antwortet ein Server nicht, gilt der zuletzt bekannte Stand.
  - **Gemessen:** Bei 200 Punkten 13,6 s über OSM, aus dem Cache 0,01 s.
  - **Größe:** Ein Eintrag mit 200 × 200 belegt etwa 0,34 MB.
  - **Datenschutz:** Der Cache speichert die Koordinaten der Anfragen, als Schlüssel nur in Hash-Form. Eine Matrix bekommt nur, wer genau dieselben Koordinaten schickt.
- **`matrixInfo`:** steht im Ergebnis, sobald eine Matrix aus Koordinaten berechnet wurde.
  - `source`: `osm`, `cache` oder `beeline`.
  - `status`: `exact`, `unexact` oder `beeline`. Bei `unexact` hat der OSM-Server für einige Punktpaare keine Route oder einen unplausiblen Wert geliefert. Diese Werte sind mit Luftlinie × durchschnittlichem Umweg geschätzt, die Faktoren stehen in `fillFactors`.
  - `matrices`: welche Matrizen berechnet wurden, dazu die verwendeten Faktoren.
  - `osmDate`: Stand der OSM-Daten, auf dem die Matrix beruht.

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
| `matrixCache` | True | Cache der OSM-Matrizen |
| `matrixCacheFile` | `matrixCache.sqlite` in `logPath` | Cache-Datei, von allen Solver-Prozessen gemeinsam genutzt |
| `matrixCacheMaxAge` | 180 | Tage, Sicherheitsnetz. Nach einem Update der ORS-Server werden die Einträge ohnehin nicht mehr verwendet. |
| `matrixCacheMaxEntries` | 500 | Höchstzahl der Einträge, die am längsten unbenutzten werden zuerst gelöscht |
| `<typ>.maxNodes` | tsp/vrp 100, tpp/wlp/pmedian/pcentre/contpmedian/contpcentre 200, scp/mcp/cpp/multimodal 300, multicommodity 500, mincostflow/maxflow 2000 | maximale Problemgröße: Quellen + Senken, bei den übrigen Typen die Knoten |
| `<typ>.maxSolvingTime` | 300, vrp 60, mincostflow/maxflow 120 | Obergrenze in Sekunden für die vom Client gewünschte Lösungszeit (bei `vrp` die Suchzeit von OR-Tools) |
| `<typ>.maxRunTime` | – | feste Zeitgrenze des Watchdogs für diesen Problemtyp (ersetzt die Berechnung oben) |

`port` wird derzeit nicht ausgewertet. Den Port legt der Startbefehl von uvicorn fest.

### Logdateien

Alle Logdateien landen in `logPath`:

- `logisticsLabServer.log`: Anfragen, Ergebnisse (eine Zeile pro Problem mit Größe, Status, Zielwert und Laufzeit), Ablehnungen und Fehler, jeweils mit Key-Namen
- `logisticsLab.log`: Zugriffe auf die OSM-Server (CSV)
- `matrixCache.sqlite` (mit `-wal`/`-shm`): Cache der OSM-Matrizen, siehe oben
- `HiGHS.log`: Ausgabe des Solvers. `logPath` ist zugleich das Arbeitsverzeichnis der Solver-Prozesse, deshalb landen auch alle anderen Dateien von CMPL und den Solvern dort.

Für den Betrieb `debugging: False` setzen, sonst wird auch jede Statusabfrage während des Wartens geloggt.

## Lokale Schnittstelle für Desktop-Apps

Eine Desktop-App (z. B. Flutter unter Windows, macOS oder Linux) kann ohne Server lokal rechnen. Sie startet dafür die lokale Schnittstelle als Kindprozess und spricht über stdin/stdout mit ihr ([JSON-RPC 2.0](https://www.jsonrpc.org/specification), eine Nachricht pro Zeile, UTF-8). Es gibt keinen Port, keine Firewall-Abfrage und keine API-Keys. Der Prozess lebt so lange wie die App.

```bash
python -m logisticsLabCore.stdio [--logPath DIR] [--osmConfig FILE] [--maxProblems N] [--debug] [--noMatrixCache]
```

- **`--logPath`:** Verzeichnis für Logdateien und `HiGHS.log`. Standard ist `logisticsLab` im Temp-Verzeichnis. Die App sollte ihr Support-Verzeichnis übergeben.
- **`--osmConfig`:** OSM-Server. Standard sind die Server der TH Wildau (`logisticsLabCore/logisticsLab.yml`).
- **Matrix-Cache:** Der Cache liegt in `--logPath` (`matrixCache.sqlite`), `--noMatrixCache` schaltet ihn ab. Ohne Netz rechnet die App mit `matrixSource: "beeline"`.
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
- **Datenmodelle:** `python -m logisticsLabCore.schema > logisticsLab.schema.json` erzeugt das JSON Schema aller Anfragen und Antworten. Daraus lassen sich die Dart-Modelle generieren, z. B. mit `quicktype --lang dart`. Server und lokale Schnittstelle verwenden dieselben Items.
  - **Anfragen:** die Problem-Items (`ContPCentreItem` …) und die Geo-Items.
  - **Antworten:** `ProblemAnswer` (`{id, status, message, results}`) und je Problemtyp ein Ergebnismodell für `results`. Die Zuordnung steht in `RESULT_ITEMS` in `logisticsLabCore/results.py`, z. B. `contpmedian`/`contpcentre` → `ContLocationResults`, `mincostflow`/`maxflow` → `FlowResults`. `checkServer.py` prüft jede echte Antwort gegen diese Modelle, ein neues oder umbenanntes Ergebnisfeld fällt also auf.
- **Beispiel-Client:** `tests/dartClient` ist ein lauffähiges Dart-Paket ohne externe Abhängigkeiten. Es enthält `LogisticsLabBackend` mit `LocalBackend` (Kindprozess, JSON-RPC) und `RemoteBackend` (REST, Abfrage von `/v1/results`), typisierte Ergebnisse in `lib/src/results.dart` und das Beispiel `bin/cont_pcentre.dart`. Fehler kommen in beiden Fällen als `LogisticsLabException` mit `httpStatus`. Für die Flutter-App lässt sich `lib/` direkt übernehmen.
- **Python-Client:** `tests/pythonClient` zeigt dasselbe in Python, nur mit der Standardbibliothek. `logisticsLabClient.py` enthält `LocalBackend` und `RemoteBackend` mit `solve`, `submit`/`wait`/`result`, `cancel` und `geo`. `rawProtocol.py` zeigt das Protokoll ohne Hilfsmodul, jede Nachricht wird ausgegeben.
- **Paketierung:** Die lokale Schnittstelle lässt sich mit PyInstaller im Modus `--onedir` zu einem Programm bündeln (`onefile` entpackt bei jedem Start). Die CMPL-Installation der Zielplattform (`cmpl/` mit `bin/` und `Thirdparty/`) muss mit hinein, und das Programm setzt `CMPLHOME` auf ihren Ort im Paket, bevor es den Kern startet. Unter macOS muss jede mitgelieferte ausführbare Datei signiert sein, auch `cmpl` und HiGHS. Für eine App in der Sandbox braucht der Kindprozess außerdem die Entitlements `com.apple.security.inherit` und `com.apple.security.network.client`.

## Szenario-Format und Kommandozeilen-Tool

Ein Szenario beschreibt ein logistisches Netz einmal. Darauf lassen sich beliebig viele Probleme rechnen, z. B. TPP, WLP, VRP und Min-Cost-Flow auf denselben Knoten. Ein Beispiel ist `tests/scenarios/brandenburg.json`. Die Datenmodelle stehen in `logisticsLabCore/scenario.py`. Sie sind Teil des JSON Schemas (`python -m logisticsLabCore.schema`).

```json
{ "format": "logisticsLab", "version": 1, "id": "brandenburg",
  "units": { "distance": "km", "time": "min" },
  "matrix": { "matrixSource": "osm", "travelmode": "car", "costPerKm": 0.5, "costPerHour": 30 },
  "nodes": [ { "id": "W", "coordinates": [52.30, 13.26], "roles": ["supplier"], "supply": 100 }, "..." ],
  "networks": { "supply": { "directed": true, "edges": [ { "from": "W", "to": "D1", "capacity": 100 } ] } },
  "vehicles": [ { "id": "LKW", "capacity": 60, "count": 2, "depot": "D1" } ],
  "problems": [ { "name": "Lagerstandorte", "type": "wlp", "parameters": { "isCapacitated": true } } ] }
```

**Regeln:**
- **Koordinaten:** Jeder Knoten hat geografische Koordinaten `[lat, lon]`. Die Adresse (`address` oder `addressDetails`) ist optional.
- **Distanzen und Fahrzeiten:** kommen nur von den OSM-Servern, über den Matrix-Cache, oder als Luftlinie (`matrixSource: beeline`). Eigene Matrizen gibt es im Szenario nicht.
- **Kosten:** werden abgeleitet: km × `costPerKm` + h × `timeFactor` × `costPerHour`, bei Kunden mal `costFactor`. `matrixMode` eines Problems wählt `distances`, `times` oder `costs`.
- **Einheiten:** `units` legt die Einheiten fest, `distance` m oder km, `time` s, min oder h. `costPerKm` und `costPerHour` beziehen sich immer auf km und h.
- **Rollen:** bestimmen, was ein Problem liest.
  - `supplier` → `customer`: TPP.
  - `candidate` → `customer`: WLP, P-Median, P-Center, SCP, MCP.
  - `facility`: kontinuierliche Standorte, ihre Anzahl ist `p` und ihre Kapazitäten gelten.
  - `depot`: VRP.
- **Netze** (`networks`): legen die erlaubten Verbindungen fest, mit Kapazität, Mindestfluss, Fixkosten und Richtung je Kante. Ihre Länge und Fahrzeit kommt von OSM.
  - `networkMode: edges`: nur diese Kanten sind erlaubt. Bei TPP und Standortproblemen sind die übrigen Paare dann gesperrt.
  - `networkMode: shortestPaths`: Es entsteht eine vollständige Matrix aus den kürzesten Wegen über das Netz. Bei TSP enthält die Lösung den ganzen Weg (`path`).
  - Flüsse und CPP brauchen ein Netz. `minCap`/`maxCap` eines Knotens begrenzen den Durchfluss, einschließlich eigenem Angebot und eigener Nachfrage. `capacity` ist dagegen die Kapazität eines Standorts bei den Standortproblemen.
  - Ungleiche Gesamtangebote und -nachfragen werden ausgeglichen (`"balance": "auto"`, Standard). Mit `"balance": "exact"` gibt es stattdessen einen Fehler. Nicht gelieferte Mengen kosten je Senke `shortageCost`, Standard 0.
- **Weitere Knotenattribute:** `minSupply`/`maxSupply`, `minDemand`/`maxDemand` (wirksam mit `useSupplyRanges`/`useDemandRanges`), `timeWindow`, `serviceTime`, `active: false` (Knoten wird ignoriert), `shortageCost` (bei `balance: auto`).
- **Güter und Verkehrsträger:** für `multicommodity` und `multimodal`.
  - `commodities`: Liste der Güter mit `costPerKm`, `costPerHour` und `capacityFactor`. An den Knoten stehen `supplies`/`demands` je Gut, an den Kanten optional abweichende Werte unter `commodities`.
  - `modes`: Liste der Verkehrsträger mit `costPerKm`, `costPerHour`, `fixedCost`, `minFlow` und `capacity`. Eine Kante ohne `modes` erlaubt alle Verkehrsträger. Mit `modes` erlaubt sie nur die genannten, mit eventuell eigenen Werten.
  - Die Kosten kommen auch hier aus der OSM-Distanz und -Fahrzeit.
  - `fixed` und `assignedTo` werden bisher nur gespeichert. Die Probleme berücksichtigen sie noch nicht, das Ergebnis enthält dann eine Warnung.

**Ergebnisse** sind eigene Dokumente (`logisticsLabSolution`). Sie stehen nicht im Szenario.
- **Bezug:** Jedes Dokument verweist mit `scenario.hash` auf genau einen Datenstand des Szenarios und enthält das Problem mit seinen Parametern.
- **Inhalt:** `matrixInfo`, `valueUnit` (Einheit der Matrixwerte) und Warnungen. Dazu `results` mit `objVal`, `summary`, `nodes`, `assignments`, `routes` oder `edges`, jeweils über Knoten-IDs, und die bisherigen Felder unter `native`.

**Kommandozeilen-Tool:**

```bash
logisticslab show  tests/scenarios/brandenburg.json
logisticslab solve tests/scenarios/brandenburg.json                        # alle Probleme, Ausgabe am Bildschirm
logisticslab solve SZENARIO.json --problem "Touren ab Wildau" --set maxSolvingTime=30
logisticslab solve SZENARIO.json --out loesungen.json --quiet              # nur als Datei
logisticslab solve SZENARIO.json --json                                    # Lösungsdokumente am Bildschirm
logisticslab solve SZENARIO.json --server https://logisticslab.example.org/v1/ --apiKey ...
logisticslab --help                                                        # ohne Installation: python -m logisticsLabCli ...
```

- **Rechnen:** Ohne `--server` rechnet das Tool lokal mit dem Kern und den OSM-Servern aus `logisticsLabCore/logisticsLab.yml`, mit Matrix-Cache in `--logPath`. Mit `--server` schickt es Matrix- und Problemanfragen an einen LogisticsLab-Server. Am Server selbst muss dafür nichts geändert werden, denn das Tool übersetzt die Szenarien in die bestehenden `/v1`-Anfragen.
- **Parameter überschreiben:** `--set NAME=WERT` gilt für die Parameter der Probleme, z. B. `p`, `maxSolvingTime`, `matrixMode`.
- **Exit-Code:** 1, wenn ein Problem mit einem Fehler endet.

### Alte LogisticsLab-Dateien umwandeln

```bash
logisticslab convert ALTE_DATEI.TPPX                                     # -> alte_datei.tppx.json daneben
logisticslab convert --dir LogisticsLab-Daten/Modelle-Ors --target LogisticsLab-Daten/Szenarien
```

- **Formate:** TPPX → `tpp`, DLPX → `wlp`/`pmedian`/`pcentre`/`mcp`, CLPX → `contpmedian`/`contpcentre`, NWFX → `mincostflow`, TSPX → `tsp`/`cpp`, VRPX → `vrp`. Die Optionen der Datei werden zu den Parametern des Problems.
- **Übersprungen:** Dateien mit eigenen Matrizen (`DistFunc OwnDef`) oder ebenen Koordinaten (`Map SimpleMap`).
- **Gespeicherte Matrizen** werden nicht übernommen. Ausnahmen: `M` in `COSTS` (gesperrte Verbindung), `CAPACITIES` und `FIXEDCOSTS` werden zu einem Netz `connections`.
- **Reihenfolge:** In den alten Dateien steht `x` = Länge, `y` = Breite. Die Umwandlung schreibt `[lat, lon]`.
- **`DistFunc` entscheidet über die Matrix:** `GreatCircle…` ergibt Luftlinie, `OSM/…` Straßennetz, auch bei `TravelMode Bird`. `DistFactor` wird zu `costPerKm` bzw. `costPerHour`.
- **Bezeichner:** Gleichnamige Quellen und Ziele am selben Ort werden ein Knoten mit beiden Rollen. Gleiche Namen an verschiedenen Orten bekommen `#2`, `#3` …
- **Nur Dateien schreiben:** `logisticslab convert` (`logisticsLabCli/convertX.py`) erzeugt nur JSON-Dateien und rechnet nicht. Gelöst wird mit dem Kommandozeilen-Tool.

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

**Bibliothek** (`tests/pyCmpl/`):
- `find*.py`: Beispiele, die ein Modell direkt aufrufen und das Ergebnis ausgeben.
- `checkLibrary.py`: Regressionstest aller Modelle. Er vergleicht die Zielfunktionswerte mit erwarteten Werten, prüft typische Fehlerfälle und endet mit Exit-Code 1, wenn etwas fehlschlägt.

```bash
python tests/pyCmpl/checkLibrary.py
```

**Kern** (`tests/coreTests/`): `checkMatrixService.py` prüft den Matrix-Cache ohne OSM-Server. Geprüft werden Laden, Wiederverwendung, Neustart, `noCache`, Ablaufzeit, ein simuliertes Update der ORS-Server und die stündliche Statusabfrage, dazu Kostenformel und Luftlinie. Zum Schluss liest er den Datenstand der konfigurierten Server, falls sie erreichbar sind.

```bash
python tests/coreTests/checkMatrixService.py
```

**Server-Beispiele** (`tests/serverExamples/`): ein eigenständiges Skript je Problemtyp und Geo-Dienst, z. B. `wlpExample.py`, `contPCentreExample.py`, `matrixExample.py`. Adresse, Key, Daten, Einreichen, Abfrage der Ergebnisse und Ausgabe stehen direkt im Code, ohne Hilfsmodul. Die Skripte eignen sich als Vorlage für eigene Clients.
- **Beispiel-Key:** Die Skripte nutzen den festen Key `loglab-local-example-key`. Im Header `X-API-Key` steht immer der Key selbst, der Server kennt nur dessen Hash.
- **Registrieren:** `python tests/serverTests/createTestKeys.py` trägt den Hash unter dem Namen `localExample` in die lokale `apiKeys.yml` ein. Mit `--keyFile` für einen anderen Server lehnt das Skript den Beispiel-Key ab, denn er steht öffentlich im Repo.
- **Starten:**

```bash
python tests/serverTests/createTestKeys.py         # einmal: Beispiel- und Test-Keys anlegen
cd logisticsLabServer && ./run_server.sh           # lokaler Server auf Port 8000
python tests/serverExamples/contPCentreExample.py  # in einem zweiten Terminal
```

**Server-Tests** (`tests/serverTests/`):
- `find<Typ>Server.py`: Beispiel je Problemtyp. Die Daten stehen in `payloads`. Senden, Abholen und die Anzeige der Lösung (`showResults`) übernimmt `logLabClient.py`.
- `getMatrixServer.py`, `getRouteServer.py`, `getGeoCodingCoords.py`, `getGeoCodingSearch.py`, `getGeoCodingReverse.py`: Beispiele für die Geo-Endpoints `/v1/matrix`, `/v1/routing`, `/v1/coordinates`, `/v1/search` und `/v1/reverse`, ebenfalls mit Key über `logLabClient.py`.
- `checkServer.py`: Regressionstest über alle Beispiele. Er prüft:
  - die Zielfunktionswerte und das gleiche Ergebnis über `/v1/solve`,
  - jede Antwort gegen das Ergebnis-Schema,
  - Fehlerfälle mit ihrem HTTP-Status,
  - einen Key ohne die Rechte für `contpcentre` und `matrix`,
  - die Geo-Endpoints und ein TSP mit Matrix aus Koordinaten. Diese Prüfungen brauchen die OSM-Server aus `logisticsLab.yml`. Sind die nicht erreichbar, werden sie übersprungen.
- Die Server der TH Wildau bieten derzeit nur das Profil `car` an. `foot` und `wheelchair` liefern dort 400.
- `runServerTests.sh`: erledigt alles in einem Schritt. Es erzeugt neue Test-Keys, startet einen lokalen Server auf Port 8000, falls keiner läuft, führt die Tests aus und stoppt den Server wieder. Das Server-Log steht in `tests/serverTests/server.log`.

```bash
PYTHON=/opt/anaconda3/envs/pyLogisticsLab/bin/python tests/serverTests/runServerTests.sh                       # checkServer.py
PYTHON=/opt/anaconda3/envs/pyLogisticsLab/bin/python tests/serverTests/runServerTests.sh findContPCentreServer.py
```

**Test-Keys:** `createTestKeys.py` legt die Keys `serverTests` (alle Dienste) und `serverTestsRestricted` (nur `tsp`) an. Gleichnamige Keys werden bei jedem Lauf ersetzt.
- **Speicherorte:** In `logisticsLabServer/apiKeys.yml` stehen nur die Hashes. Die Keys selbst stehen in `tests/serverTests/.env` (Rechte `600`). Beide Dateien sind nicht versioniert.
- **Ohne Export:** `logLabClient.py` und der Dart-Client lesen die `.env` selbst. Variablen aus der Umgebung haben Vorrang. Ist die `.env` einmal angelegt, laufen die Skripte gegen einen laufenden Server also direkt, z. B. `python tests/serverTests/findWlpServer.py`.
- **Entfernen:** `python tests/serverTests/createTestKeys.py --remove` löscht die Keys und die `.env`.
- **Entfernter Server:** Das Skript dort mit dessen Key-Datei ausführen und die `.env` auf den Client kopieren:

```bash
python tests/serverTests/createTestKeys.py --keyFile /etc/logisticsLab/apiKeys.yml --url https://logisticslab.example.org/v1/
```

Bei den Heuristiken (`vrp`, `contpmedian`, `contpcentre`) gilt ein besserer Wert als erwartet ebenfalls als bestanden.

**Dart-Client** (`tests/dartClient/`, Dart SDK ab 3.5):

```bash
cd tests/dartClient
dart pub get
LOGLAB_PYTHON=/pfad/zu/python dart run bin/cont_pcentre.dart local    # lokale Schnittstelle als Kindprozess
dart run bin/cont_pcentre.dart remote                                 # Server, LOGLAB_URL und LOGLAB_API_KEY aus der .env
```

**Python-Client** (`tests/pythonClient/`): Beispiele für die JSON-RPC-Kommunikation mit der lokalen Schnittstelle, analog zum Dart-Client.
- **`logisticsLabClient.py`:** `LocalBackend` startet `python -m logisticsLabCore.stdio` als Kindprozess. `RemoteBackend` spricht mit dem REST-Server. Beide haben dieselbe Schnittstelle, Fehler kommen als `LogisticsLabException` mit `httpStatus`.
- **`contPCentre.py`:** dasselbe Beispiel wie `cont_pcentre.dart`, mit `local` oder `remote`. Für `remote` kommt der Key aus `LOGLAB_API_KEY` oder der `.env`.
- **`rawProtocol.py`:** das Protokoll ohne Hilfsmodul: `ready`, `solve`, `jobStatus`, `result`, `shutdown`, jede Nachricht wird ausgegeben.
- **`parallelAndCancel.py`:** mehrere Probleme gleichzeitig mit Statusmeldungen, ein Abbruch, eine Luftlinien-Kostenmatrix und eine abgelehnte Anfrage (422).

```bash
python tests/pythonClient/rawProtocol.py
python tests/pythonClient/contPCentre.py local      # oder remote
python tests/pythonClient/parallelAndCancel.py
```

**OSM-Server direkt** (`tests/osmTests/`): `get*.py` nutzen die Bibliothek `osm_data`, `ors*.py` fragen einen OpenRouteService-Server direkt per HTTP ab (Koordinaten `[lon, lat]`, kein LogisticsLab-Key). Diese Skripte testen die OSM-Server, nicht den LogisticsLab-Server.
