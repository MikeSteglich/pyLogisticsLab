# LogisticsLab-Dateiformate: Szenario (.llab) und Lösung (.llsol)

Stand: 21.10.2026 · Online-Fassung: [Claude Doc](https://claude.ai/artifact/HeaoXfv48BUs6MAHYMKRCV)

## Überblick

Ein Szenario (`.llab`) beschreibt ein logistisches Netz einmal – Knoten, Netze, Fahrzeuge, Güter – und darauf beliebig viele Probleme; ein Lösungsdokument (`.llsol`) enthält die Lösungen dieser Probleme. Beide Dateien sind JSON in UTF-8.

| | Szenario | Lösungsdokument |
| --- | --- | --- |
| Endung | `.llab` | `.llsol` |
| Feld `format` | `"logisticsLab"` | `"logisticsLabSolution"` |
| Feld `version` | `1` | `1` |
| Inhalt | ein Objekt | eine Liste von Objekten, eines je gelöstem Problem |
| erzeugt von | Hand, Editor, App oder `logisticslab convert` | `logisticslab solve --out` oder einer App |

- **Erkennung am Inhalt:** Entscheidend ist das Feld `format`, nicht die Endung. Andere Endungen werden angenommen. `.ll` ist für LLVM vergeben und wird nicht verwendet.
- **Keine eigenen Matrizen:** Distanzen und Fahrzeiten kommen von den OSM-Servern (Straßennetz) oder als Luftlinie, Kosten werden daraus abgeleitet. Ein Szenario enthält deshalb nur Koordinaten, keine Distanz- oder Kostenmatrix.
- **Strikt:** Unbekannte Felder werden abgelehnt (Tippfehler fallen auf). Die maßgebliche Definition sind die Datenmodelle in `logisticsLabCore/scenario.py`; das JSON Schema dazu erzeugt `python -m logisticsLabCore.schema --scenario`.
- **Indizes:** Szenarien verweisen über Knoten-IDs (Zeichenketten), nicht über Positionen. Das unterscheidet sie von den REST- und JSON-RPC-Anfragen, die 0-basierte Indizes verwenden.

## Aufbau eines Szenarios

Pflicht sind nur `id` und `nodes`; alles andere hat einen Standard.

| Feld | Typ | Standard | Bedeutung |
| --- | --- | --- | --- |
| `format` | `"logisticsLab"` | `"logisticsLab"` | Kennung des Formats |
| `version` | `1` | `1` | Version des Formats |
| `$schema` | Text | – | optional, Pfad oder URL des JSON Schemas für Editoren; wird nicht ausgewertet |
| `id` | Text | – | Kennung des Szenarios |
| `name`, `description` | Text | – | für Menschen |
| `source` | Text | – | Herkunft, z. B. die alte Datei, aus der umgewandelt wurde |
| `units` | Objekt | `{"distance": "km", "time": "h"}` | Einheiten aller Distanzen und Zeiten im Szenario und in den Lösungen (Abschnitt Einheiten) |
| `matrix` | Objekt | OSM, Auto | wie Distanzen, Zeiten und Kosten entstehen (Abschnitt Matrix) |
| `nodes` | Liste | – | Knoten mit Koordinaten und Attributen |
| `networks` | Objekt Name → Netz | `{}` | erlaubte Verbindungen, für Flüsse, CPP und Netzbeschränkungen |
| `vehicles` | Liste | `[]` | Fahrzeugtypen für VRP |
| `commodities` | Liste | `[]` | Güter für `multicommodity` |
| `modes` | Liste | `[]` | Verkehrsträger für `multimodal` |
| `problems` | Liste | `[]` | Probleme, die auf diesen Daten gerechnet werden |

Beim Einlesen wird geprüft: Knoten-IDs sind eindeutig; Kanten, `assignedTo`, `deliveryTo`, `depot` und `network` verweisen nur auf vorhandene Knoten bzw. Netze; Güter und Verkehrsträger an Knoten und Kanten sind im Szenario definiert. Ein Fehler nennt die Stelle.

## Knoten

Jeder Knoten hat eine eindeutige `id` und Koordinaten `[lat, lon]` in Grad; seine Rollen bestimmen, welche Probleme ihn lesen. Felder ohne Bedeutung für ein Problem werden ignoriert, manche mit Warnung im Lösungsdokument.

| Rolle | Bedeutung | gelesen von |
| --- | --- | --- |
| `supplier` | Anbieter mit Angebot | `tpp`, Netzflüsse, `multistagewlp` |
| `customer` | Kunde mit Nachfrage | alle Transport-, Standort- und Tourenprobleme, Netzflüsse |
| `candidate` | möglicher Standort bzw. Lager | `wlp`, `pmedian`, `pcentre`, `scp`, `mcp`, `multistagewlp` |
| `depot` | Depot der Fahrzeuge | `vrp`, `pdp` |
| `pickup` | Abholort: holt `amount` ab und bringt es zu `deliveryTo` | `pdp` |
| `delivery` | Zustellort | `pdp` |
| `transit` | Umschlagknoten ohne Angebot und Nachfrage | Netzflüsse (Kennzeichnung) |

Ein Knoten kann mehrere Rollen haben, z. B. `["candidate", "depot", "transit"]`. Welche Rolle ein Problem als Quelle oder Ziel liest, lässt sich mit dem Parameter `roles` umstellen: `"roles": {"sources": "depot", "destinations": "customer"}`.

| Feld | Typ | Standard | Bedeutung, Verwendung |
| --- | --- | --- | --- |
| `id` | Text | Pflicht | Kennung, auf die Kanten und Lösungen verweisen |
| `coordinates` | `[lat, lon]` | Pflicht | Breite − 90 … 90, Länge − 180 … 180 |
| `name`, `address` | Text | – | Name; Adresse als freier Text |
| `addressDetails` | Objekt | – | `street`, `postcode`, `city`, `country` |
| `roles` | Liste | `[]` | siehe oben |
| `active` | Ja/Nein | `true` | `false`: der Knoten wird überall ignoriert |
| `supply`, `demand` | Zahl | – | Angebot, Nachfrage (`supplier`, `customer`) |
| `minSupply`, `maxSupply`, `minDemand`, `maxDemand` | Zahl | – | Spannen für `tpp` mit `useSupplyRanges` / `useDemandRanges` |
| `capacity` | Zahl | unbegrenzt | Kapazität eines `candidate` (WLP, P-Median, P-Center mit `isCapacitated`, Lager im `multistagewlp`) |
| `fixedCost` | Zahl | – | Fix- bzw. Öffnungskosten eines `candidate` |
| `fixed` | Ja/Nein | `false` | Standort muss offen sein – gespeichert, noch nicht ausgewertet |
| `assignedTo` | Knoten-ID | – | feste Zuordnung eines Kunden – gespeichert, noch nicht ausgewertet |
| `costFactor` | Zahl | `1` | Faktor auf die Kosten eines Kunden |
| `price` | Zahl | – | Erlös je Einheit eines `customer` – TPP mit `objSense: max` |
| `unitCost` | Zahl | – | Kosten je Einheit eines `supplier` (Herstellung, Einkauf) – TPP mit `objSense: max` |
| `timeWindow` | `[frühest, spätest]` | – | Zeitfenster für `vrp` als Uhrzeit in `units.time` ab 0:00 (bei `min`: 480 = 08:00); `spätest` `null` = offen. Am Depot: Start der Touren und späteste Rückkehr – gilt auch ohne `useTimeWindows` |
| `serviceTime` | Zahl | `0` | Servicezeit in `units.time` für `vrp` und `pdp` – beim Zustellort (`pdp`) die Stoppzeit je Halt: mehrere Mengen, die nacheinander an denselben Knoten gehen, sind ein Halt mit einer Stoppzeit |
| `serviceTimePerUnit` | Zahl | `0` | Servicezeit je Einheit in `units.time`, zusätzlich zu `serviceTime` – mal Nachfrage (`vrp`), Abhol- oder Liefermenge (`pdp`) |
| `amount` | Zahl | – | Abholort (`pdp`): abzuholende Menge |
| `deliveryTo` | Knoten-ID | – | Abholort (`pdp`): Zustellort der Menge – ein Knoten mit Rolle `delivery`; mehrere Abholorte dürfen denselben Zustellort haben |
| `minCap`, `maxCap` | Zahl | `0`, unbegrenzt | Mindest- und Höchstdurchsatz in Netzflüssen, einschließlich eigenem Angebot und eigener Nachfrage |
| `shortageCost` | Zahl | `0` | Kosten je nicht gelieferter Einheit bei `balance: auto` |
| `supplies`, `demands` | Objekt Gut → Zahl | – | Angebot und Nachfrage je Gut für `multicommodity` |
| `capacityFactors` | Objekt Gut → Zahl | 1 je Gut | Kapazität von `minCap`/`maxCap`, die eine Einheit eines Guts belegt (`multicommodity`) |

**Unbegrenzt:** Mengen und Kapazitäten dürfen statt einer Zahl `"M"` oder `null` sein. Die frühere Rolle `facility` gibt es nicht mehr; kontinuierliche Standorte sind Parameter des Problems (`p`, `capacities`).

## Netze und Kanten

Ein Netz legt die erlaubten Verbindungen zwischen Knoten fest; Länge und Fahrzeit jeder Kante kommen trotzdem von OSM bzw. aus der Luftlinie. `networks` ist ein Objekt Name → Netz, ein Problem wählt sein Netz mit `"network": "<Name>"`.

```json
"networks": {
  "supply": { "directed": true, "edges": [
    { "from": "W",  "to": "D1", "capacity": 100, "fixedCost": 200 },
    { "from": "D1", "to": "B" } ] } }
```

| Feld | Typ | Standard | Bedeutung |
| --- | --- | --- | --- |
| Netz `directed` | Ja/Nein | `false` | ungerichtete Kanten ergeben eine Verbindung in beide Richtungen |
| Netz `edges` | Liste | Pflicht | die Kanten |
| `from`, `to` | Knoten-ID | Pflicht | Anfang und Ende |
| `directed` | Ja/Nein | wie das Netz | Richtung dieser Kante |
| `capacity` | Zahl | unbegrenzt | Höchstfluss |
| `minFlow` | Zahl | `0` | Mindestfluss (bei `multistagewlp` nur, wenn die Kante genutzt wird) |
| `fixedCost` | Zahl | – | Fixkosten, wenn die Kante genutzt wird (`mincostflow` mit `useFixedCosts`, `multistagewlp`, TPP-Netz) |
| `modes` | Objekt Verkehrsträger → Werte | alle Verkehrsträger | `multimodal`: erlaubte Verkehrsträger mit abweichenden Werten |
| `commodities` | Objekt Gut → Werte | Werte des Guts | `multicommodity`: abweichende Kostensätze und Kapazitätsfaktoren |

**Wie ein Problem das Netz nutzt** (`networkMode` am Problem):

- `edges` (Standard): nur diese Kanten sind erlaubt. Bei TPP und den Standortproblemen sind alle übrigen Paare gesperrt; die Kantenwerte (`capacity`, `fixedCost`) gelten für das jeweilige Paar.
- `shortestPaths`: aus dem Netz entsteht eine vollständige Matrix der kürzesten Wege. Beim TSP enthält die Lösung dann den ganzen Weg (`path`).
- **Pflicht** ist ein Netz für `mincostflow`, `maxflow`, `multicommodity`, `multimodal`, `multistagewlp` und `cpp`; `vrp` ignoriert ein Netz mit Warnung.
- **Knotenkapazitäten** (`minCap`, `maxCap`, bei `multistagewlp` `capacity`) splittet LogisticsLab beim Lösen selbst in Ein- und Ausgang. Ein Knoten muss dafür nicht von Hand als zwei Knoten mit einer Kante dazwischen angelegt werden.

## Fahrzeuge, Güter und Verkehrsträger

Fahrzeuge brauchen nur `vrp` und `pdp`, Güter nur `multicommodity`, Verkehrsträger nur `multimodal`.

**Fahrzeuge** (`vehicles`) – je Eintrag ein Fahrzeugtyp:

| Feld | Typ | Standard | Bedeutung |
| --- | --- | --- | --- |
| `id` | Text | Pflicht | Name; bei `count` > 1 heißen die Fahrzeuge in der Lösung `<id>1`, `<id>2` … |
| `name` | Text | – | Bezeichnung für die Anzeige |
| `capacity` | Zahl | Pflicht | Kapazität eines Fahrzeugs |
| `count` | Zahl | automatisch | Anzahl; fehlt sie, stehen so viele Fahrzeuge wie Kunden bereit und der Solver minimiert zuerst die Zahl der Touren, dann die Strecke |
| `depot` | Knoten-ID | – | Depot; sonst Parameter `depot` oder der einzige Knoten mit Rolle `depot` |

**Güter** (`commodities`) – Standardwerte für alle Kanten; an einer Kante unter `commodities` abweichend:

| Feld | Typ | Standard | Bedeutung |
| --- | --- | --- | --- |
| `id`, `name` | Text | `id` Pflicht | Kennung, auf die `supplies`/`demands` der Knoten verweisen |
| `costPerKm`, `costPerHour` | Zahl | Werte der Matrix | Kostensätze je Einheit des Guts |
| `capacityFactor` | Zahl | `1` | Kantenkapazität, die eine Einheit belegt |

**Verkehrsträger** (`modes`) – Standardwerte für alle Kanten; an einer Kante unter `modes` abweichend, und eine Kante mit `modes` erlaubt nur die genannten:

| Feld | Typ | Standard | Bedeutung |
| --- | --- | --- | --- |
| `id`, `name` | Text | `id` Pflicht | Kennung |
| `costPerKm`, `costPerHour` | Zahl | Werte der Matrix | Kostensätze |
| `fixedCost` | Zahl | – | Fixkosten, wenn der Verkehrsträger auf einer Kante genutzt wird |
| `minFlow` | Zahl | – | Mindestmenge, wenn genutzt |
| `capacity` | Zahl | unbegrenzt | Höchstmenge je Kante |

## Einheiten, Matrix und Kosten

Distanzen und Fahrzeiten berechnet LogisticsLab aus den Koordinaten; `matrix` legt fest wie, `units` in welchen Einheiten sie im Szenario und in den Lösungen stehen.

| `units` | Werte | Standard |
| --- | --- | --- |
| `distance` | `m`, `km` | `km` |
| `time` | `s`, `min`, `h` | `h` |

Alle Zeitangaben im Szenario (`timeWindow`, `serviceTime`, Parameter wie `maxTime`) und alle Distanzen (`maxDist`, `radius`) sind in diesen Einheiten. `costPerKm` und `costPerHour` beziehen sich immer auf km und h.

| `matrix` | Werte | Standard | Bedeutung |
| --- | --- | --- | --- |
| `matrixSource` | `osm`, `beeline` | `osm` | Straßennetz der OSM-Server oder Luftlinie (Großkreis) |
| `travelmode` | `car`, `foot`, `wheelchair` | `car` | Profil für OSM |
| `detourFactor` | Zahl > 0 | `1.3` | nur Luftlinie: Faktor auf die Distanz |
| `averageSpeed` | km/h | je `travelmode` | nur Luftlinie: Geschwindigkeit für die Zeiten |
| `timeFactor` | Zahl > 0 | `1.0` | Faktor auf alle Fahrzeiten, z. B. 1.2 für Lkw |
| `costPerKm`, `costPerHour` | Zahl ≥ 0 | – | Kostensätze für `matrixMode: costs` |
| `noCache` | Ja/Nein | `false` | `true`: Matrix neu von den OSM-Servern statt aus dem Cache |

**Kosten** einer Verbindung, bei einem Kunden zusätzlich mal seinem `costFactor`:

```latex
c_{ij} = d_{ij}\,[\mathrm{km}] \cdot \mathrm{costPerKm} + t_{ij}\,[\mathrm{h}] \cdot \mathrm{timeFactor} \cdot \mathrm{costPerHour}
```

- **Welche Matrix ein Problem nutzt**, wählt sein Parameter `matrixMode`: `distances`, `times` oder `costs`. Ohne Angabe gilt `costs`, wenn `costPerKm` oder `costPerHour` gesetzt ist, sonst `distances`. `costs` ohne Kostensatz ist ein Fehler.
- **Je Problem abweichend:** `"matrix": { … }` am Problem überschreibt die Werte des Szenarios, z. B. ein anderer `costPerKm`.
- **Kontinuierliche Standorte** (`contpmedian`, `contpcentre`) rechnen immer mit Großkreisdistanzen in km, unabhängig von `matrixSource` (Warnung im Lösungsdokument).
- **Matrix-Cache:** Rohe OSM-Matrizen (m, s) werden zwischengespeichert, Faktoren und Kosten danach angewendet. Ein Wechsel von `costPerKm` braucht deshalb keine neue Abfrage.

## Probleme

Jedes Problem in `problems` ist ein Objekt mit `name` (Pflicht, eindeutig zum Auswählen mit `--problem`), `type` (Pflicht) und optional `parameters`, `network`, `networkMode` und `matrix`. Mehrere Probleme verschiedener Typen auf denselben Daten sind der Normalfall.

```json
"problems": [
  { "name": "Ein Lager", "type": "pmedian", "parameters": { "p": 1, "matrixMode": "distances" } },
  { "name": "Touren",   "type": "vrp",     "parameters": { "maxTime": 60 } } ]
```

**Parameter für alle Typen:** `matrixMode` (`distances`, `times`, `costs`), `maxSolvingTime` (Sekunden), `mipGap` (relative Lücke bei MIP), `roles` (andere Rollen als Quellen/Ziele). Beim Lösen überschreibt `logisticslab solve … --set NAME=WERT` jeden Parameter.

| `type` | Problem | liest | eigene Parameter |
| --- | --- | --- | --- |
| `tpp` | Transportproblem | `supplier` → `customer`, optional Netz | `objSense` (`min`, `max`, `maxflow`, `minimax`), `isSingleSource`, `useFixedCosts`, `useCapacities`, `useSupplyRanges`, `useDemandRanges`, `minBlock`, `maxBlock` |
| `wlp` | Warehouse Location | `candidate` → `customer` | `isCapacitated` |
| `pmedian` | p-Median | `candidate` → `customer` | `p` (Pflicht), `isCapacitated`, `isDemandWeighted` |
| `pcentre` | p-Center | `candidate` → `customer` | wie `pmedian` |
| `scp` | Set Covering | `candidate` → `customer` | `radius` (Pflicht), `useFixedCosts` (Standard `false`: wenigste Standorte) |
| `mcp` | Maximal Covering | `candidate` → `customer` | `radius`, `maxSrcCost` (Budget, Pflicht), `useFixedCosts` (Standard `true`) |
| `contpmedian` | kontinuierlicher p-Median | `customer` | `p` (Pflicht), `capacities` (ein Wert oder `p` Werte), `isCapacitated`, `isDemandWeighted`, `isSingleSource`, `nrOfStarts` |
| `contpcentre` | kontinuierliches p-Center | `customer` | wie `contpmedian` |
| `tsp` | Rundreise oder Durchfahrt | alle Knoten, optional Netz | `tourType`: `round` (zurück zum Start), `path` (Durchfahrt von `startNode` nach `endNode`), `open` (offenes Ende), `openStart` (offener Anfang, nur `endNode`), `free` (komplett offen); ohne `tourType` `startNode`, `endNode` (Knoten-ID; `null` = offener Start bzw. offenes Ende); `matrixMode` |
| `cpp` | Briefträgerproblem | Netz (Pflicht) | `startNode` |
| `pdp` | Pickup and Delivery: jede Menge wird auf derselben Tour erst abgeholt, dann zugestellt; die Ladung bleibt unter der Kapazität. Mit Höchstfahrzeit ein Dial-a-Ride-Problem (DARP) | `depot` + `pickup` (mit `amount`, `deliveryTo`) + `delivery`, `vehicles` | wie `vrp`, dazu `maxRideTime` (längste Fahrt je Paar von der Abfahrt am Abholort bis zum Beginn des Service am Ziel, in `units.time`) und `maxDetour` (höchstens dieses Vielfache der Direktfahrzeit) – mit beiden gilt die strengere Grenze; in den Ergebnissen `requests` je Paar mit `pickup`, `delivery`, `amount`, `vehicle`, `direct`, `ride`, `detour` und im `summary` `longestRide`, `maxDetour`; in den Ergebnissen je Abschnitt `amount` (+ Abholung, − Zustellung) und `load` (Ladung danach), je Route `maxLoad`; `load` ist die abgeholte Menge, `utilization` bezieht sich auf `maxLoad` |
| `vrp` | Tourenplanung | `depot` + `customer`, `vehicles` | `depot`, `useTimeWindows`, `fixedStart` (alle Routen beginnen zum Start der Einsatzzeit des Depots, sonst so spät wie möglich ohne Warten), `maxTime` (Höchstdauer je Route vom Start bis zur Rückkehr), `maxDist` (je Route, in `units`), `capacities` (statt `vehicles`) |
| `mincostflow` | Min-Cost-Flow | Netz (Pflicht) | `useFixedCosts`, `balance` |
| `shortestpath` | Kürzester Weg | Netz (Pflicht) | `startNode`, `endNode` (Knoten-IDs), `matrixMode`; Kanten je einzeln gerichtet (`directed`) – Ergebnis wie beim TSP: `routes` mit `legs`, `summary` mit `pathLength`, `nrOfLegs` |
| `maxflow` | Maximaler Fluss | Netz (Pflicht) | `endpoints`: `nodes` (Standard) mit `source`, `sink` (Knoten-IDs) oder `roles`: von allen `supplier` zu allen `customer` – der Kern führt eine künstliche Quelle und Senke ein, `supply`/`demand` begrenzen deren Kanten (leer oder `M`: unbegrenzt) |
| `multicommodity` | Mehrgüterfluss | Netz, `commodities` | `commodities` (Auswahl), `isInteger`, `balance` |
| `multimodal` | multimodaler Fluss | Netz, `modes` | `balance` |
| `multistagewlp` | mehrstufiges WLP | Netz: `supplier` → `candidate` (Lager) → … → `customer` | `isSingleSource`, `balance` |

- **`objSense: maxflow`** beim TPP: größte transportierte Menge; Angebot und Nachfrage sind ohne Spannen Obergrenzen, unter gleich großen Mengen gewinnt die günstigste Verteilung. `minBlock`/`maxBlock` sperren nach Kostensatz, Fixkosten werden ignoriert. Zielwert ist `totalFlow`.
- **`objSense: max`** beim TPP: Bewertet wird der Deckungsbeitrag je Einheit einer Verbindung = `price` des Kunden − `unitCost` des Anbieters − Transportkosten (aus `costPerKm`/`costPerHour`; ohne sie keine Transportkosten). Die Lösung gibt `totalContribution`, `totalFixedCosts`, `netContribution` (Zielwert: Deckungsbeitrag nach Fixkosten) und `minContributionRate`/`maxContributionRate`; `rate` der Verbindungen ist der Deckungsbeitrag je Einheit. Sinnvoll vor allem mit Spannen für Angebot oder Nachfrage.
- **`balance`** bei Netzflüssen: `auto` (Standard) gleicht ungleiche Summen von Angebot und Nachfrage aus, nicht gelieferte Mengen kosten `shortageCost`; `exact` verlangt gleiche Summen.
- **`isSingleSource`** bei `multistagewlp`: Wer von Lagern beliefert wird – Kunden und Lager späterer Stufen –, bekommt die Ware aus genau einem Lager.
- **`isInteger`** bei `multicommodity`: ganzzahlige Flüsse als MIP; das LP ist beim Mehrgüterfluss im Allgemeinen nicht ganzzahlig.

## Lösungsdokument (.llsol)

Eine `.llsol`-Datei ist eine JSON-Liste mit einem Lösungsdokument je gelöstem Problem. Jedes Dokument verweist über `scenario.hash` auf genau einen Datenstand des Szenarios und steht für sich: Ergebnisse gehören nie ins Szenario.

| Feld | Inhalt |
| --- | --- |
| `format`, `version` | `"logisticsLabSolution"`, `1` |
| `created` | Zeitpunkt der Lösung, ISO 8601 in UTC |
| `scenario` | `id` des Szenarios und `hash` seines Datenstands |
| `problem` | das gelöste Problem mit `name`, `type`, `network`, `networkMode` und den tatsächlich verwendeten `parameters` (einschließlich `--set`) |
| `status` | `solution`, `noSolution` oder `error` |
| `message` | Meldung des Solvers oder Fehlertext |
| `units` | die `units` des Szenarios |
| `valueUnit` | Einheit von `objVal` und der Verbindungswerte: `km`, `m`, `h`, `min`, `s` oder `costs` |
| `matrixInfo` | Herkunft der Matrix: `source` (`osm`, `cache`, `beeline`), `status`, `travelmode`, `matrices`, `osmDate` |
| `warnings` | Hinweise, z. B. ignorierte Attribute oder ein ignoriertes Netz |
| `results` | nur bei `status: solution`, siehe unten |

**Bezug zum Szenario:** `hash` ist SHA-256 über die Daten des Szenarios ohne `name`, `description`, `source`, `$schema` und `problems`. Eine Lösung bleibt also gültig, wenn Probleme hinzukommen oder Texte geändert werden; ändern sich Knoten, Netze, Fahrzeuge, Güter, Verkehrsträger, Einheiten oder Matrixoptionen, passt sie nicht mehr.

**`results`** verwendet Knoten-IDs statt Indizes; welche Felder vorkommen, hängt vom Typ ab:

| Feld | Inhalt | Typen |
| --- | --- | --- |
| `objVal` | Zielfunktionswert in `valueUnit` | alle |
| `summary` | Kennzahlen, z. B. `nrOfOpen`, `totalVarCosts`, `totalFixedCosts`, `totalOpeningCosts`, `nrOfRoutes` | je nach Typ |
| `nodes` | Objekt Knoten-ID → Werte: `open`, `load`, `flow`, `unusedSupply`, `unmetDemand`, bei Knotenkapazität (`maxCap`, Lager: `capacity`) `capacity` und `utilization` (Durchsatz / Kapazität), bei kontinuierlichen Standorten `F1 … Fp` mit `coordinates` | Standortprobleme, Netzflüsse, `multistagewlp` |
| `assignments` | Liste `{from, to, flow, …}`, bei Transport mit `rate` und mit Kapazitäten (`useCapacities`) `capacity`/`utilization`, bei Standorten mit `value` bzw. `distance` | `tpp`, Standort- und Covering-Probleme |
| `routes` | je Fahrzeug `vehicle`, `nodes`, `load`, `distance`; beim TSP die Abschnitte `legs` (`from`, `to`, `value` in `valueUnit`) und `summary` mit `tourLength`, `nrOfNodes`, `longestLeg`; beim VRP je Route die Abschnitte `legs` (mit `arrival`, `waiting`), `summary` mit `totalDistance`, `nrOfRoutes`, `nrOfVehicles`, `totalLoad`, `longestRoute`, `longestDuration` und der Zeitplan `arrivals`, `waitingTimes`, `times`, `serviceTimes`, `travelTimes` und die Summen `travelTime`, `waitingTime`, `serviceTime`, `duration` | `tsp`, `shortestpath`, `vrp`, `pdp`, `cpp` |
| `edges` | Liste `{from, to, flow, rate, used}`, bei mehreren Gütern `flows` je Gut, bei mehreren Verkehrsträgern `modes`; bei begrenzter Kapazität `capacity` und `utilization` (genutzter Anteil; mehrere Güter mit ihren `capacityFactor`, mehrere Verkehrsträger: der am stärksten ausgelastete) | Netzflüsse, `multistagewlp` |
| `solvingTime` | Rechenzeit in Sekunden | alle |
| `native` | die unveränderte Antwort des Kerns (Indizes, Einheiten der Anfrage) | alle |

`native` entspricht exakt den Ergebnissen von REST-Server und lokaler Schnittstelle (`logisticsLabCore/results.py`). Es ist für Prüfungen und Werkzeuge gedacht; eine App liest die Felder darüber.

## Beispiel

Ein Werk, zwei mögliche Lager und zwei Kunden, mit zwei Problemen auf denselben Daten – ein gekürzter Ausschnitt aus `tests/scenarios/brandenburg.llab`:

```json
{
  "format": "logisticsLab", "version": 1, "id": "brandenburg",
  "name": "Werk Ludwigsfelde, zwei Lager, Kunden",
  "units": { "distance": "km", "time": "min" },
  "matrix": { "matrixSource": "osm", "travelmode": "car", "costPerKm": 0.5, "costPerHour": 30 },
  "nodes": [
    { "id": "W",  "name": "Werk Ludwigsfelde", "coordinates": [52.30, 13.26], "roles": ["supplier"], "supply": 100 },
    { "id": "D1", "name": "Lager Wildau", "coordinates": [52.32, 13.63], "roles": ["candidate", "transit"],
      "capacity": 80, "fixedCost": 5000 },
    { "id": "D2", "name": "Lager Brandenburg", "coordinates": [52.41, 12.55], "roles": ["candidate", "transit"],
      "capacity": 60, "fixedCost": 4000 },
    { "id": "B",  "name": "Berlin",  "coordinates": [52.52, 13.40], "roles": ["customer"], "demand": 40 },
    { "id": "P",  "name": "Potsdam", "coordinates": [52.39, 13.06], "roles": ["customer"], "demand": 25 }
  ],
  "networks": {
    "supply": { "directed": true, "edges": [
      { "from": "W",  "to": "D1", "capacity": 100, "fixedCost": 200 },
      { "from": "W",  "to": "D2", "capacity": 60,  "fixedCost": 150 },
      { "from": "D1", "to": "B" }, { "from": "D2", "to": "P" }, { "from": "D2", "to": "B" } ] }
  },
  "problems": [
    { "name": "Lagerstandorte (WLP)", "type": "wlp", "parameters": { "matrixMode": "costs", "isCapacitated": true } },
    { "name": "Lager mehrstufig", "type": "multistagewlp", "network": "supply" }
  ]
}
```

Das Lösungsdokument des zweiten Problems (vollständiges Szenario, gekürzt auf je zwei Kanten und drei Knoten, `native` ausgelassen):

```json
[ {
  "format": "logisticsLabSolution", "version": 1, "created": "2026-10-21T17:28:19+00:00",
  "scenario": { "id": "brandenburg", "hash": "sha256:dcbfb854…c24c6b4" },
  "problem": { "name": "Lager mehrstufig", "type": "multistagewlp", "parameters": {},
               "network": "supply", "networkMode": "edges" },
  "status": "solution", "message": "Solution has been found",
  "units": { "distance": "km", "time": "min" }, "valueUnit": "costs",
  "matrixInfo": { "source": "cache", "status": "exact", "travelmode": "car",
                  "matrices": ["distances", "times"], "osmDate": "2024-12-30T00:59:58Z" },
  "results": {
    "objVal": 18609.1,
    "edges": [ { "from": "W", "to": "D1", "flow": 75.0, "rate": 27.56, "used": 1 },
               { "from": "W", "to": "D2", "flow": 25.0, "rate": 57.2,  "used": 1 } ],
    "nodes": { "D1": { "flow": 75.0, "open": 1 }, "D2": { "flow": 25.0, "open": 1 }, "B": { "flow": 40.0 } },
    "summary": { "totalVarCosts": 9009.06, "totalFixedCosts": 600.0, "totalOpeningCosts": 9000.0, "nrOfOpen": 2 },
    "solvingTime": 0.03,
    "native": { }
  }
} ]
```

`objVal` setzt sich aus `summary` zusammen: 9009.06 Transport + 600 Kantenfixkosten + 9000 Öffnungskosten = 18 609.06.

## Werkzeuge

Das Kommandozeilen-Tool `logisticslab` liest Szenarien, schreibt Lösungsdokumente und wandelt alte Dateien um; es steckt in allen Distributionen (`logisticslab-cli`, `LogisticsLab`).

```bash
logisticslab show  SZENARIO.llab                                  # Überblick: Knoten, Netze, Fahrzeuge, Probleme
logisticslab solve SZENARIO.llab                                  # alle Probleme, Ausgabe am Bildschirm
logisticslab solve SZENARIO.llab --problem "Lager mehrstufig"     # nur ausgewählte Probleme
logisticslab solve SZENARIO.llab --set p=3 --set maxSolvingTime=30
logisticslab solve SZENARIO.llab --out                            # SZENARIO.llsol neben dem Szenario
logisticslab solve SZENARIO.llab --out loesungen.llsol --quiet    # eigener Name, keine Ausgabe
logisticslab solve SZENARIO.llab --json                           # Lösungsdokumente am Bildschirm
logisticslab solve SZENARIO.llab --server https://…/v1/ --apiKey …  # auf einem LogisticsLab-Server
logisticslab convert ALTE_DATEI.TPPX                              # -> alte_datei.tppx.llab
logisticslab convert --dir ALT --target NEU                       # ganze Verzeichnisse
```

- **Exit-Code:** 1, wenn ein Problem mit einem Fehler endet; sonst 0, auch bei `noSolution`.
- **JSON Schema für Editoren:** `python -m logisticsLabCore.schema --scenario > logisticsLab-scenario.schema.json` erzeugt das Schema des Szenarioformats. In VS Code prüft es Szenarien beim Bearbeiten und bietet Vervollständigung an:

```json
"files.associations": { "*.llab": "json", "*.llsol": "json" },
"json.schemas": [ { "fileMatch": ["*.llab"], "url": "./.vscode/logisticsLab-scenario.schema.json" } ]
```

- **Alte LogisticsLab-Dateien:** `convert` macht aus TPPX `tpp`, aus DLPX `wlp`/`pmedian`/`pcentre`/`mcp`, aus CLPX `contpmedian`/`contpcentre`, aus NWFX `mincostflow`, aus TSPX `tsp`/`cpp` und aus VRPX `vrp`; die Optionen der Datei werden Parameter des Problems. Übersprungen werden Dateien mit eigenen Matrizen (`DistFunc OwnDef`) oder ebenen Koordinaten. Die alten Dateien haben `x` = Länge, `y` = Breite; das Szenario hat `[lat, lon]`.
- **Apps:** Eine App liest dieselben Dateien und löst sie über die lokale Schnittstelle (`logisticsLabStdio`) oder den REST-Server; die Übersetzung Szenario → Anfrage macht `ScenarioSolver` in `logisticsLabCore/scenario.py`.
