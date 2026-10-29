# pyLogisticsLab

Python library and REST server for logistics optimisation problems (TSP, transportation problem, location problems, vehicle routing …) with access to OpenStreetMap services for distance matrices, routing and geocoding. Besides the REST server there is a local interface for desktop apps.

```
        Flutter app (desktop, web, mobile)
           │                       │
   REST + API key            JSON-RPC via stdin/stdout
           │                   (desktop only)
  logisticsLabServer        logisticsLabCore.stdio
           └──────────┬────────────┘
               logisticsLabCore         validation of the data, jobs, solver processes, cancelling
                      │
          pyLogisticsLab · osm_data     models (CMPL, OR-Tools) · OSM servers of TH Wildau
```

A project of the Technical University of Applied Sciences Wildau, AGPL-3.0-or-later.

## Contents

| Directory | Contents |
|---|---|
| `pyLogisticsLab/` | library with the models: `TspMaster`, `Tpp`, `Wlp`, `PMedian`, `PCentre`, the continuous `ContPMedian`, `ContPCentre` (`contLocation.py`), `Scp`, `Mcp`, `Cpp`, `Vrp` and the network flows `MinCostFlow`, `MaxFlow`, `MultiCommodityFlow`, `MultiModalFlow` and the multi-stage WLP `MultiStageWlp` (`nwf.py`) |
| `logisticsLabCore/` | core without transport layer: data models (items), handlers, job management with solver processes, local stdio interface, scenario format (`scenario.py`) |
| `logisticsLabServer/` | REST server (FastAPI) based on the core, with API keys and limits |
| `osm_data/` | access to OpenRouteService/OSRM (matrix, routing) and Photon/Nominatim (geocoding) |
| `cmpl/` | CMPL installation of this machine (`bin/cmpl`, `Thirdparty/…`), not versioned – see below |
| `confs/` | all configurations: OSM servers (`logisticsLab.yml`), server (`logisticsLabServer.yml`), API keys (`apiKeys.yml`, not versioned) |
| `logs/` | log files and matrix cache of the server, the command line tool and the local interface, not versioned |
| `logisticsLabCli/` | command line tool `logisticslab`: solve and show scenarios, convert old LogisticsLab files (TPPX, TSPX, CLPX, DLPX, NWFX, VRPX) |
| `tests/` | example and test scripts for the library (`tests/pyCmpl`) and the server (`tests/serverTests`), example scenario (`tests/scenarios`) |

## Installation

```bash
conda create -n pyLogisticsLab python=3.14
conda activate pyLogisticsLab
pip install -r requirements.txt          # pyCmpl from GitHub and the other packages
pip install -e .                         # workstation and desktop app
pip install -e ".[server]"               # REST server: additionally fastapi, uvicorn, httpx
```

`pip install -e .` installs the project from `pyproject.toml` in development mode. Afterwards `pyLogisticsLab`, `logisticsLabCore`, `logisticsLabCli` and `osm_data` can be imported from anywhere, without `PYTHONPATH`. Changes to the sources take effect immediately.
- **Commands:** The installation creates two commands: `logisticslab` (command line tool, see below) and `logisticslab-stdio` (local interface for desktop apps, same as `python -m logisticsLabCore.stdio`).
- **Only in development mode (`-e`):** `pyLogisticsLab` finds the CMPL installation under `<project>/cmpl` via the location of its sources. With a normal installation `CMPLHOME` has to be set.
- **pyCmpl is not a dependency in `pyproject.toml`:** Otherwise pip would replace a pyCmpl installed with `pip install -e ../pyCmpl` by the version from GitHub. Anyone developing pyCmpl locally installs it first with `pip install -e ../pyCmpl` and then `pip install -e . --no-deps`, if the other packages are already there.
- **The REST server** (`logisticsLabServer/`) is not a package but is started from its directory. It finds the core via the installation.

**pyCmpl** is a repository of its own ([MikeSteglich/pyCmpl](https://github.com/MikeSteglich/pyCmpl)) and is installed in a fixed version via `requirements.txt` (git tag, e.g. `v3.0.0`). The same version is also used by the CMPL distribution and the CMPL IDE.
- **Taking over a new version:** Set a new tag in pyCmpl, enter it in `requirements.txt` and reinstall.
- **Developing pyCmpl at the same time:** Clone pyCmpl next to pyLogisticsLab and include it with `pip install -e ../pyCmpl`. Changes then take effect immediately.
- **Changing pyCmpl:** only in `../pyCmpl`, not in a copy. The whole process (developing, version and tag, updating the projects, rebuilding the CMPL IDE) is described in the section “Changing pyCmpl” in the README of pyCmpl.
- **Private repository:** On a server pip needs read access, e.g. via a deploy key (SSH) or a token with read permission.

**CMPL binaries:** They are not in the repository. pyCmpl looks for CMPL under `$CMPLHOME/bin/cmpl` (on Windows `cmpl.exe`). If `CMPLHOME` is not set, `pyLogisticsLab` sets the variable to `<project>/cmpl`, provided there is a `bin/` there. The directory has the layout of a CMPL installation:

```
cmpl/
  bin/cmpl, bin/cmpl.opt, bin/modules.opt, bin/solversel.opt, bin/cmplstd.cmpl
  Thirdparty/Highs/highs
```

The paths to the solvers in `bin/cmpl.opt` are relative to `bin/` (`../Thirdparty/Highs/highs`). Without CMPL only TSP and VRP run, which use OR-Tools. The Linux server needs a CMPL distribution for Linux.

**Configuration and logs:** All configurations are in `confs/`, all log files and the matrix cache in `logs/`. The server, the command line tool, the local interface, `osm_data` and the tests find them there by themselves, no matter from which directory they are started (`logisticsLabCore/paths.py`).

| File | versioned | Contents |
|---|---|---|
| `confs/logisticsLab.yml` | yes | OSM servers of TH Wildau (matrix, routing, geocoding), without credentials |
| `confs/logisticsLab.local.yml` | no | optional: own OSM servers or an ORS API key. If present, it replaces `logisticsLab.yml`. Template: `confs/logisticsLab.local.example.yml` |
| `confs/logisticsLabServer.yml` | yes | configuration of the REST server, see below |
| `confs/apiKeys.yml` | no | API keys of the server (hashes only), created by `manageKeys.py`. Template for reference: `confs/apiKeys.example.yml` |
| `checkserver/checkServer.opt` | no | mail access of the server monitoring, template `checkserver/checkServer.example.opt` |

- **Other locations:** `LOGLAB_CONF_DIR` sets the configuration directory, `LOGLAB_LOG_DIR` the log directory, e.g. `/etc/logisticsLab` and `/var/log/logisticsLab` on the Linux server. Single files can be changed in `logisticsLabServer.yml` (`apiKeyFile`, `logPath`, `osmConfigFile`) or with `--osmConfig` and `--logPath`.

## Library

The models get their data directly as lists or matrices:

```python
import pyLogisticsLab as ll

m = ll.Tpp(varCosts=[[3, 2, 7], [7, 5, 2]], supplies=[50, 60], demands=[40, 30, 40],
           objSense='min', maxSolvingTime=60)
m.solve()
print(m.getObjValue(), m.getFlows())
```

More examples are in `tests/pyCmpl/`. Anyone using pyCmpl directly without `pyLogisticsLab` has to set `CMPLHOME` themselves. Errors are reported as `ll.LogLabException`. Progress messages go through the `logging` module (logger `pyLogisticsLab.*`) and not through `print`. To see them, call `logging.basicConfig(level=logging.INFO)`.

## Server

The server is in `logisticsLabServer/` and is started **from this directory**, because its modules import each other directly. It reads its configuration from `confs/logisticsLabServer.yml` and `confs/logisticsLab.yml` and writes its logs to `logs/`.

```bash
cd logisticsLabServer
python manageKeys.py add my-test            # create a key once and note it down
uvicorn main:app --host 127.0.0.1 --port 8000
```

For development `fastapi dev main.py` also works (reloads on changes). `fastapi dev` is not meant for production.

### Course of a request

Optimisation problems run asynchronously. The client submits the problem, gets an `id` and polls the result until the status is `solution`, `noSolution`, `error` or `cancelled`. Each problem is solved in a solver process of its own, so it can be cancelled via `/v1/cancel`, even while it is running.

```bash
KEY=...   # from manageKeys.py
curl -s -X POST http://127.0.0.1:8000/v1/tpp -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
     -d '{"varCosts": [[3,2],[1,4]], "supplies": [10,10], "demands": [8,8]}'
# {"id": "6f1c…", "status": "waiting", "message": "Problem is waiting in queue"}

curl -s -X POST http://127.0.0.1:8000/v1/results -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
     -d '{"id": "6f1c…"}'
# {"id": "6f1c…", "status": "solution", "message": "...", "results": {"objVal": 24.0, "solvingTime": 0.04, ...}}
```

A final result is deleted once it has been fetched. Results that are not fetched are deleted by the server after `maxInactivityTime`.

A service thread also cleans up regularly (every `serviceIntervall` seconds):

- **Abandoned problems:** If a client does not ask for the status of a waiting or running problem for longer than `maxPollingPause`, the problem is cancelled (`cancelled`). Clients therefore have to call `/v1/results` at least every `maxPollingPause` seconds.
- **Hanging solvers:** A watchdog terminates every problem that computes longer than `maxSolvingTime` + `runTimeGrace`. Without `maxSolvingTime`, `defaultMaxRunTime` + `runTimeGrace` applies, or `maxRunTime` of the problem type, if set. The problem then ends with `error` and HTTP status 504.

### Endpoints

All endpoints are `POST` and expect JSON. Unknown fields are rejected with 422.

| Endpoint | Purpose | Service for key permissions |
|---|---|---|
| `/v1/tsp` | travelling salesman: `distances` or `coordinates` | `tsp` |
| `/v1/tpp` | transportation problem: `varCosts` or `sourceCoordinates` + `destinationCoordinates`, plus `supplies`, `demands`; optional fixed costs, capacities, ranges, `objSense` (`min`/`max`/`minimax`), single source, blocking | `tpp` |
| `/v1/wlp` | warehouse location: `varCosts` (cost rate per unit of demand) or coordinates, `fixedCosts`, `demands`; with `isCapacitated` also `supplies` | `wlp` |
| `/v1/pmedian` | p-median: `p`, `varCosts` or coordinates; optional `demands`, `supplies`, `isDemandWeighted`, `isCapacitated` | `pmedian` |
| `/v1/pcentre` | p-centre (minimises the largest distance): fields as for p-median | `pcentre` |
| `/v1/contpmedian` | continuous p-median (locations can be chosen freely, great-circle distance in km): `p`, `coordinates` of the customers, optional `demands`, `capacities` (a number or p numbers; without: uncapacitated), `isSingleSource` (default `true`), `nrOfStarts` (default 20) | `contpmedian` |
| `/v1/contpcentre` | continuous p-centre: fields as for `contpmedian` | `contpcentre` |
| `/v1/scp` | set covering: `distances` or coordinates, `radius`; optional `fixedCosts` (default 1, i.e. as few locations as possible) | `scp` |
| `/v1/mcp` | maximal covering: `distances` or coordinates, `radius`, `demands`, `maxSrcCost` (budget for the fixed costs of the locations; with `fixedCosts` 1 the number) | `mcp` |
| `/v1/cpp` | Chinese postman: `edges` (`[[i, j], ...]`), `edgeWeights`, `startNode`; optional `edgeTypes` (0 directed, 1 undirected, default 1) | `cpp` |
| `/v1/vrp` | vehicle routing: `distances` or `coordinates` (all nodes including the depot), `demands`, `capacities` (per vehicle), `depot`; optional `times`, `timeWindows`, `serviceTimes`, `maxTime`, `maxDist`, `maxWaitingTime`, `maxSolvingTime` | `vrp` |
| `/v1/mincostflow` | min-cost flow: `edges`, `costs` per edge, `supplies`, optional `demands`, `minCaps`, `maxCaps`, `fixedCosts` per edge (incurred if the edge carries flow; makes the problem a MIP, with `mipGap`) | `mincostflow` |
| `/v1/maxflow` | maximum flow: `edges`, `source`, `sink`, `maxCaps`, optional `minCaps`, `nrOfNodes` | `maxflow` |
| `/v1/multicommodity` | multi-commodity flow: `edges`, `costs` [edges × commodities], `supplies`/`demands` [nodes × commodities], optional shared `minCaps`/`maxCaps` per edge, `capacityFactors` [edges × commodities] | `multicommodity` |
| `/v1/multistagewlp` | multi-stage WLP (fixed-charge transshipment problem): sources → warehouses in one or more stages → customers. `edges`, `costs`, `supplies`, optional `demands`, `nodeFixedCosts` (opening costs, nodes with costs > 0 are warehouses), `nodeMaxCaps` (capacity of a warehouse), `nodeMinCaps` (minimum throughput of an open warehouse), `minCaps`, `maxCaps`, `fixedCosts` per edge, `isSingleSource` (default `false`: whoever is supplied by warehouses gets the goods from exactly one warehouse), `balance`, `shortageCosts`, `mipGap` | `multistagewlp` |
| `/v1/multimodal` | multimodal flow: `edges`, `costs` [edges × modes] (`null`: mode not available on this edge), `supplies`, optional `demands`, `fixedCosts`, `minCaps` (minimum quantity if used), `maxCaps` | `multimodal` |
| `/v1/solve` | any problem, selected via the field `type` (`"tsp"`, `"tpp"`, `"wlp"`, `"pmedian"`, `"pcentre"`, `"contpmedian"`, `"contpcentre"`, `"scp"`, `"mcp"`, `"cpp"`, `"vrp"`, `"mincostflow"`, `"maxflow"`, `"multicommodity"`, `"multimodal"`, `"multistagewlp"`) | depending on `type` |
| `/v1/results` | status or result for an `id` | – |
| `/v1/cancel` | cancel a waiting or running problem (`{"id": ...}`); the status changes to `cancelled` shortly afterwards | – |
| `/v1/matrix` | matrix from coordinates: `matrixMode` `distances` (m), `durations` (s), `costs`, `both` (distances and times) or `all`, optional `sources`, `destinations`, `rounded` and the matrix options (see below) | `matrix` |
| `/v1/routing` | route via several coordinates | `routing` |
| `/v1/coordinates` | coordinates `[lat, lon]` for `adresses`, optional `limit` (hits per address, 1–10), `countrycodes` (e.g. `["DE"]`), `near` (`[lat, lon]`, nearby hits first). Answer: `coordinates` (first hit, `null` without a hit) and `hits` (per address a list with `coordinates`, `name`, `street`, `postcode`, `city`, `country`, `countrycode`, `server`) | `geocoding` |
| `/v1/search`, `/v1/reverse` | hits for an address (`adress`) or address for a coordinate (`coordinate`), `results` is empty without a hit | `geocoding` |

The results of all problems start with `objVal` and `solvingTime`, followed by the problem-specific fields. Coordinates are passed as `[lat, lon]`. All indices are **0-based**, i.e. the position in the passed list or the row of the matrix. `-1` means “none”.

| Type | Result fields |
|---|---|
| `tsp` | `route` (sequence of nodes) |
| `tpp` | `flows` (matrix), `totalCosts`, `totalVarCosts`, `totalFixedCosts`, `totalFlow`, `sourceFlows`, `destinationFlows`, `minCostRate`, `maxCostRate` |
| `wlp`, `pmedian`, `pcentre` | `activeSources` (0/1 per source), `assignments` (supplying source per sink) |
| `contpmedian`, `contpcentre` | `locations` (`[lat, lon]` per location), `assignments` (location with the largest flow per customer), `customerDistances` (km, if split, to the most distant supplying location), with `isSingleSource: false` also `flows` [locations × customers] |
| `scp`, `mcp` | `activeSources`, `coveringSources` (all open sources within the radius per sink), `assignments` (the nearest of them; for `mcp` `-1` for uncovered sinks) |
| `cpp` | `eulerTour` (sequence of nodes), `edgeUsages` (usages per passed edge) |
| `vrp` | `routes`, `routeLoads`, `routeDistances` per vehicle; with times (`times` or from `coordinates`) the schedule per stop: `routeArrivals` (arrival), `routeWaitingTimes` (waiting because of time windows), `routeTimes` (start of service), `routeServiceTimes`, `routeTravelTimes` (travel time from the previous stop). Without time windows and `maxTime` every route starts at 0 and does not wait. Unused vehicles have the route `[depot, depot]` |
| `mincostflow`, `maxflow` | `flows` per edge; for `maxflow` `objVal` is the maximum flow; `mincostflow` with `fixedCosts` additionally `usages` (0/1 per edge), `totalVarCosts`, `totalFixedCosts` |
| `multicommodity` | `flows` [edges × commodities] |
| `multimodal` | `flows` and `usages` (0/1) [edges × modes], `totalVarCosts`, `totalFixedCosts` |
| `multistagewlp` | `flows`, `usages` (0/1) per edge, `openNodes` (1 open, 0 closed per warehouse, otherwise `null`), `nodeFlows`, `totalVarCosts`, `totalFixedCosts` (edges), `totalOpeningCosts` |

For the network flows:
- **Nodes and edges:** Nodes are indices from 0, edges are pairs `[i, j]`.
- **Unlimited capacities:** `null` or `"M"`.
- **Balancing (`balance`):**
  - `"auto"` (default): as for TPP. With excess supply, supply remains unused at the sources. With excess demand, the whole supply is delivered and part of the demand remains unmet. `shortageCosts` sets costs per undelivered unit per node, default 0. Applies to all flows except `maxflow`.
  - `"exact"`: Total supply and total demand have to be equal, for `multicommodity` per commodity. Otherwise 400 is returned.
- **Node capacities:** `nodeMinCaps`/`nodeMaxCaps` limit the flow through each node, including its own supply and demand, e.g. at a transshipment point. For `multicommodity` the limit applies to all commodities together. For `multimodal` there are only `nodeMaxCaps`, because minimum quantities there only apply to used modes.
- **Implementation:** Internally the library splits a node with capacity into an input and an output node. Dummy nodes take up the excess. The results refer only to the original nodes and edges.
- **Related results:** with node capacities `nodeFlows`. If an excess was balanced, `unusedSupplies`, `unmetDemands` and `totalShortageCosts` are added, each per node, for `multicommodity` per node and commodity.
- **Parallel edges:** None of the flow models allows parallel edges between the same nodes. Several transport routes are modelled via `multimodal` with modes.
- **Solver:** All four run via CMPL and HiGHS (`minCostFlow.cmpl`, with fixed costs `minCostFlowFixed.cmpl`, `maxFlow.cmpl`, `multiCommodity.cmpl`, `multimodal.cmpl` in `pyLogisticsLab/`).
- **Fixed costs:** For `mincostflow`, `minCaps` remains a fixed minimum quantity. An edge with `minCaps > 0` is therefore always used and incurs its fixed costs. For `multimodal`, on the other hand, the minimum quantity only applies if the mode is used.
- **Unbounded max flow:** If there is a path from `source` to `sink` only over unlimited edges, 400 is returned.

For the continuous location problems:
- **Distance:** great-circle distance in km, not the road network. The customers have to lie on one hemisphere.
- **Objective:** `contpmedian` minimises the sum of demand × distance, `contpcentre` the largest distance of a customer to a supplying location. For the uncapacitated `contpcentre` the demands do not count.
- **Capacities:** With `capacities`, `demands` are mandatory. `isSingleSource: true` assigns each customer to exactly one location, `false` allows its demand to be split.
- **Method:** heuristic, not provably optimal. It starts with the discrete `pmedian`/`pcentre` with the customers as candidates, then alternates location choice (spherical Weiszfeld or smallest enclosing spherical cap) and assignment (nearest location or `Tpp.cmpl` with capacities), then further random starts within `nrOfStarts` and `maxSolvingTime`.

On geocoding:
- **No hit:** `null` or an empty list, never `[0, 0]`. That would be a valid point in the Atlantic and would silently end up in matrices.
- **`countrycodes`:** Nominatim filters on the server. Photon has no country filter, there the fetched hits (at most 10) are filtered. If none of them is in the country, the list is empty.
- **`near`:** prefers hits nearby without replacing the relevance. Photon weights them itself, with a radius of some 10 km (`zoom=10`), with Nominatim a preferred map section of about 50 km around the point applies (`viewbox`). More distant hits remain possible. `countrycodes` is meant for a hard exclusion.

### Matrices from coordinates

All problems with coordinates (`tsp`, `tpp`, `wlp`, `pmedian`, `pcentre`, `scp`, `mcp`, `vrp`) and `/v1/matrix` compute their matrix in one place (`logisticsLabCore/matrixService.py`). The client does not need to manage matrices.

| Field | Default | Meaning |
|---|---|---|
| `matrixMode` | `distances` | `distances` (m), `times` (s) or `costs`; for `vrp` always distances, with `timeWindows`/`maxTime` also times |
| `travelmode` | `car` | `car`, `foot`, `wheelchair`. The OSM servers of TH Wildau currently only offer `car`. |
| `matrixSource` | `osm` | `osm`: road network of the OSM servers. `beeline`: straight-line distance × `detourFactor`, without any OSM server |
| `detourFactor` | 1.0 | only `beeline`: 1 is the distance as the crow flies; roads are typically 1.2–1.4 |
| `averageSpeed` | car 50, foot 5, wheelchair 4 | km/h, only `beeline`, for the travel times |
| `timeFactor` | 1.0 | factor on all travel times, e.g. 1.2 for trucks |
| `costPerKm`, `costPerHour` | – | for `matrixMode: costs`: costs = km × `costPerKm` + h × `timeFactor` × `costPerHour`; at least one is required |
| `noCache` | false | `true` reloads the matrix from the OSM servers and renews the cache entry |

- **Rounding:** Distances and times are rounded to integers, costs to 2 decimal places. For `/v1/matrix` this only happens with `rounded: true`.
- **Cache:** The raw data of the OSM servers (metres and seconds) are kept in an SQLite file. The factors are applied only afterwards. An entry therefore applies to all cost rates and time factors, and other factors do not trigger a new OSM request.
  - **Data version:** The key of an entry contains the data version of the ORS servers (`graph_build_date` from `/ors/v2/status`). Each process queries it at most once per hour. After an update of the servers, old entries are no longer used and are gradually displaced. If a server does not answer, the last known version applies.
  - **Measured:** For 200 points 13.6 s via OSM, 0.01 s from the cache.
  - **Size:** An entry with 200 × 200 takes about 0.34 MB.
  - **Privacy:** The cache stores the coordinates of the requests, as key only in hashed form. Only someone sending exactly the same coordinates gets a matrix.
- **`matrixInfo`:** is part of the result as soon as a matrix has been computed from coordinates.
  - `source`: `osm`, `cache` or `beeline`.
  - `status`: `exact`, `unexact` or `beeline`. With `unexact` the OSM server returned no route or an implausible value for some pairs of points. These values are estimated with straight-line distance × average detour, the factors are in `fillFactors`.
  - `matrices`: which matrices were computed, plus the factors used.
  - `osmDate`: version of the OSM data the matrix is based on.

If the matrix is computed from coordinates, it is also part of the result (`varCosts`, `distances`, or for `vrp` `distances` and `times`). For `vrp` all numbers are rounded, because OR-Tools requires integers. From coordinates, `vrp` loads the travel times only if `timeWindows` or `maxTime` are set.

If `docs: True` is set, the full description of all fields is available under `/docs`.

### Access with API keys

Every request needs the header `X-API-Key`. The keys are managed by `manageKeys.py` in the server directory:

```bash
python manageKeys.py add DSS-WS2026 --expires 2027-03-31 --allowed tsp,tpp --maxOpenProblems 3
python manageKeys.py list
python manageKeys.py disable DSS-WS2026     # block
python manageKeys.py enable DSS-WS2026
python manageKeys.py remove DSS-WS2026
```

- `add` shows the key **only once**. `apiKeys.yml` contains only its SHA-256 hash. The file is created with permissions `600` and is not versioned.
- The server reloads `apiKeys.yml` automatically when it changes. Blocking and new keys therefore take effect without a restart.
- A key belongs to a name, e.g. a course or a person. The name appears in the log, and only the key that submitted a problem can fetch its result.
- Without `--allowed` a key may use all services: the problem types (`tsp`, `tpp`, `wlp`, `pmedian`, `pcentre`, `contpmedian`, `contpcentre`, `scp`, `mcp`, `cpp`, `vrp`, `mincostflow`, `maxflow`, `multicommodity`, `multimodal`, `multistagewlp`) and `matrix`, `routing`, `geocoding`. Keys with their own `--allowed` list do not get new services automatically.
- With `authentication: False` the server is open without a key. This is only meant for local development.

### Responses on rejection

| Status | Meaning |
|---|---|
| 401 | key missing, wrong, expired or blocked |
| 403 | key may not use this service |
| 422 | request does not match the schema (field missing, wrong type, unknown field) |
| 429 | key already has `maxOpenProblems` waiting or running problems – fetch results first |
| 503 | queue is full (`maxQueueSize`) – try again later |
| 400 | data do not fit (e.g. wrong matrix size) or `id` unknown |
| 404 | problem was solved but has no feasible solution (`noSolution`) |
| 504 | problem exceeded the time limit of the watchdog and was terminated |

### Configuration (`confs/logisticsLabServer.yml`)

| Option | Default | Meaning |
|---|---|---|
| `maxProblems` | 4 | solver processes, i.e. problems solved at the same time |
| `maxQueueSize` | 50 | waiting and running problems of all keys together |
| `maxOpenProblemsPerKey` | 3 | default for keys without their own `maxOpenProblems` |
| `maxInactivityTime` | 3600 | seconds after which unfetched results are deleted |
| `maxPollingPause` | 600 | seconds without a status request after which an open problem is cancelled (0: off) |
| `serviceIntervall` | 30 | seconds between two clean-up runs |
| `runTimeGrace` | 60 | buffer in seconds on `maxSolvingTime` for the watchdog |
| `defaultMaxRunTime` | 600 | time limit of the watchdog in seconds for problems without `maxSolvingTime` (e.g. TSP), plus `runTimeGrace` |
| `authentication` | True | API keys required |
| `apiKeyFile` | `confs/apiKeys.yml` | path to the key file |
| `docs` | False | offer `/docs`, `/redoc` and `/openapi.json` |
| `logging`, `debugging` | True, True | log levels INFO/WARNING/ERROR or additionally DEBUG |
| `logPath` | `logs/` (`LOGLAB_LOG_DIR`) | directory for all log files |
| `logMaxBytes`, `logBackupCount` | 5 MB, 5 | rotation of `logisticsLabServer.log` |
| `matrixCache` | True | cache of the OSM matrices |
| `matrixCacheFile` | `matrixCache.sqlite` in `logPath` | cache file, shared by all solver processes |
| `matrixCacheMaxAge` | 180 | days, safety net. After an update of the ORS servers the entries are not used anyway. |
| `matrixCacheMaxEntries` | 500 | maximum number of entries, the longest unused are deleted first |
| `<type>.maxNodes` | tsp/vrp 100, tpp/wlp/pmedian/pcentre/contpmedian/contpcentre 200, scp/mcp/cpp/multimodal/multistagewlp 300, multicommodity 500, mincostflow/maxflow 2000 | maximum problem size: sources + sinks, for the other types the nodes |
| `<type>.maxSolvingTime` | 300, vrp 60, mincostflow/maxflow 120 | upper limit in seconds for the solving time requested by the client (for `vrp` the search time of OR-Tools) |
| `<type>.maxRunTime` | – | fixed time limit of the watchdog for this problem type (replaces the calculation above) |

`port` is currently not evaluated. The port is set by the uvicorn start command.

### Log files

All log files end up in `logPath`:

- `logisticsLabServer.log`: requests, results (one line per problem with size, status, objective value and runtime), rejections and errors, each with the key name
- `logisticsLab.log`: accesses to the OSM servers (CSV)
- `matrixCache.sqlite` (with `-wal`/`-shm`): cache of the OSM matrices, see above
- `HiGHS.log`: output of the solver. `logPath` is also the working directory of the solver processes, so all other files of CMPL and the solvers end up there as well.

For production set `debugging: False`, otherwise every status request while waiting is logged as well.

## Local interface for desktop apps

A desktop app (e.g. Flutter on Windows, macOS or Linux) can compute locally without a server. To do so it starts the local interface as a child process and talks to it via stdin/stdout ([JSON-RPC 2.0](https://www.jsonrpc.org/specification), one message per line, UTF-8). There is no port, no firewall prompt and no API keys. The process lives as long as the app.

```bash
python -m logisticsLabCore.stdio [--logPath DIR] [--osmConfig FILE] [--maxProblems N] [--debug] [--noMatrixCache]
```

- **`--logPath`:** directory for log files and `HiGHS.log`. Default is `logs/` or `LOGLAB_LOG_DIR`. The app should pass its support directory.
- **`--osmConfig`:** OSM servers. Default is `confs/logisticsLab.local.yml`, if present, otherwise the servers of TH Wildau from `confs/logisticsLab.yml`.
- **Matrix cache:** The cache is in `--logPath` (`matrixCache.sqlite`), `--noMatrixCache` turns it off. Without network the app computes with `matrixSource: "beeline"`.
- **End:** The process ends when stdin is closed or after `shutdown`. Running solvers are terminated with it.
- **Clean-up:** The watchdog for hanging solvers is also active locally. Unfetched results are deleted after 12 hours. Abandoned problems are not cancelled locally, because when the app ends, the process ends too.
- **stdout belongs to the protocol only.** All other output, including that of CMPL and HiGHS, goes to stderr.

Data formats and results are the same as for the REST server. The methods correspond to the endpoints:

| Method | Parameters | Result |
|---|---|---|
| `solve` | problem with `type` (all types of `/v1/solve`), as for `/v1/solve` | `{id, status, message}` |
| `status` | `{id}` | `{id, status, message}` |
| `result` | `{id}` | as `/v1/results`; a finished problem is deleted afterwards |
| `cancel` | `{id}` | `{id, status, message}` |
| `matrix`, `routing`, `coordinates`, `search`, `reverse` | as the REST endpoints | `{message, ...}` |
| `version` | `{}` | `{version, protocol}` |
| `shutdown` | `{}` | `{}` |

The process also sends messages on its own. Polling in a loop as with the REST server is not necessary.

| Notification | Parameters | when |
|---|---|---|
| `ready` | `{version, protocol}` | after the start, from then on requests are accepted |
| `jobStatus` | `{id, status, message}` | on every status change: `waiting` → `running` → `solution` / `noSolution` / `error` / `cancelled` |

```json
→ {"jsonrpc":"2.0","id":1,"method":"solve","params":{"type":"tpp","varCosts":[[3,2],[1,4]],"supplies":[10,10],"demands":[8,8]}}
← {"jsonrpc":"2.0","id":1,"result":{"id":"6f1c…","status":"waiting","message":"Problem is waiting in queue"}}
← {"jsonrpc":"2.0","method":"jobStatus","params":{"id":"6f1c…","status":"running","message":"Problem is running"}}
← {"jsonrpc":"2.0","method":"jobStatus","params":{"id":"6f1c…","status":"solution","message":"Solution has been found"}}
→ {"jsonrpc":"2.0","id":2,"method":"result","params":{"id":"6f1c…"}}
← {"jsonrpc":"2.0","id":2,"result":{"id":"6f1c…","status":"solution","message":"…","results":{"objVal":24.0,…}}}
```

Errors come as JSON-RPC errors. `data.httpStatus` corresponds to the status the REST server would return. The app can therefore treat both ways the same:

| Code | Meaning | `data` |
|---|---|---|
| -32700 / -32600 | not a valid JSON or JSON-RPC message | – |
| -32601 | unknown method | – |
| -32602 | parameters do not match the schema | `{httpStatus: 422, errors: [...]}` |
| -32000 | error of a problem or geo service, e.g. unknown `id` | `{httpStatus: 400, ...}` |
| -32603 | internal error | – |

### Notes for the Flutter app

- **Common interface:** In Dart create an abstract class (e.g. `LogisticsLabBackend` with `submit`, `status`, `result`, `cancel`) with two implementations. `LocalBackend` starts the process with `Process.start` from `dart:io` and reads stdout line by line (`utf8.decoder` + `LineSplitter`). `RemoteBackend` talks to the server via HTTP and sends the API key. Web and mobile use only `RemoteBackend`, because processes cannot be started there.
- **Data models:** `python -m logisticsLabCore.schema > logisticsLab.schema.json` generates the JSON Schema of all requests and responses. The Dart models can be generated from it, e.g. with `quicktype --lang dart`. Server and local interface use the same items.
  - **Requests:** the problem items (`ContPCentreItem` …) and the geo items.
  - **Responses:** `ProblemAnswer` (`{id, status, message, results}`) and per problem type a result model for `results`. The mapping is in `RESULT_ITEMS` in `logisticsLabCore/results.py`, e.g. `contpmedian`/`contpcentre` → `ContLocationResults`, `mincostflow`/`maxflow` → `FlowResults`. `checkServer.py` checks every real response against these models, so a new or renamed result field is noticed.
- **Example client:** `tests/dartClient` is a runnable Dart package without external dependencies. It contains `LogisticsLabBackend` with `LocalBackend` (child process, JSON-RPC) and `RemoteBackend` (REST, polling of `/v1/results`), typed results in `lib/src/results.dart` and the example `bin/cont_pcentre.dart`. In both cases errors come as `LogisticsLabException` with `httpStatus`. For the Flutter app `lib/` can be taken over directly.
- **Python client:** `tests/pythonClient` shows the same in Python, using only the standard library. `logisticsLabClient.py` contains `LocalBackend` and `RemoteBackend` with `solve`, `submit`/`wait`/`result`, `cancel` and `geo`. `rawProtocol.py` shows the protocol without a helper module, every message is printed.
- **Packaging:** `python3 dist/buildDist.py` builds a distribution that runs without installation. It contains a bundled Python, all libraries, the CMPL core and HiGHS, see `dist/README.md`. The app starts `bin/python/bin/python3 -I -m logisticsLabCore.stdio --osmConfig confs/logisticsLab.yml` from it (Windows: `bin\python\python.exe`), or it ships the program compiled with Nuitka from `dist/buildStdio.py`. On macOS every bundled executable has to be signed, `--sign` takes care of that. For an app in the sandbox the child process also needs the entitlements `com.apple.security.inherit` and `com.apple.security.network.client`.

## Scenario format and command line tool

A scenario describes a logistics network once. Any number of problems can be computed on it, e.g. TPP, WLP, VRP and min-cost flow on the same nodes. An example is `tests/scenarios/brandenburg.llab`. The data models are in `logisticsLabCore/scenario.py`. They are part of the JSON Schema (`python -m logisticsLabCore.schema`). The full description of both formats, `.llab` and `.llsol`, with all fields and parameters per problem type is in [docs/dateiformate.md](docs/dateiformate.md) (in German).

```json
{ "format": "logisticsLab", "version": 1, "id": "brandenburg",
  "units": { "distance": "km", "time": "min" },
  "matrix": { "matrixSource": "osm", "travelmode": "car", "costPerKm": 0.5, "costPerHour": 30 },
  "nodes": [ { "id": "W", "coordinates": [52.30, 13.26], "roles": ["supplier"], "supply": 100 }, "..." ],
  "networks": { "supply": { "directed": true, "edges": [ { "from": "W", "to": "D1", "capacity": 100 } ] } },
  "vehicles": [ { "id": "Truck", "capacity": 60, "count": 2, "depot": "D1" } ],
  "problems": [ { "name": "Warehouse locations", "type": "wlp", "parameters": { "isCapacitated": true } } ] }
```

**Files:** Scenarios have the extension **`.llab`**, solution documents **`.llsol`**. Both are JSON inside.
- **Detection by content:** The tool also accepts other extensions. What matters is the field `format` (`logisticsLab` or `logisticsLabSolution`).
- **Own extension:** With it the desktop app can open the files by double-click and filter them in the file dialog. `.ll` is taken by LLVM.
- **VS Code:** Enter in `.vscode/settings.json` (project or user):

```json
"files.associations": { "*.llab": "json", "*.llsol": "json" },
"json.schemas": [ { "fileMatch": ["*.llab"], "url": "./.vscode/logisticsLab-scenario.schema.json" } ]
```

  The schema file is generated by `python -m logisticsLabCore.schema --scenario > .vscode/logisticsLab-scenario.schema.json`. VS Code then checks scenarios while editing and offers completion. A scenario may also have a field `"$schema"`.

**Rules:**
- **Coordinates:** Every node has geographic coordinates `[lat, lon]`. The address (`address` or `addressDetails`) is optional.
- **Distances and travel times:** come only from the OSM servers, via the matrix cache, or as straight-line distance (`matrixSource: beeline`). There are no own matrices in the scenario.
- **Costs:** are derived: km × `costPerKm` + h × `timeFactor` × `costPerHour`, for customers times `costFactor`. `matrixMode` of a problem selects `distances`, `times` or `costs`.
- **Units:** `units` sets the units, `distance` m or km, `time` s, min or h. `costPerKm` and `costPerHour` always refer to km and h.
- **Roles:** determine what a problem reads.
  - `supplier` → `customer`: TPP.
  - `candidate` → `customer`: WLP, p-median, p-centre, SCP, MCP.
  - `supplier` → `candidate` → … → `customer` via a network: multi-stage WLP (`multistagewlp`). The warehouses are `candidate` with `capacity` (throughput, otherwise `maxCap`), `fixedCost` (opening costs) and optionally `minCap`. The edges have `capacity`, `minFlow` (only if used) and `fixedCost`. With `isSingleSource: true` every customer and every warehouse of a later stage gets the goods from exactly one warehouse. The warehouses are nodes and are not split into input and output by hand. As with all scenarios, the costs come from OSM distance and travel time.
  - `customer` alone: continuous locations (`contpmedian`, `contpcentre`). The locations are the result and not nodes. Their number is the parameter `p` (mandatory), their capacities the parameter `capacities`: one value for all or a list with `p` values, only with `isCapacitated` (default: `true` if `capacities` is given). In the solution they are called `F1` … `Fp`. The former role `facility` no longer exists, a file using it is rejected with a hint.
  - `depot`: VRP.
- **Networks** (`networks`): define the allowed connections, with capacity, minimum flow, fixed costs and direction per edge. Their length and travel time come from OSM.
  - `networkMode: edges`: only these edges are allowed. For TPP and location problems the other pairs are then blocked.
  - `networkMode: shortestPaths`: A complete matrix of the shortest paths over the network is created. For TSP the solution contains the whole path (`path`).
  - Flows and CPP need a network. `minCap`/`maxCap` of a node limit the throughput, including its own supply and demand. `capacity`, on the other hand, is the capacity of a location in the location problems.
  - Unequal total supplies and demands are balanced (`"balance": "auto"`, default). With `"balance": "exact"` there is an error instead. Undelivered quantities cost `shortageCost` per sink, default 0.
- **Further node attributes:** `minSupply`/`maxSupply`, `minDemand`/`maxDemand` (effective with `useSupplyRanges`/`useDemandRanges`), `timeWindow`, `serviceTime`, `active: false` (node is ignored), `shortageCost` (with `balance: auto`).
- **Commodities and modes:** for `multicommodity` and `multimodal`.
  - `commodities`: list of commodities with `costPerKm`, `costPerHour` and `capacityFactor`. The nodes have `supplies`/`demands` per commodity, the edges optionally different values under `commodities`.
  - `capacityFactors` at a node: capacity of `minCap`/`maxCap` that one unit of a commodity takes up, e.g. `{"P1": 2.5, "P2": 2}`. The default is 1, not the `capacityFactor` of the commodity. A transshipment point with different factors per commodity therefore does not need to be split into input and output by hand (library: `MultiCommodityFlow(nodeCapacityFactors=…)`).
  - `isInteger: true` as parameter of `multicommodity`: integer flows as a MIP, with `mipGap`. Without the parameter the LP is solved. For the multi-commodity flow its solution is in general not integer, even with integer supplies and demands: shared capacities of several commodities and capacity factors ≠ 1 break the total unimodularity of the single-commodity flow. Example: `logisticslab solve SCENARIO.llab --set isInteger=true`.
  - `modes`: list of modes with `costPerKm`, `costPerHour`, `fixedCost`, `minFlow` and `capacity`. An edge without `modes` allows all modes. With `modes` it allows only the ones listed, possibly with their own values.
  - Here, too, the costs come from OSM distance and travel time.
  - `fixed` and `assignedTo` are only stored so far. The problems do not take them into account yet, the result then contains a warning.

**Results** are documents of their own (`logisticsLabSolution`). They are not part of the scenario.
- **Reference:** Each document refers with `scenario.hash` to exactly one data version of the scenario and contains the problem with its parameters.
- **Contents:** `matrixInfo`, `valueUnit` (unit of the matrix values) and warnings. Plus `results` with `objVal`, `summary`, `nodes`, `assignments`, `routes` or `edges`, each via node IDs, and the previous fields under `native`.
- **VRP routes:** Each route has `vehicle`, `nodes`, `load` and `distance`. Per stop there are also `arrivals`, `waitingTimes`, `times` (start of service), `serviceTimes` and `travelTimes`. The totals are in `travelTime`, `waitingTime`, `serviceTime` and `duration`, all in `units.time`. The server computes the times from the time matrix, an app does not need the matrix for this.

**Command line tool:**

```bash
logisticslab show  tests/scenarios/brandenburg.llab
logisticslab solve tests/scenarios/brandenburg.llab                        # all problems, output on screen
logisticslab solve SCENARIO.llab --problem "Tours from Wildau" --set maxSolvingTime=30
logisticslab solve SCENARIO.llab --out --quiet                             # only as file SCENARIO.llsol
logisticslab solve SCENARIO.llab --out solutions.llsol                     # file with its own name
logisticslab solve SCENARIO.llab --json                                    # solution documents on screen
logisticslab solve SCENARIO.llab --server https://logisticslab.example.org/v1/ --apiKey ...
logisticslab --help                                                        # without installation: python -m logisticsLabCli ...
```

- **Computing:** Without `--server` the tool computes locally with the core and the OSM servers from `confs/logisticsLab.yml`, with logs and matrix cache in `logs/cli` (`--logPath`). With `--server` it sends matrix and problem requests to a LogisticsLab server. Nothing has to be changed on the server for this, because the tool translates the scenarios into the existing `/v1` requests.
- **Overriding parameters:** `--set NAME=VALUE` applies to the parameters of the problems, e.g. `p`, `maxSolvingTime`, `matrixMode`.
- **Exit code:** 1 if a problem ends with an error.

### Converting old LogisticsLab files

```bash
logisticslab convert OLD_FILE.TPPX                                       # -> old_file.tppx.llab next to it
logisticslab convert --dir LogisticsLab-Daten/Modelle-Ors --target LogisticsLab-Daten/Szenarien
```

- **Formats:** TPPX → `tpp`, DLPX → `wlp`/`pmedian`/`pcentre`/`mcp`, CLPX → `contpmedian`/`contpcentre`, NWFX → `mincostflow`, TSPX → `tsp`/`cpp`, VRPX → `vrp`. The options of the file become the parameters of the problem.
- **CLPX:** The sources do not become nodes. Their number becomes `p`, with `Capacitated` their capacities become `capacities`: one value if all are equal. The continuous problems do not support fixed sources and customers with a fixed assignment to a source, these are not taken over.
- **Skipped:** files with own matrices (`DistFunc OwnDef`) or planar coordinates (`Map SimpleMap`).
- **Stored matrices** are not taken over. Exceptions: `M` in `COSTS` (blocked connection), `CAPACITIES` and `FIXEDCOSTS` become a network `connections`.
- **Order:** In the old files `x` = longitude, `y` = latitude. The conversion writes `[lat, lon]`.
- **`DistFunc` decides on the matrix:** `GreatCircle…` results in straight-line distance, `OSM/…` in the road network, also with `TravelMode Bird`. `DistFactor` becomes `costPerKm` or `costPerHour`.
- **Identifiers:** Sources and destinations with the same name at the same place become one node with both roles. Equal names at different places get `#2`, `#3` …
- **Writing files only:** `logisticslab convert` (`logisticsLabCore/convertX.py`) only creates scenarios (`.llab`) and does not compute. Solving is done with the command line tool.

## Operation on Linux with nginx

nginx handles TLS, rate limiting and the size limit. uvicorn is only reachable locally. The paths below are examples.

**Important:** Start uvicorn with **exactly one** worker process. Queue and results are kept in the memory of the process. With several workers `/results` would often not find the `id`. `maxProblems` takes care of parallelism.

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
Environment=LOGLAB_CONF_DIR=/etc/logisticsLab
Environment=LOGLAB_LOG_DIR=/var/log/logisticsLab
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
# 10 requests/s per IP – enough for polling the result every 0.2 s
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

    client_max_body_size 2m;       # limit large matrices

    location /v1/ {
        limit_req zone=loglab burst=20 nodelay;
        limit_req_status 429;

        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;   # matrix and routing requests run synchronously
    }

    location / {
        return 404;
    }
}
```

The certificate can be obtained e.g. with `certbot --nginx -d logisticslab.example.org`. From outside only the ports 80/443 (and 22) have to be open. Port 8000 stays closed.

## Tests

**Library** (`tests/pyCmpl/`):
- `find*.py`: examples that call a model directly and print the result.
- `checkLibrary.py`: regression test of all models. It compares the objective values with expected values, checks typical error cases and ends with exit code 1 if something fails.

```bash
python tests/pyCmpl/checkLibrary.py
```

**Core** (`tests/coreTests/`): `checkMatrixService.py` checks the matrix cache without OSM servers. It checks loading, reuse, restart, `noCache`, expiry, a simulated update of the ORS servers and the hourly status request, plus the cost formula and straight-line distance. Finally it reads the data version of the configured servers, if they are reachable.

```bash
python tests/coreTests/checkMatrixService.py
```

**Server examples** (`tests/serverExamples/`): a standalone script per problem type and geo service, e.g. `wlpExample.py`, `contPCentreExample.py`, `matrixExample.py`. Address, key, data, submission, polling of the results and output are directly in the code, without a helper module. The scripts are suitable as templates for own clients.
- **Example key:** The scripts use the fixed key `loglab-local-example-key`. The header `X-API-Key` always contains the key itself, the server only knows its hash.
- **Registering:** `python tests/serverTests/createTestKeys.py` enters the hash under the name `localExample` into the local `apiKeys.yml`. With `--keyFile` for another server the script refuses the example key, because it is public in the repo.
- **Starting:**

```bash
python tests/serverTests/createTestKeys.py         # once: create example and test keys
cd logisticsLabServer && ./run_server.sh           # local server on port 8000
python tests/serverExamples/contPCentreExample.py  # in a second terminal
```

**Server tests** (`tests/serverTests/`):
- `find<Type>Server.py`: example per problem type. The data are in `payloads`. Sending, fetching and displaying the solution (`showResults`) is done by `logLabClient.py`.
- `getMatrixServer.py`, `getRouteServer.py`, `getGeoCodingCoords.py`, `getGeoCodingSearch.py`, `getGeoCodingReverse.py`: examples for the geo endpoints `/v1/matrix`, `/v1/routing`, `/v1/coordinates`, `/v1/search` and `/v1/reverse`, also with key via `logLabClient.py`.
- `checkServer.py`: regression test over all examples. It checks:
  - the objective values and the same result via `/v1/solve`,
  - every response against the result schema,
  - error cases with their HTTP status,
  - a key without the permissions for `contpcentre` and `matrix`,
  - the geo endpoints and a TSP with a matrix from coordinates. These checks need the OSM servers from `logisticsLab.yml`. If they are not reachable, they are skipped.
- The servers of TH Wildau currently only offer the profile `car`. `foot` and `wheelchair` return 400 there.
- `runServerTests.sh`: does everything in one step. It creates new test keys, starts a local server on port 8000 if none is running, runs the tests and stops the server again. The log of the test server is in `logs/testServer.log`.

```bash
PYTHON=/opt/anaconda3/envs/pyLogisticsLab/bin/python tests/serverTests/runServerTests.sh                       # checkServer.py
PYTHON=/opt/anaconda3/envs/pyLogisticsLab/bin/python tests/serverTests/runServerTests.sh findContPCentreServer.py
```

**Test keys:** `createTestKeys.py` creates the keys `serverTests` (all services) and `serverTestsRestricted` (only `tsp`). Keys with the same name are replaced on every run.
- **Locations:** `confs/apiKeys.yml` contains only the hashes. The keys themselves are in `tests/serverTests/.env` (permissions `600`). Neither file is versioned.
- **Without export:** `logLabClient.py` and the Dart client read the `.env` themselves. Variables from the environment take precedence. Once the `.env` has been created, the scripts therefore run directly against a running server, e.g. `python tests/serverTests/findWlpServer.py`.
- **Removing:** `python tests/serverTests/createTestKeys.py --remove` deletes the keys and the `.env`.
- **Remote server:** Run the script there with its key file and copy the `.env` to the client:

```bash
python tests/serverTests/createTestKeys.py --keyFile /etc/logisticsLab/apiKeys.yml --url https://logisticslab.example.org/v1/
```

For the heuristics (`vrp`, `contpmedian`, `contpcentre`) a better value than expected also counts as passed.

**Dart client** (`tests/dartClient/`, Dart SDK 3.5 or later):

```bash
cd tests/dartClient
dart pub get
LOGLAB_PYTHON=/path/to/python dart run bin/cont_pcentre.dart local    # local interface as child process
dart run bin/cont_pcentre.dart remote                                 # server, LOGLAB_URL and LOGLAB_API_KEY from the .env
```

**Python client** (`tests/pythonClient/`): examples for the JSON-RPC communication with the local interface, analogous to the Dart client.
- **`logisticsLabClient.py`:** `LocalBackend` starts `python -m logisticsLabCore.stdio` as a child process. `RemoteBackend` talks to the REST server. Both have the same interface, errors come as `LogisticsLabException` with `httpStatus`.
- **`contPCentre.py`:** the same example as `cont_pcentre.dart`, with `local` or `remote`. For `remote` the key comes from `LOGLAB_API_KEY` or the `.env`.
- **`rawProtocol.py`:** the protocol without a helper module: `ready`, `solve`, `jobStatus`, `result`, `shutdown`, every message is printed.
- **`parallelAndCancel.py`:** several problems at the same time with status messages, a cancellation, a straight-line cost matrix and a rejected request (422).

```bash
python tests/pythonClient/rawProtocol.py
python tests/pythonClient/contPCentre.py local      # or remote
python tests/pythonClient/parallelAndCancel.py
```

**OSM servers directly** (`tests/osmTests/`): `get*.py` use the library `osm_data`, `ors*.py` query an OpenRouteService server directly via HTTP (coordinates `[lon, lat]`, no LogisticsLab key). These scripts test the OSM servers, not the LogisticsLab server.

## License

© 2026 Mike Steglich, Technical University of Applied Sciences Wildau

pyLogisticsLab is free software under the [GNU Affero General Public License v3](LICENSE) or any later version (AGPL-3.0-or-later). Anyone who offers a modified version as a network service, for example the REST server, must make the source code of the changes available to its users.

Third-party software: pyCmpl and CMPL (GPL v3), HiGHS (MIT), OR-Tools (Apache 2.0) and the Python packages from `pyproject.toml` with their own licenses. For contributions see [CONTRIBUTING.md](CONTRIBUTING.md).
