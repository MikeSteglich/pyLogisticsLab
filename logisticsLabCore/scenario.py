""" scenario format of LogisticsLab - one description of a logistic network for all problem types

    A scenario contains nodes (with coordinates [lat, lon], address and attributes), named networks of edges, vehicles,
    the matrix options and a list of problems. Distances and travel times come only from the OSM servers (or as bee
    line), costs are derived from them (costPerKm, costPerHour, costFactor of a customer).

    ScenarioSolver translates a problem into the items of the REST server (/v1/...) and maps the results back to the
    node ids. It needs a backend with matrix(payload) and solve(payload) - see cli.py (local core or REST server).

        scenario = Scenario.model_validate(json.load(f))
        solution = ScenarioSolver(scenario, backend).solve(scenario.problems[0])

    Units of the scenario (units): distance m or km, time s, min or h. costPerKm and costPerHour refer to km and h.
"""

from .items import MatrixOptions, CostOptions

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Optional, Literal, Union

import datetime
import hashlib
import heapq
import json
import math


FORMAT = 'logisticsLab'
SOLUTION_FORMAT = 'logisticsLabSolution'
VERSION = 1

TO_M = {'m': 1, 'km': 1000}
TO_S = {'s': 1, 'min': 60, 'h': 3600}
Unlimited = Union[float, Literal['M'], None]

PROBLEM_TYPES = ('tpp', 'wlp', 'pmedian', 'pcentre', 'scp', 'mcp', 'contpmedian', 'contpcentre', 'tsp', 'cpp', 'vrp',
                 'mincostflow', 'maxflow', 'multicommodity', 'multimodal', 'multistagewlp', 'shortestpath')


class ScenarioException(Exception):
    pass


#*************** data model ************************************************

class Item(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

class AddressDetails(Item):
    street: Optional[str] = None
    postcode: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None

class Node(Item):
    """ attributes are used by the problems that need them - e.g. demand by tpp, wlp, vrp ... """
    id: str
    name: Optional[str] = None
    coordinates: list[float]                     # [lat, lon]
    address: Optional[str] = None                # free text, e.g. for geocoding
    addressDetails: Optional[AddressDetails] = None
    roles: list[Literal['supplier', 'customer', 'candidate', 'depot', 'transit']] = []
    active: bool = True                          # False: the node is ignored
    supply: Unlimited = None
    minSupply: Unlimited = None
    maxSupply: Unlimited = None
    demand: Unlimited = None
    minDemand: Unlimited = None
    maxDemand: Unlimited = None
    capacity: Unlimited = None                   # candidate
    fixedCost: Optional[float] = None            # candidate
    fixed: bool = False                          # candidate: must be open
    assignedTo: Optional[str] = None             # customer: fixed assignment to a candidate
    costFactor: float = 1.0                      # customer: factor on its costs
    price: Optional[float] = None                # customer: revenue per unit - tpp with objSense max
    unitCost: Optional[float] = None             # supplier: costs per unit (production, purchase) - tpp max
    timeWindow: Optional[list[Optional[float]]] = None   # [earliest, latest] in units.time, latest null: open
    serviceTime: float = 0                       # in units.time
    minCap: float = 0                            # networks: minimal flow through the node (incl. own supply, demand)
    maxCap: Unlimited = None                     # networks: maximal flow through the node
    shortageCost: float = 0                      # networks with balance auto: costs per unit of unmet demand
    supplies: Optional[dict[str, float]] = None  # multicommodity: supply per commodity
    demands: Optional[dict[str, float]] = None   # multicommodity: demand per commodity
    capacityFactors: Optional[dict[str, float]] = None   # multicommodity: capacity of the node (minCap, maxCap)
                                                 # used by one unit of a commodity - default 1

    @field_validator('roles', mode='before')
    @classmethod
    def noFacility(cls, roles):
        # continuous location problems had nodes with role facility - their position is a result, not data
        if isinstance(roles, list) and 'facility' in roles:
            raise ValueError("role facility is not used anymore - contpmedian and contpcentre get the number of "
                             "facilities as parameter p and their capacities as parameter capacities")
        return roles

    @model_validator(mode='after')
    def check(self):
        if len(self.coordinates) != 2 or not (abs(self.coordinates[0]) <= 90 and abs(self.coordinates[1]) <= 180):
            raise ValueError(f'node {self.id}: coordinates [lat, lon] expected')
        return self

class Mode(Item):
    """ transport mode at an edge - costs from the OSM distance and time, missing values from the mode definition """
    costPerKm: Optional[float] = None
    costPerHour: Optional[float] = None
    fixedCost: Optional[float] = None
    minFlow: Optional[float] = None              # minimal flow if the mode is used
    capacity: Unlimited = None

class ModeDefinition(Mode):
    """ transport mode of the scenario, e.g. truck, train - the defaults for all edges """
    id: str
    name: Optional[str] = None

class EdgeCommodity(Item):
    costPerKm: Optional[float] = None
    costPerHour: Optional[float] = None
    capacityFactor: Optional[float] = None       # capacity of the edge used by one unit

class Commodity(Item):
    """ commodity of the scenario - default cost rates and capacity factor for all edges """
    id: str
    name: Optional[str] = None
    costPerKm: Optional[float] = None
    costPerHour: Optional[float] = None
    capacityFactor: float = 1.0

class Edge(Item):
    """ allowed connection - its length and time come from the OSM servers """
    from_: str = Field(alias='from')
    to: str
    directed: Optional[bool] = None              # default: directed of the network
    capacity: Unlimited = None
    minFlow: float = 0
    fixedCost: Optional[float] = None
    modes: Optional[dict[str, Mode]] = None      # multimodal: available modes, default all modes of the scenario
    commodities: Optional[dict[str, EdgeCommodity]] = None   # multicommodity: values per commodity

class Network(Item):
    directed: bool = False
    edges: list[Edge]

class Vehicle(Item):
    id: str
    name: Optional[str] = None
    capacity: float
    count: int = 1
    depot: Optional[str] = None

class Units(Item):
    distance: Literal['m', 'km'] = 'km'
    time: Literal['s', 'min', 'h'] = 'h'

class MatrixSettings(MatrixOptions, CostOptions):
    """ travelmode, matrixSource (osm, beeline), detourFactor, averageSpeed, timeFactor, noCache, costPerKm, costPerHour """

class Problem(Item):
    name: str
    type: Literal[PROBLEM_TYPES]
    parameters: dict = {}
    network: Optional[str] = None
    networkMode: Literal['edges', 'shortestPaths'] = 'edges'
    matrix: Optional[MatrixSettings] = None      # overrides the matrix options of the scenario for this problem

class Scenario(Item):
    schema_: Optional[str] = Field(None, alias='$schema')   # optional, e.g. for the editor - not used
    format: Literal['logisticsLab'] = FORMAT
    version: Literal[1] = VERSION
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None                 # e.g. the file the scenario has been converted from
    units: Units = Units()
    matrix: MatrixSettings = MatrixSettings()
    nodes: list[Node]
    networks: dict[str, Network] = {}
    vehicles: list[Vehicle] = []
    commodities: list[Commodity] = []
    modes: list[ModeDefinition] = []
    problems: list[Problem] = []

    @model_validator(mode='after')
    def check(self):
        ids = [ n.id for n in self.nodes ]
        if len(set(ids)) != len(ids):
            raise ValueError('node ids must be unique')
        known = set(ids)
        for name, net in self.networks.items():
            for e in net.edges:
                if e.from_ not in known or e.to not in known:
                    raise ValueError(f'network {name}: edge {e.from_}-{e.to} with an unknown node')
        commodities, modes = { c.id for c in self.commodities }, { m.id for m in self.modes }
        for n in self.nodes:
            if n.assignedTo and n.assignedTo not in known:
                raise ValueError(f'node {n.id}: unknown assignedTo {n.assignedTo}')
            for k in list(n.supplies or {}) + list(n.demands or {}) + list(n.capacityFactors or {}):
                if k not in commodities:
                    raise ValueError(f'node {n.id}: unknown commodity {k}')
        for name, net in self.networks.items():
            for e in net.edges:
                if any(k not in commodities for k in e.commodities or {}):
                    raise ValueError(f'network {name}: edge {e.from_}-{e.to} with an unknown commodity')
                if any(m not in modes for m in e.modes or {}):
                    raise ValueError(f'network {name}: edge {e.from_}-{e.to} with an unknown mode')
        for v in self.vehicles:
            if v.depot and v.depot not in known:
                raise ValueError(f'vehicle {v.id}: unknown depot {v.depot}')
        for p in self.problems:
            if p.network and p.network not in self.networks:
                raise ValueError(f'problem {p.name}: unknown network {p.network}')
        return self

    def dataHash(self):
        """ hash of the data (without names, descriptions and problems) - a solution refers to it """
        data = self.model_dump(by_alias=True, exclude={'schema_', 'name', 'description', 'source', 'problems'})
        return 'sha256:' + hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def unlimited(v):
    return v is None or v == 'M'


#*************** solver ************************************************

def _utilization(load, capacity):
    """ capacity and used share of it - empty without a (finite, positive) capacity """
    if capacity is None or unlimited(capacity) or capacity <= 0:
        return {}
    return {'capacity': capacity, 'utilization': load / capacity}


class ScenarioSolver:
    """ translates the problems of a scenario into items of the REST server and maps the results to node ids """

    def __init__(self, scenario, backend):
        self.s = scenario
        self.backend = backend
        self.nodes = { n.id: n for n in scenario.nodes if n.active }

    #*********** common ************
    def solve(self, problem, parameters=None):
        """ solution document of a problem - parameters override the parameters of the problem """
        payload = self.prepare(problem, parameters)
        return self.finish(self.backend.solve(payload))

    def prepare(self, problem, parameters=None):
        """ item of the problem for /v1/solve (as dict) - needs only backend.matrix

            The answer of the solver goes to finish. prepare and finish allow to solve the item as a job of the core
            (status, cancel), see LogisticsLabCore.submitScenario.
        """
        self.problem = problem
        self.par = {**problem.parameters, **(parameters or {})}
        self.opts = self.s.matrix.model_copy(update=problem.matrix.model_dump(exclude_unset=True)) if problem.matrix \
                    else self.s.matrix
        self.warnings = []
        self.matrixInfo = None
        self.valueUnit = None
        handler = getattr(self, '_' + problem.type)
        payload, self._mapResults = handler()
        # None means a default of the core - except an open start or end of a tsp (default 0: the first node)
        keep = ('startNode', 'endNode') if problem.type == 'tsp' else ()
        return {k: v for k, v in payload.items() if v is not None or k in keep}

    def finish(self, answer):
        """ solution document from the answer of the solver {status, message, results?} """
        solution = {
            'format': SOLUTION_FORMAT, 'version': VERSION,
            'created': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
            'scenario': {'id': self.s.id, 'hash': self.s.dataHash()},
            'problem': {**self.problem.model_dump(exclude_none=True), 'parameters': self.par},
            'status': answer.get('status'), 'message': answer.get('message'),
            'units': self.s.units.model_dump(),
        }
        if self.valueUnit:
            solution['valueUnit'] = self.valueUnit         # unit of objVal and of the values of the connections
        if self.matrixInfo:
            solution['matrixInfo'] = self.matrixInfo
        if answer.get('status') == 'solution':
            native = answer['results']
            try:
                results = {'objVal': native['objVal']}
                results.update(self._mapResults(native))
                results['solvingTime'] = native.get('solvingTime')
                results['native'] = native
                solution['results'] = results
            except ScenarioException as e:
                # the solver found something that is no solution of the problem (e.g. a tour over a missing way)
                solution.update(status='error', message=str(e))
        if self.warnings:
            solution['warnings'] = self.warnings
        return solution

    def _role(self, role, default):
        role = (self.par.get('roles') or {}).get(role, default)
        nodes = [ n for n in self.nodes.values() if role in n.roles ]
        if not nodes:
            raise ScenarioException(f'problem {self.problem.name}: no active nodes with role {role}')
        return nodes

    def _required(self, nodes, attr, what):
        """ every node needs a number in attr - else the nodes without it in the message """
        missing = [ (f'{n.name} ({n.id})' if n.name else n.id) for n in nodes
                    if not isinstance(getattr(n, attr), (int, float)) ]
        if missing:
            more = f' and {len(missing) - 5} more' if len(missing) > 5 else ''
            raise ScenarioException(f'problem {self.problem.name}: {what} missing at {", ".join(missing[:5])}{more}')

    def _flowEnds(self, nodes, perCommodity=False):
        """ a network flow needs suppliers and customers in its network with their quantities (per commodity) """
        ends = []
        for key, default, attr in (('sources', 'supplier', 'supplies' if perCommodity else 'supply'),
                                   ('destinations', 'customer', 'demands' if perCommodity else 'demand')):
            role = (self.par.get('roles') or {}).get(key, default)
            inNet = [ n for n in nodes if role in n.roles ]
            if not inNet:
                raise ScenarioException(f'problem {self.problem.name}: no node with role {role} in the network')
            if perCommodity:
                missing = [ (f'{n.name} ({n.id})' if n.name else n.id) for n in inNet if not getattr(n, attr) ]
                if missing:
                    raise ScenarioException(f'problem {self.problem.name}: {attr} per commodity missing at '
                                            f'{", ".join(missing[:5])}')
            else:
                self._required(inNet, attr, attr)
            ends.append(inNet)
        return ends

    def _node(self, id, name):
        if id not in self.nodes:
            raise ScenarioException(f'problem {self.problem.name}: unknown or inactive {name} {id}')
        return self.nodes[id]

    def _kind(self, default=None):
        """ matrix of the problem: distances, times or costs """
        kind = self.par.get('matrixMode')
        if kind is None:
            kind = default or ('costs' if (self.opts.costPerKm or self.opts.costPerHour) else 'distances')
        if kind == 'costs' and not (self.opts.costPerKm or self.opts.costPerHour):
            raise ScenarioException(f'problem {self.problem.name}: matrixMode costs needs costPerKm and/or costPerHour')
        self.valueUnit = {'distances': self.s.units.distance, 'times': self.s.units.time, 'costs': 'costs'}[kind]
        return kind

    def _rawMatrix(self, rows, cols):
        """ OSM (or bee line) distances in m and durations in s [rows x cols], durations x timeFactor """
        coords, index = [], {}
        for n in rows + cols:
            if n.id not in index:
                index[n.id] = len(coords)
                coords.append(n.coordinates)
        o = self.opts
        payload = {'coordinates': coords, 'sources': [ index[n.id] for n in rows ],
                   'destinations': [ index[n.id] for n in cols ], 'matrixMode': 'both', 'rounded': False,
                   'travelmode': o.travelmode, 'matrixSource': o.matrixSource, 'detourFactor': o.detourFactor,
                   'averageSpeed': o.averageSpeed, 'timeFactor': o.timeFactor, 'noCache': o.noCache}
        answer = self.backend.matrix({k: v for k, v in payload.items() if v is not None})
        info = answer.get('matrixInfo')
        if info:
            self.matrixInfo = {**(self.matrixInfo or {}), **info}
        return answer['distances'], answer['durations']

    def _value(self, kind, d, t):
        """ value of a connection in the units of the scenario - d in m, t in s """
        if kind == 'distances':
            return d / TO_M[self.s.units.distance]
        if kind == 'times':
            return t / TO_S[self.s.units.time]
        return d / 1000 * (self.opts.costPerKm or 0) + t / 3600 * (self.opts.costPerHour or 0)

    def _matrix(self, rows, cols, kind):
        """ matrix of the kind [rows x cols] - restricted to the network of the problem or as shortest paths """
        if self.problem.network is None:
            D, T = self._rawMatrix(rows, cols)
            return [ [ self._value(kind, D[i][j], T[i][j]) for j in range(len(cols)) ] for i in range(len(rows)) ]

        net = self.s.networks[self.problem.network]
        if self.problem.networkMode == 'edges':
            D, T = self._rawMatrix(rows, cols)
            allowed = set()
            for e in net.edges:
                allowed.add((e.from_, e.to))
                if not (net.directed if e.directed is None else e.directed):
                    allowed.add((e.to, e.from_))
            return [ [ self._value(kind, D[i][j], T[i][j]) if (r.id, c.id) in allowed else 'M'
                       for j, c in enumerate(cols) ] for i, r in enumerate(rows) ]

        dist, self.paths = self._shortestPaths(net, kind)
        return [ [ dist.get(r.id, {}).get(c.id, 'M') if r.id != c.id else 0 for c in cols ] for r in rows ]

    def _edgeValues(self, net, kind):
        """ value of every edge of the network (OSM between its two nodes), arcs of undirected edges in both directions """
        ids = sorted({ e.from_ for e in net.edges } | { e.to for e in net.edges })
        nodes = [ self._node(i, 'node of the network') for i in ids ]
        D, T = self._rawMatrix(nodes, nodes)
        pos = { n: i for i, n in enumerate(ids) }
        arcs = {}
        for e in net.edges:
            i, j = pos[e.from_], pos[e.to]
            arcs[(e.from_, e.to)] = self._value(kind, D[i][j], T[i][j])
            if not (net.directed if e.directed is None else e.directed):
                arcs[(e.to, e.from_)] = self._value(kind, D[j][i], T[j][i])
        return arcs

    def _shortestPaths(self, net, kind):
        """ Dijkstra from every node - distances and predecessors over the arcs of the network """
        arcs = self._edgeValues(net, kind)
        adj = {}
        for (a, b), v in arcs.items():
            adj.setdefault(a, []).append((b, v))
        dist, pred = {}, {}
        for s in { a for a, _ in arcs } | { b for _, b in arcs }:
            d, p, heap = {s: 0}, {}, [(0, s)]
            while heap:
                du, u = heapq.heappop(heap)
                if du > d[u]:
                    continue
                for v, w in adj.get(u, []):
                    if du + w < d.get(v, math.inf):
                        d[v], p[v] = du + w, u
                        heapq.heappush(heap, (du + w, v))
            dist[s], pred[s] = d, p
        return dist, pred

    def _path(self, a, b):
        """ nodes of the shortest path a -> b (shortestPaths) """
        p = self.paths.get(a, {})
        path = [b]
        while path[-1] != a:
            if path[-1] not in p:
                return [a, b]
            path.append(p[path[-1]])
        return path[::-1]

    def _common(self):
        return {'maxSolvingTime': self.par.get('maxSolvingTime'), 'mipGap': self.par.get('mipGap')}

    def _costFactors(self, matrix, cols, kind):
        """ the cost factor of a customer multiplies its column (distances and costs) """
        if kind == 'times' or all(c.costFactor == 1 for c in cols):
            return matrix
        return [ [ v if v == 'M' else v * c.costFactor for v, c in zip(row, cols) ] for row in matrix ]

    DEFAULTS = {'fixed': False, 'assignedTo': None, 'costFactor': 1.0}

    def _warnIgnored(self, nodes, attributes):
        for a in attributes:
            if any(getattr(n, a) != self.DEFAULTS[a] for n in nodes):
                self.warnings.append(f'{a} is not supported by {self.problem.type} and is ignored')

    #*********** transportation problem ************
    def _tpp(self):
        S, D = self._role('sources', 'supplier'), self._role('destinations', 'customer')
        par = self.par
        self._required(S, 'supply', 'supply')
        self._required(D, 'demand', 'demand')
        sense = par.get('objSense', 'min')
        isMax, isMaxFlow = sense == 'max', sense == 'maxflow'
        minBlock, maxBlock = par.get('minBlock'), par.get('maxBlock')
        if not isMax:
            kind = self._kind()
            C = self._costFactors(self._matrix(S, D, kind), D, kind)
        else:
            C = self._contributions(S, D)
        R = C                                        # rates of the solution: costs or contributions per unit
        if isMaxFlow:
            # largest total quantity - among those the cheapest: weights 1 - a small share of the cost rate; the
            # blocking applies to the cost rates, so it is done here
            def blocked(c):
                return c == 'M' or (minBlock is not None and c < minBlock) or (not unlimited(maxBlock) and c > maxBlock)
            R = [ [ 'M' if blocked(c) else c for c in row ] for row in C ]
            cMax = max([ c for row in R for c in row if c != 'M' ] or [1]) or 1
            C = [ [ 'M' if c == 'M' else 1 - 1e-4 * c / cMax for c in row ] for row in R ]
            minBlock = maxBlock = None
            sense = 'max'
            if par.get('useFixedCosts'):
                self.warnings.append('objSense maxflow: the fixed costs are ignored')
        net = self.s.networks.get(self.problem.network) if self.problem.network else None

        def pairMatrix(attr, default):
            m = [ [ default for _ in D ] for _ in S ]
            if net is None:
                return m
            ps, pd = { n.id: i for i, n in enumerate(S) }, { n.id: j for j, n in enumerate(D) }
            for e in net.edges:
                v = getattr(e, attr)
                if v is not None and e.from_ in ps and e.to in pd:
                    m[ps[e.from_]][pd[e.to]] = v
            return m

        payload = {'type': 'tpp', 'varCosts': C,
                   'supplies': [ n.supply for n in S ], 'demands': [ n.demand for n in D ],
                   'objSense': sense, 'isSingleSource': par.get('isSingleSource', False),
                   'minBlock': minBlock, 'maxBlock': maxBlock,
                   'sourceNames': [ n.id for n in S ], 'destinationNames': [ n.id for n in D ], **self._common()}
        if par.get('useSupplyRanges'):
            payload['minSupplies'] = [ n.minSupply or 0 for n in S ]
            payload['maxSupplies'] = [ n.supply if n.maxSupply is None else n.maxSupply for n in S ]
        elif isMaxFlow:
            # largest quantity: supply and demand are upper bounds
            payload['minSupplies'], payload['maxSupplies'] = [ 0 for _ in S ], [ n.supply for n in S ]
        if par.get('useDemandRanges'):
            payload['minDemands'] = [ n.minDemand or 0 for n in D ]
            payload['maxDemands'] = [ n.demand if n.maxDemand is None else n.maxDemand for n in D ]
        elif isMaxFlow:
            payload['minDemands'], payload['maxDemands'] = [ 0 for _ in D ], [ n.demand for n in D ]
        caps = None
        if par.get('useCapacities'):
            payload['capacities'] = caps = pairMatrix('capacity', 'M')
        if par.get('useFixedCosts') and not isMaxFlow:
            payload['fixedCosts'] = pairMatrix('fixedCost', 0)

        def results(r):
            flows = r['flows']
            if isMaxFlow:
                # the objective is the quantity - the costs of the cost rates of the used connections
                used = [ (flows[i][j], R[i][j]) for i in range(len(S)) for j in range(len(D))
                         if flows[i][j] > 1e-9 and R[i][j] != 'M' ]
                varCosts = sum(f * c for f, c in used)
                summary = {'totalFlow': sum(sum(row) for row in flows), 'totalCosts': varCosts, 'totalVarCosts': varCosts}
                if used:
                    summary.update(minCostRate=min(c for _, c in used), maxCostRate=max(c for _, c in used))
            elif isMax:
                # the rates are contributions: total contribution, after the fixed costs (objective), per unit
                summary = {'totalContribution': r['totalVarCosts'], 'totalFixedCosts': r['totalFixedCosts'],
                           'netContribution': r['totalVarCosts'] - r['totalFixedCosts'], 'totalFlow': r['totalFlow'],
                           'minContributionRate': r['minCostRate'], 'maxContributionRate': r['maxCostRate']}
            else:
                summary = {k: r[k] for k in ('totalCosts', 'totalVarCosts', 'totalFixedCosts', 'totalFlow',
                                             'minCostRate', 'maxCostRate') if k in r}
            return {
                **({'objVal': summary['totalFlow']} if isMaxFlow else {}),
                'summary': summary,
                'nodes': {**{ n.id: {'flow': f} for n, f in zip(S, r['sourceFlows']) },
                          **{ n.id: {'flow': f} for n, f in zip(D, r['destinationFlows']) }},
                'assignments': [ {'from': S[i].id, 'to': D[j].id, 'flow': flows[i][j], 'rate': R[i][j],
                                  **_utilization(flows[i][j], caps[i][j] if caps else None)}
                                 for i in range(len(S)) for j in range(len(D)) if flows[i][j] > 1e-9 ]}
        return payload, results

    def _contributions(self, S, D):
        """ tpp max: contribution per unit of a connection = price of the customer - unit cost of the supplier -
            transport costs (matrix with costPerKm/costPerHour; without them no transport costs) """
        priced = any(n.price is not None for n in D) or any(n.unitCost is not None for n in S)
        if not priced:
            self.warnings.append('objSense max without price (customers) and unitCost (suppliers) - '
                                 'the contribution is only the negative transport costs')
        if self.opts.costPerKm or self.opts.costPerHour:
            T = self._costFactors(self._matrix(S, D, 'costs'), D, 'costs')
        else:
            self.warnings.append('objSense max without costPerKm and costPerHour - no transport costs')
            T = [ [ 0 for _ in D ] for _ in S ]
            if self.problem.network:
                # the network restricts the connections - its blocked pairs stay blocked
                M = self._matrix(S, D, 'distances')
                T = [ [ 'M' if v == 'M' else 0 for v in row ] for row in M ]
        self.valueUnit = 'costs'
        return [ [ 'M' if t == 'M' else (d.price or 0) - (s.unitCost or 0) - t for d, t in zip(D, row) ]
                 for s, row in zip(S, T) ]

    #*********** discrete location and covering ************
    def _discrete(self, type):
        S, D = self._role('sources', 'candidate'), self._role('destinations', 'customer')
        kind = self._kind()
        M = self._matrix(S, D, kind)
        if type in ('wlp', 'pmedian'):
            M = self._costFactors(M, D, kind)
        else:
            self._warnIgnored(D, ['costFactor'])
        self._warnIgnored(S, ['fixed'])
        self._warnIgnored(D, ['assignedTo'])
        par = self.par
        demands = [ n.demand if n.demand is not None else 1 for n in D ]
        capacities = [ n.capacity for n in S ]
        fixedCosts = [ n.fixedCost or 0 for n in S ]
        if type == 'wlp':
            payload = {'type': 'wlp', 'varCosts': M, 'fixedCosts': fixedCosts, 'demands': demands,
                       'isCapacitated': par.get('isCapacitated', False)}
            if payload['isCapacitated']:
                payload['supplies'] = capacities
        elif type in ('pmedian', 'pcentre'):
            payload = {'type': type, 'p': par['p'], 'varCosts': M, 'demands': demands,
                       'isCapacitated': par.get('isCapacitated', False),
                       'isDemandWeighted': par.get('isDemandWeighted', False)}
            if payload['isCapacitated']:
                payload['supplies'] = capacities
        else:
            payload = {'type': type, 'distances': M, 'radius': par['radius']}
            if par.get('useFixedCosts', type == 'mcp'):
                payload['fixedCosts'] = fixedCosts
            if type == 'mcp':
                payload['demands'] = demands
                payload['maxSrcCost'] = par['maxSrcCost']
        payload.update(self._common())

        def results(r):
            nodes = { n.id: {'open': int(a)} for n, a in zip(S, r['activeSources']) }
            assignments = []
            for j, i in enumerate(r['assignments']):
                if i >= 0:
                    assignments.append({'from': S[i].id, 'to': D[j].id, 'flow': demands[j], 'value': M[i][j]})
                    nodes[S[i].id]['load'] = nodes[S[i].id].get('load', 0) + demands[j]
                    nodes[S[i].id]['nrOfAssigned'] = nodes[S[i].id].get('nrOfAssigned', 0) + 1
            out = {'nodes': nodes, 'assignments': assignments,
                   'summary': {'nrOfOpen': sum(r['activeSources']), 'nrOfAssigned': len(assignments)}}
            if 'coveringSources' in r:
                out['covering'] = { D[j].id: [ S[i].id for i in c ] for j, c in enumerate(r['coveringSources']) }
            return out
        return payload, results

    def _wlp(self): return self._discrete('wlp')
    def _pmedian(self): return self._discrete('pmedian')
    def _pcentre(self): return self._discrete('pcentre')
    def _scp(self): return self._discrete('scp')
    def _mcp(self): return self._discrete('mcp')

    #*********** continuous location ************
    def _continuous(self, type):
        D = self._role('destinations', 'customer')
        par = self.par
        # the facilities are a result - their number p and their capacities are parameters, not nodes
        p = par.get('p')
        if not isinstance(p, int) or isinstance(p, bool) or p < 1:
            raise ScenarioException(f'problem {self.problem.name}: parameter p (number of facilities) is needed')
        caps = par.get('capacities')
        isCap = par.get('isCapacitated', caps is not None)
        weighted = par.get('isDemandWeighted', True)
        demands = [ n.demand if n.demand is not None else 1 for n in D ]
        payload = {'type': type, 'p': p, 'coordinates': [ n.coordinates for n in D ],
                   'isSingleSource': par.get('isSingleSource', True), 'nrOfStarts': par.get('nrOfStarts'),
                   **self._common()}
        if isCap:
            if caps is None or (isinstance(caps, list) and len(caps) != p):
                raise ScenarioException(f'problem {self.problem.name}: capacitated - parameter capacities needed, '
                                        f'one value for all facilities or a list of {p} values')
            payload['capacities'] = caps
            payload['demands'] = demands
            if not weighted:
                self.warnings.append('isDemandWeighted false with capacities: the costs are weighted with the demands')
        elif weighted or type == 'contpcentre':
            payload['demands'] = demands
        if caps is not None and not isCap:
            self.warnings.append('capacities are ignored with isCapacitated false')
        if type == 'contpmedian' and any(n.costFactor != 1 for n in D):
            payload['costFactors'] = [ n.costFactor for n in D ]
        elif type == 'contpcentre':
            self._warnIgnored(D, ['costFactor'])
        if self.opts.matrixSource != 'beeline':
            self.warnings.append('continuous location problems use great-circle distances, not the road network')
        scale = 1000 / TO_M[self.s.units.distance]                  # results in km
        self.valueUnit = self.s.units.distance
        ids = [ f'F{k+1}' for k in range(p) ]

        def results(r):
            flows = r.get('flows')
            assignments = []
            for j, k in enumerate(r['assignments']):
                if k >= 0:
                    assignments.append({'from': ids[k], 'to': D[j].id,
                                        'flow': flows[k][j] if flows else demands[j],
                                        'distance': r['customerDistances'][j] * scale})
            return {'objVal': r['objVal'] * scale,
                    'nodes': { ids[k]: {'coordinates': loc, 'load': sum(a['flow'] for a in assignments if a['from'] == ids[k])}
                               for k, loc in enumerate(r['locations']) },
                    'assignments': assignments}
        return payload, results

    def _contpmedian(self): return self._continuous('contpmedian')
    def _contpcentre(self): return self._continuous('contpcentre')

    #*********** routing ************
    def _tsp(self):
        nodes = list(self.nodes.values())
        kind = self._kind('distances')
        # startNode / endNode None: open start / open end - tourType: round trip (back to the start), path (from the
        # start to endNode, "Durchfahrt") or open (open end)
        start = self.par['startNode'] if 'startNode' in self.par else nodes[0].id
        end = self.par['endNode'] if 'endNode' in self.par else start
        tourType = self.par.get('tourType')
        if tourType == 'round':
            end = start
        elif tourType == 'open':
            end = None
        elif tourType == 'openStart':
            # open start, fixed end
            start = None
            if self.par.get('endNode') is None:
                raise ScenarioException(f'problem {self.problem.name}: tourType openStart needs the parameter endNode')
        elif tourType == 'free':
            start = end = None
        elif tourType == 'path':
            if self.par.get('endNode') is None:
                raise ScenarioException(f'problem {self.problem.name}: tourType path needs the parameter endNode')
            if end == start:
                raise ScenarioException(f'problem {self.problem.name}: tourType path needs an endNode other than startNode')
        pos = { n.id: i for i, n in enumerate(nodes) }
        # OR-Tools needs integers - m, s or 1/100 of the costs, without a connection a very long one
        scale = {'distances': TO_M[self.s.units.distance], 'times': TO_S[self.s.units.time], 'costs': 100}[kind]
        values = self._matrix(nodes, nodes, kind)
        self._checkReachable(nodes, values, start, end, tourType)
        M = [ [ 10**12 if v == 'M' else round(v * scale) for v in row ] for row in values ]
        payload = {'type': 'tsp', 'distances': M,
                   'startNode': None if start is None else pos[self._node(start, 'startNode').id],
                   'endNode': None if end is None else pos[self._node(end, 'endNode').id],
                   'openRoute': start is None or end is None or end != start}
        if self.problem.network and self.problem.networkMode == 'edges':
            net = self.s.networks[self.problem.network]
            edges = set()
            for e in net.edges:
                edges.add((pos[e.from_], pos[e.to]))
                if not (net.directed if e.directed is None else e.directed):
                    edges.add((pos[e.to], pos[e.from_]))
            payload['edges'] = [ list(e) for e in sorted(edges) ]

        def results(r):
            route = [ nodes[i].id for i in r['route'] ]
            # a connection without a way in the network has a very large value - then there is no tour at all
            impossible = [ (nodes[a].name or nodes[a].id, nodes[b].name or nodes[b].id)
                           for a, b in zip(r['route'], r['route'][1:]) if values[a][b] == 'M' ]
            if impossible:
                raise ScenarioException(f'problem {self.problem.name}: no tour through all nodes in the network - '
                                        f'no way from {impossible[0][0]} to {impossible[0][1]}')
            # the sections of the tour with their length (distance, time or costs as the objective)
            legs = [ {'from': nodes[a].id, 'to': nodes[b].id, 'value': values[a][b]}
                     for a, b in zip(r['route'], r['route'][1:]) ]
            out = {'objVal': r['objVal'] / scale, 'routes': [ {'nodes': route, 'legs': legs} ],
                   'summary': {'tourLength': r['objVal'] / scale, 'nrOfNodes': len(set(route)),
                               'longestLeg': max((l['value'] for l in legs if l['value'] != 'M'), default=0)}}
            if self.problem.network and self.problem.networkMode == 'shortestPaths':
                path = [route[0]]
                for leg, (a, b) in zip(legs, zip(route, route[1:])):
                    # the way of the section through the network
                    leg['path'] = self._path(a, b)
                    path += leg['path'][1:]
                out['routes'][0]['path'] = path
            return out
        return payload, results

    def _checkReachable(self, nodes, values, start, end, tourType):
        """ every node of a tour needs a way to another node and from another node - not the start of a passage or
            an open tour (nothing before it) and not the end of a passage (nothing after it) """
        name = lambda n: f'{n.name} ({n.id})' if n.name else n.id
        n = len(nodes)
        for k, node in enumerate(nodes):
            out = any(values[k][j] != 'M' for j in range(n) if j != k)
            into = any(values[i][k] != 'M' for i in range(n) if i != k)
            needsOut = not (end is not None and end != start and node.id == end)
            needsIn = not (node.id == start and (end is None or end != start))
            # an open start or end: the first or last node is not known before - no check of that side
            if start is None:
                needsIn = False
            if end is None:
                needsOut = False
            if needsOut and not out:
                raise ScenarioException(f'problem {self.problem.name}: no way from {name(node)} to another node '
                                        f'in the network - check the direction of its edges')
            if needsIn and not into:
                raise ScenarioException(f'problem {self.problem.name}: no way to {name(node)} from another node '
                                        f'in the network - check the direction of its edges')

    def _cpp(self):
        if not self.problem.network:
            raise ScenarioException(f'problem {self.problem.name}: cpp needs a network')
        net = self.s.networks[self.problem.network]
        kind = self._kind('distances')
        ids = sorted({ e.from_ for e in net.edges } | { e.to for e in net.edges })
        nodes = [ self._node(i, 'node of the network') for i in ids ]
        pos = { n: i for i, n in enumerate(ids) }
        D, T = self._rawMatrix(nodes, nodes)
        edges, weights, types = [], [], []
        for e in net.edges:
            i, j = pos[e.from_], pos[e.to]
            edges.append([i, j])
            weights.append(self._value(kind, D[i][j], T[i][j]))
            types.append(0 if (net.directed if e.directed is None else e.directed) else 1)
        start = self.par.get('startNode', ids[0])
        startNode = self._node(start, 'startNode')
        if startNode.id not in pos:
            raise ScenarioException(f'problem {self.problem.name}: start {startNode.name or startNode.id} is no node of the network')
        # every edge must be reachable from the start and the start from every edge (directed edges one way)
        succ, pred = {}, {}
        for (i, j), t in zip(edges, types):
            for a, b in ((i, j), (j, i)) if t == 1 else ((i, j),):
                succ.setdefault(a, set()).add(b)
                pred.setdefault(b, set()).add(a)
        def reach(graph, frm):
            seen, todo = {frm}, [frm]
            while todo:
                for b in graph.get(todo.pop(), ()):
                    if b not in seen:
                        seen.add(b)
                        todo.append(b)
            return seen
        s0 = pos[startNode.id]
        there, back = reach(succ, s0), reach(pred, s0)
        name = lambda k: nodes[k].name or nodes[k].id
        cut = [ k for k in range(len(ids)) if k not in there or k not in back ]
        if cut:
            k = cut[0]
            way = f'from the start {name(s0)} to {name(k)}' if k not in there else \
                f'from {name(k)} back to the start {name(s0)}'
            raise ScenarioException(f'problem {self.problem.name}: no way {way} - check the direction of the edges')
        payload = {'type': 'cpp', 'edges': edges, 'edgeWeights': weights, 'edgeTypes': types,
                   'startNode': s0, **self._common()}

        def results(r):
            tour = [ ids[i] for i in r['eulerTour'] ]
            # value of a section: the cheapest edge between its nodes in its direction
            values = {}
            for e, (i, j), t, w in zip(net.edges, edges, types, weights):
                for a, b in ((i, j), (j, i)) if t == 1 else ((i, j),):
                    key = (ids[a], ids[b])
                    values[key] = min(values.get(key, w), w)
            legs = [ {'from': a, 'to': b, 'value': values.get((a, b), 0)} for a, b in zip(tour, tour[1:]) ]
            length = sum(l['value'] for l in legs)
            edgesLength = sum(weights)
            usages = r['edgeUsages']
            return {'objVal': length,
                    'routes': [ {'nodes': tour, 'legs': legs} ],
                    'edges': [ {'from': e.from_, 'to': e.to, 'usages': u, 'value': w}
                               for e, u, w in zip(net.edges, usages, weights) ],
                    'summary': {'tourLength': length, 'edgesLength': edgesLength,
                                'extraLength': length - edgesLength, 'nrOfEdges': len(net.edges),
                                'nrOfRepeats': sum(max(u - 1, 0) for u in usages)}}
        return payload, results

    def _vrp(self):
        depots = [ n for n in self.nodes.values() if 'depot' in n.roles ]
        depotId = self.par.get('depot') or (self.s.vehicles[0].depot if self.s.vehicles and self.s.vehicles[0].depot
                                             else (depots[0].id if len(depots) == 1 else None))
        if depotId is None:
            raise ScenarioException(f'problem {self.problem.name}: no depot - parameter depot or one node with role depot')
        depot = self._node(depotId, 'depot')
        customers = [ n for n in self._role('destinations', 'customer') if n.id != depot.id ]
        self._required(customers, 'demand', 'demand')
        nodes = [depot] + customers
        if self.problem.network:
            self.warnings.append('vrp uses the complete matrix of the OSM servers, the network is ignored')
        D, T = self._rawMatrix(nodes, nodes)
        ts = TO_S[self.s.units.time]
        par = self.par
        useTW = par.get('useTimeWindows', any(n.timeWindow for n in customers))
        capacities, vehicleIds = [], []
        for v in self.s.vehicles:
            capacities += [v.capacity] * v.count
            vehicleIds += [v.id] if v.count == 1 else [ f'{v.id}{k+1}' for k in range(v.count) ]
        if 'capacities' in par:
            capacities = par['capacities']
            vehicleIds = [ f'V{k+1}' for k in range(len(capacities)) ]
        if not capacities:
            raise ScenarioException(f'problem {self.problem.name}: no vehicles')
        # a customer whose demand fits into no vehicle
        tooBig = [ n for n in customers if n.demand > max(capacities) ]
        if tooBig:
            n = tooBig[0]
            raise ScenarioException(f'problem {self.problem.name}: the demand {n.demand:g} of {n.name or n.id} is larger '
                                    f'than the largest vehicle ({max(capacities):g})')
        # OR-Tools needs integers - meters and seconds
        payload = {'type': 'vrp', 'distances': [ [ round(v) for v in row ] for row in D ],
                   'demands': [0] + [ n.demand or 0 for n in customers ], 'capacities': capacities, 'depot': 0,
                   'maxSolvingTime': par.get('maxSolvingTime')}
        # the times always - the solution contains the travel and waiting times of the routes
        payload['times'] = [ [ round(v) for v in row ] for row in T ]
        payload['serviceTimes'] = [ round(n.serviceTime * ts) for n in nodes ]
        if useTW:
            big = 10**9
            payload['timeWindows'] = [ [ round((n.timeWindow or [0, None])[0] * ts),
                                         big if (n.timeWindow or [0, None])[1] is None else round(n.timeWindow[1] * ts) ]
                                       for n in nodes ]
        if par.get('maxTime') is not None:
            payload['maxTime'] = round(par['maxTime'] * ts)
        if par.get('maxDist') is not None:
            payload['maxDist'] = round(par['maxDist'] * TO_M[self.s.units.distance])
        dm, tm = TO_M[self.s.units.distance], ts
        self.valueUnit = self.s.units.distance

        def results(r):
            routes = []
            for k, route in enumerate(r['routes']):
                if len(route) <= 2:
                    continue
                entry = {'vehicle': vehicleIds[k], 'nodes': [ nodes[i].id for i in route ],
                         'load': sum(r['routeLoads'][k]), 'distance': r['routeDistances'][k][-1] / dm}
                if r.get('routeTimes'):
                    # schedule per node of the route and the totals of the route, in units.time
                    for key, name in (('routeArrivals', 'arrivals'), ('routeTimes', 'times'),
                                      ('routeWaitingTimes', 'waitingTimes'), ('routeServiceTimes', 'serviceTimes'),
                                      ('routeTravelTimes', 'travelTimes')):
                        if r.get(key):
                            entry[name] = [ t / tm for t in r[key][k] ]
                    entry['travelTime'] = sum(entry.get('travelTimes', []))
                    entry['waitingTime'] = sum(entry.get('waitingTimes', []))
                    entry['serviceTime'] = sum(entry.get('serviceTimes', []))
                    entry['duration'] = entry['times'][-1] - entry['times'][0]
                # the sections of the route: distance and - with times - arrival and waiting at their end
                entry['legs'] = []
                for j, (a, b) in enumerate(zip(route, route[1:])):
                    leg = {'from': nodes[a].id, 'to': nodes[b].id, 'value': D[a][b] / dm}
                    if entry.get('arrivals'):
                        leg['arrival'] = entry['arrivals'][j + 1]
                    if entry.get('waitingTimes'):
                        leg['waiting'] = entry['waitingTimes'][j + 1]
                    entry['legs'].append(leg)
                routes.append(entry)
            summary = {'totalDistance': r['objVal'] / dm, 'nrOfRoutes': len(routes), 'nrOfVehicles': len(capacities),
                       'totalLoad': sum(e['load'] for e in routes),
                       'longestRoute': max((e['distance'] for e in routes), default=0)}
            if routes and 'duration' in routes[0]:
                summary['longestDuration'] = max(e['duration'] for e in routes)
            return {'objVal': r['objVal'] / dm, 'routes': routes, 'summary': summary}
        return payload, results

    #*********** network flows ************
    def _network(self, type):
        """ nodes and arcs of the network of the problem - an undirected edge gives an arc in both directions """
        if not self.problem.network:
            raise ScenarioException(f'problem {self.problem.name}: {type} needs a network')
        net = self.s.networks[self.problem.network]
        ids = sorted({ e.from_ for e in net.edges } | { e.to for e in net.edges })
        nodes = [ self._node(i, 'node of the network') for i in ids ]
        pos = { n: k for k, n in enumerate(ids) }
        D, T = self._rawMatrix(nodes, nodes)
        arcs = []                                    # (edge, from, to, distance in m, time in s)
        for e in net.edges:
            directed = net.directed if e.directed is None else e.directed
            for a, b in ((e.from_, e.to),) if directed else ((e.from_, e.to), (e.to, e.from_)):
                arcs.append((e, a, b, D[pos[a]][pos[b]], T[pos[a]][pos[b]]))
        return nodes, pos, arcs

    def _rate(self, d, t, *levels):
        """ costs of a connection - costPerKm and costPerHour of the first level that has them, else of the scenario """
        cpk = next((l.costPerKm for l in levels if l is not None and l.costPerKm is not None), self.opts.costPerKm)
        cph = next((l.costPerHour for l in levels if l is not None and l.costPerHour is not None), self.opts.costPerHour)
        return d / 1000 * (cpk or 0) + t / 3600 * (cph or 0)

    def _nodeOptions(self, nodes):
        """ node capacities, balance and shortage costs for the library """
        mins = [ n.minCap or 0 for n in nodes ]
        maxs = [ None if unlimited(n.maxCap) else n.maxCap for n in nodes ]
        shortage = [ n.shortageCost or 0 for n in nodes ]
        balance = self.par.get('balance', 'auto')
        out = {'nodeMinCaps': mins if any(mins) else None,
               'nodeMaxCaps': maxs if any(m is not None for m in maxs) else None, 'balance': balance}
        if balance == 'auto' and any(shortage):
            out['shortageCosts'] = shortage
        return out

    def _nodeResults(self, nodes, r, values=lambda v: v, caps=None, load=None):
        """ flow through the nodes, unused supply and unmet demand - values maps a value of the library (e.g. a list
            per commodity); caps: capacities of the nodes (default maxCap), load: used capacity of a node flow """
        out = {}
        for key, name in (('nodeFlows', 'flow'), ('unusedSupplies', 'unusedSupply'), ('unmetDemands', 'unmetDemand')):
            for n, v in zip(nodes, r.get(key) or []):
                if (sum(v) if isinstance(v, list) else v) > 1e-9:
                    out.setdefault(n.id, {})[name] = values(v)
        caps = caps if caps is not None else [ None if unlimited(n.maxCap) else n.maxCap for n in nodes ]
        for k, (n, v, c) in enumerate(zip(nodes, r.get('nodeFlows') or [], caps)):
            used = _utilization(load(k, v) if load else v, c)
            if used:
                out.setdefault(n.id, {}).update(used)
        return out

    def _summary(self, r):
        return { k: r[k] for k in ('totalVarCosts', 'totalFixedCosts', 'totalShortageCosts') if k in r }

    def _flows(self, type):
        nodes, pos, arcs = self._network(type)
        kind = self._kind('costs' if (self.opts.costPerKm or self.opts.costPerHour) else 'distances')
        par = self.par
        edges = [ [pos[a], pos[b]] for _, a, b, _, _ in arcs ]
        costs = [ self._value(kind, d, t) for _, _, _, d, t in arcs ]
        minCaps = [ e.minFlow for e, *_ in arcs ]
        maxCaps = [ 'M' if unlimited(e.capacity) else e.capacity for e, *_ in arcs ]
        nodeOptions = self._nodeOptions(nodes)

        if type == 'mincostflow':
            self._flowEnds(nodes)
            payload = {'type': 'mincostflow', 'edges': edges, 'costs': costs,
                       'supplies': [ 0 if unlimited(n.supply) else n.supply for n in nodes ],
                       'demands': [ 0 if unlimited(n.demand) else n.demand for n in nodes ],
                       'minCaps': minCaps, 'maxCaps': maxCaps, **nodeOptions, **self._common()}
            if par.get('useFixedCosts'):
                payload['fixedCosts'] = [ e.fixedCost or 0 for e, *_ in arcs ]
        elif par.get('endpoints', 'nodes') == 'roles':
            # all suppliers -> all customers: an artificial source before the suppliers and an artificial sink after
            # the customers, their edges are limited by supply and demand (empty: unlimited)
            S, D = self._role('sources', 'supplier'), self._role('destinations', 'customer')
            outside = [ n.id for n in S + D if n.id not in pos ]
            if outside:
                self.warnings.append(f'maxflow: not in the network, ignored: {", ".join(outside)}')
            S, D = [ n for n in S if n.id in pos ], [ n for n in D if n.id in pos ]
            if not S or not D:
                raise ScenarioException(f'problem {self.problem.name}: maxflow needs suppliers and customers in the network')
            source, sink = len(nodes), len(nodes) + 1
            ends = [ (source, pos[n.id], n.supply) for n in S ] + [ (pos[n.id], sink, n.demand) for n in D ]
            extend = lambda v, fill: None if v is None else v + [fill, fill]
            payload = {'type': 'maxflow', 'edges': edges + [ [a, b] for a, b, _ in ends ], 'source': source, 'sink': sink,
                       'maxCaps': maxCaps + [ 'M' if unlimited(c) else c for _, _, c in ends ],
                       'minCaps': minCaps + [ 0 for _ in ends ], 'nrOfNodes': len(nodes) + 2,
                       'maxSolvingTime': par.get('maxSolvingTime'),
                       'nodeMinCaps': extend(nodeOptions['nodeMinCaps'], 0),
                       'nodeMaxCaps': extend(nodeOptions['nodeMaxCaps'], None)}
        else:
            payload = {'type': 'maxflow', 'edges': edges, 'source': pos[self._node(par['source'], 'source').id],
                       'sink': pos[self._node(par['sink'], 'sink').id], 'maxCaps': maxCaps, 'minCaps': minCaps,
                       'nrOfNodes': len(nodes), 'maxSolvingTime': par.get('maxSolvingTime'),
                       'nodeMinCaps': nodeOptions['nodeMinCaps'], 'nodeMaxCaps': nodeOptions['nodeMaxCaps']}

        def results(r):
            out = {'edges': []}
            for k, ((e, a, b, _, _), f) in enumerate(zip(arcs, r['flows'])):
                if f > 1e-9:
                    entry = {'from': a, 'to': b, 'flow': f, 'rate': costs[k], **_utilization(f, maxCaps[k])}
                    if r.get('usages'):
                        entry['used'] = r['usages'][k]
                    out['edges'].append(entry)
            nodeResults = self._nodeResults(nodes, r)
            if type == 'maxflow' and par.get('endpoints', 'nodes') == 'roles':
                # quantity of the suppliers and customers: flows of the artificial edges
                for (a, b, c), f in zip(ends, r['flows'][len(arcs):]):
                    n, sends = (nodes[b], True) if a == source else (nodes[a], False)
                    entry = nodeResults.setdefault(n.id, {})
                    entry['flow'] = f
                    if not unlimited(c) and c - f > 1e-9:
                        entry['unusedSupply' if sends else 'unmetDemand'] = c - f
            if nodeResults:
                out['nodes'] = nodeResults
            if self._summary(r):
                out['summary'] = self._summary(r)
            return out
        return payload, results

    def _multistagewlp(self):
        """ sources (supplier) -> warehouses (candidate, one or more stages) -> customers over the network -
            a warehouse has opening costs (fixedCost) and a capacity (capacity, otherwise maxCap) """
        nodes, pos, arcs = self._network('multistagewlp')
        if not any('candidate' in n.roles for n in nodes):
            raise ScenarioException(f'problem {self.problem.name}: multistagewlp needs nodes with role candidate (warehouses)')
        self._flowEnds(nodes)
        kind = self._kind('costs' if (self.opts.costPerKm or self.opts.costPerHour) else 'distances')
        par = self.par
        costs = [ self._value(kind, d, t) for _, _, _, d, t in arcs ]
        isWh = [ 'candidate' in n.roles for n in nodes ]
        options = self._nodeOptions(nodes)
        caps = [ (n.capacity if w and not unlimited(n.capacity) else (None if unlimited(n.maxCap) else n.maxCap))
                 for n, w in zip(nodes, isWh) ]
        payload = {'type': 'multistagewlp', 'edges': [ [pos[a], pos[b]] for _, a, b, _, _ in arcs ], 'costs': costs,
                   'supplies': [ 0 if unlimited(n.supply) else n.supply for n in nodes ],
                   'demands': [ 0 if unlimited(n.demand) else n.demand for n in nodes ],
                   'nodeFixedCosts': [ (n.fixedCost or 0) if w else 0 for n, w in zip(nodes, isWh) ],
                   'nodeMaxCaps': caps if any(c is not None for c in caps) else None,
                   'nodeMinCaps': options['nodeMinCaps'],
                   'minCaps': [ e.minFlow for e, *_ in arcs ],
                   'maxCaps': [ 'M' if unlimited(e.capacity) else e.capacity for e, *_ in arcs ],
                   'fixedCosts': [ e.fixedCost or 0 for e, *_ in arcs ],
                   'isSingleSource': bool(par.get('isSingleSource', False)),
                   **{ k: options[k] for k in ('balance', 'shortageCosts') if k in options }, **self._common()}

        def results(r):
            out = {'edges': []}
            for k, ((e, a, b, _, _), f) in enumerate(zip(arcs, r['flows'])):
                if f > 1e-9:
                    out['edges'].append({'from': a, 'to': b, 'flow': f, 'rate': costs[k], 'used': r['usages'][k],
                                         **_utilization(f, payload['maxCaps'][k])})
            nodeResults = self._nodeResults(nodes, r, caps=caps)
            for n, o in zip(nodes, r['openNodes']):
                if o is not None:
                    nodeResults.setdefault(n.id, {})['open'] = o
            out['nodes'] = nodeResults
            summary = self._summary(r)
            summary['totalOpeningCosts'] = r['totalOpeningCosts']
            summary['nrOfOpen'] = sum(1 for o in r['openNodes'] if o)
            out['summary'] = summary
            return out
        return payload, results

    def _shortestpath(self):
        """ shortest way from startNode to endNode in the network - one unit as a min cost flow; the way as a route
            with its sections like a tour """
        nodes, pos, arcs = self._network('shortestpath')
        kind = self._kind('distances')
        par = self.par
        name = lambda n: f'{n.name} ({n.id})' if n.name else n.id
        start, end = self._node(par.get('startNode'), 'startNode'), self._node(par.get('endNode'), 'endNode')
        for n in (start, end):
            if n.id not in pos:
                raise ScenarioException(f'problem {self.problem.name}: {name(n)} is no node of the network')
        if start.id == end.id:
            raise ScenarioException(f'problem {self.problem.name}: start and end are the same node')
        # is there a way at all? (the edges in their direction)
        succ = {}
        for _, a, b, _, _ in arcs:
            succ.setdefault(a, []).append(b)
        seen, todo = {start.id}, [start.id]
        while todo:
            for b in succ.get(todo.pop(), []):
                if b not in seen:
                    seen.add(b)
                    todo.append(b)
        if end.id not in seen:
            raise ScenarioException(f'problem {self.problem.name}: no way from {name(start)} to {name(end)} in the '
                                    f'network - check the direction of the edges')
        costs = [ self._value(kind, d, t) for _, _, _, d, t in arcs ]
        payload = {'type': 'mincostflow', 'edges': [ [pos[a], pos[b]] for _, a, b, _, _ in arcs ], 'costs': costs,
                   'supplies': [ 1 if n.id == start.id else 0 for n in nodes ],
                   'demands': [ 1 if n.id == end.id else 0 for n in nodes ],
                   'minCaps': [ 0 for _ in arcs ], 'maxCaps': [ 'M' for _ in arcs ], 'balance': 'exact',
                   **self._common()}

        def results(r):
            used = { a: (b, costs[k]) for k, ((_, a, b, _, _), f) in enumerate(zip(arcs, r['flows'])) if f > 0.5 }
            path, legs = [start.id], []
            while path[-1] != end.id and path[-1] in used and len(path) <= len(nodes):
                b, v = used[path[-1]]
                legs.append({'from': path[-1], 'to': b, 'value': v})
                path.append(b)
            length = sum(l['value'] for l in legs)
            return {'objVal': length, 'routes': [ {'nodes': path, 'legs': legs} ],
                    'summary': {'pathLength': length, 'nrOfLegs': len(legs)}}
        return payload, results

    def _mincostflow(self): return self._flows('mincostflow')
    def _maxflow(self): return self._flows('maxflow')

    def _multicommodity(self):
        nodes, pos, arcs = self._network('multicommodity')
        commodities = [ c for c in self.s.commodities if c.id in self.par.get('commodities', [ c.id for c in self.s.commodities ]) ]
        if not commodities:
            raise ScenarioException(f'problem {self.problem.name}: multicommodity needs commodities')
        self._flowEnds(nodes, perCommodity=True)
        self.valueUnit = 'costs'
        ids = [ c.id for c in commodities ]
        costs, factors = [], []
        for e, a, b, d, t in arcs:
            ec = e.commodities or {}
            costs.append([ self._rate(d, t, ec.get(c.id), c) for c in commodities ])
            factors.append([ ec[c.id].capacityFactor if c.id in ec and ec[c.id].capacityFactor is not None
                             else c.capacityFactor for c in commodities ])
        payload = {'type': 'multicommodity', 'edges': [ [pos[a], pos[b]] for _, a, b, _, _ in arcs ], 'costs': costs,
                   'supplies': [ [ (n.supplies or {}).get(k, 0) for k in ids ] for n in nodes ],
                   'demands': [ [ (n.demands or {}).get(k, 0) for k in ids ] for n in nodes ],
                   'minCaps': [ e.minFlow for e, *_ in arcs ],
                   'maxCaps': [ 'M' if unlimited(e.capacity) else e.capacity for e, *_ in arcs ],
                   'capacityFactors': factors, **self._nodeOptions(nodes), 'maxSolvingTime': self.par.get('maxSolvingTime'),
                   'isInteger': bool(self.par.get('isInteger', False))}
        if self.par.get('mipGap') is not None:
            payload['mipGap'] = self.par['mipGap']
        if any(n.capacityFactors for n in nodes):
            payload['nodeCapacityFactors'] = [ [ (n.capacityFactors or {}).get(k, 1) for k in ids ] for n in nodes ]
        perCommodity = lambda v: { k: x for k, x in zip(ids, v) if x > 1e-9 }

        def results(r):
            edges = []
            for k, ((e, a, b, _, _), f) in enumerate(zip(arcs, r['flows'])):
                if sum(f) > 1e-9:
                    cap = payload['maxCaps'][k]
                    entry = {'from': a, 'to': b, 'flow': sum(f), 'flows': perCommodity(f),
                             **_utilization(sum(x * c for x, c in zip(f, factors[k])), cap)}
                    if 'utilization' in entry:
                        # share of the capacity used by each commodity
                        entry['utilizations'] = { i: x * c / cap for i, x, c in zip(ids, f, factors[k]) if x > 1e-9 }
                    edges.append(entry)
            out = {'edges': edges}
            nodeFactors = payload.get('nodeCapacityFactors')
            nodeLoad = lambda k, v: sum(x * c for x, c in zip(v, nodeFactors[k] if nodeFactors else [1] * len(v)))
            nodeResults = self._nodeResults(nodes, r, perCommodity, load=nodeLoad)
            for k, (n, v) in enumerate(zip(nodes, r.get('nodeFlows') or [])):
                res = nodeResults.get(n.id)
                if res and 'capacity' in res:
                    fs = nodeFactors[k] if nodeFactors else [1] * len(v)
                    res['utilizations'] = { i: x * c / res['capacity'] for i, x, c in zip(ids, v, fs) if x > 1e-9 }
            if nodeResults:
                out['nodes'] = nodeResults
            if self._summary(r):
                out['summary'] = self._summary(r)
            return out
        return payload, results

    def _multimodal(self):
        nodes, pos, arcs = self._network('multimodal')
        modes = self.s.modes
        if not modes:
            raise ScenarioException(f'problem {self.problem.name}: multimodal needs modes')
        self._flowEnds(nodes)
        self.valueUnit = 'costs'
        costs, fixed, minCaps, maxCaps = [], [], [], []
        for e, a, b, d, t in arcs:
            row = ([], [], [], [])
            for m in modes:
                # without modes at the edge all modes are available, otherwise only the given ones
                em = (e.modes or {}).get(m.id) if e.modes is not None else Mode()
                if em is None:
                    for lst, v in zip(row, (None, 0, 0, 0)):
                        lst.append(v)
                    continue
                pick = lambda attr, default: next((v for v in (getattr(em, attr), getattr(m, attr)) if v is not None), default)
                cap = pick('capacity', None)
                for lst, v in zip(row, (self._rate(d, t, em, m), pick('fixedCost', 0), pick('minFlow', 0),
                                        None if unlimited(cap) else cap)):
                    lst.append(v)
            for lst, r_ in zip((costs, fixed, minCaps, maxCaps), row):
                lst.append(r_)
        payload = {'type': 'multimodal', 'edges': [ [pos[a], pos[b]] for _, a, b, _, _ in arcs ], 'costs': costs,
                   'supplies': [ 0 if unlimited(n.supply) else n.supply for n in nodes ],
                   'demands': [ 0 if unlimited(n.demand) else n.demand for n in nodes ],
                   'fixedCosts': fixed, 'minCaps': minCaps, 'maxCaps': maxCaps, **self._nodeOptions(nodes),
                   **self._common()}

        def results(r):
            edges = []
            for k, ((e, a, b, _, _), f) in enumerate(zip(arcs, r['flows'])):
                if sum(f) > 1e-9:
                    shares = [ x / c for x, c in zip(f, maxCaps[k]) if c is not None and c > 0 ]
                    edges.append({'from': a, 'to': b, 'flow': sum(f),
                                  'modes': { m.id: x for m, x in zip(modes, f) if x > 1e-9 },
                                  **({'utilization': max(shares)} if shares else {}),
                                  # utilization of the capacity of each mode
                                  **({'utilizations': { m.id: x / c for m, x, c in zip(modes, f, maxCaps[k])
                                                        if c is not None and c > 0 and x > 1e-9 }} if shares else {})})
            out = {'edges': edges}
            nodeResults = self._nodeResults(nodes, r)
            if nodeResults:
                out['nodes'] = nodeResults
            if self._summary(r):
                out['summary'] = self._summary(r)
            return out
        return payload, results
