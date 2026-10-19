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

from pydantic import BaseModel, ConfigDict, Field, model_validator
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
                 'mincostflow', 'maxflow')


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
    roles: list[Literal['supplier', 'customer', 'candidate', 'facility', 'depot', 'transit']] = []
    active: bool = True                          # False: the node is ignored
    supply: Unlimited = None
    minSupply: Unlimited = None
    maxSupply: Unlimited = None
    demand: Unlimited = None
    minDemand: Unlimited = None
    maxDemand: Unlimited = None
    capacity: Unlimited = None                   # candidate, facility
    fixedCost: Optional[float] = None            # candidate
    fixed: bool = False                          # candidate: must be open
    assignedTo: Optional[str] = None             # customer: fixed assignment to a candidate
    costFactor: float = 1.0                      # customer: factor on its costs
    timeWindow: Optional[list[Optional[float]]] = None   # [earliest, latest] in units.time, latest null: open
    serviceTime: float = 0                       # in units.time
    minThroughput: float = 0                     # networks: flow through the node
    maxThroughput: Unlimited = None

    @model_validator(mode='after')
    def check(self):
        if len(self.coordinates) != 2 or not (abs(self.coordinates[0]) <= 90 and abs(self.coordinates[1]) <= 180):
            raise ValueError(f'node {self.id}: coordinates [lat, lon] expected')
        return self

class Mode(Item):
    """ transport mode of an edge - costs from the OSM distance and time """
    costPerKm: Optional[float] = None
    costPerHour: Optional[float] = None
    fixedCost: Optional[float] = None
    minFlow: float = 0
    capacity: Unlimited = None

class Edge(Item):
    """ allowed connection - its length and time come from the OSM servers """
    from_: str = Field(alias='from')
    to: str
    directed: Optional[bool] = None              # default: directed of the network
    capacity: Unlimited = None
    minFlow: float = 0
    fixedCost: Optional[float] = None
    modes: Optional[dict[str, Mode]] = None

class Network(Item):
    directed: bool = False
    edges: list[Edge]

class Vehicle(Item):
    id: str
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
        for n in self.nodes:
            if n.assignedTo and n.assignedTo not in known:
                raise ValueError(f'node {n.id}: unknown assignedTo {n.assignedTo}')
        for v in self.vehicles:
            if v.depot and v.depot not in known:
                raise ValueError(f'vehicle {v.id}: unknown depot {v.depot}')
        for p in self.problems:
            if p.network and p.network not in self.networks:
                raise ValueError(f'problem {p.name}: unknown network {p.network}')
        return self

    def dataHash(self):
        """ hash of the data (without names, descriptions and problems) - a solution refers to it """
        data = self.model_dump(by_alias=True, exclude={'name', 'description', 'source', 'problems'})
        return 'sha256:' + hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def unlimited(v):
    return v is None or v == 'M'


#*************** solver ************************************************

class ScenarioSolver:
    """ translates the problems of a scenario into items of the REST server and maps the results to node ids """

    def __init__(self, scenario, backend):
        self.s = scenario
        self.backend = backend
        self.nodes = { n.id: n for n in scenario.nodes if n.active }

    #*********** common ************
    def solve(self, problem, parameters=None):
        """ solution document of a problem - parameters override the parameters of the problem """
        self.problem = problem
        self.par = {**problem.parameters, **(parameters or {})}
        self.opts = self.s.matrix.model_copy(update=problem.matrix.model_dump(exclude_unset=True)) if problem.matrix \
                    else self.s.matrix
        self.warnings = []
        self.matrixInfo = None
        self.valueUnit = None
        handler = getattr(self, '_' + problem.type)
        payload, mapResults = handler()
        payload = {k: v for k, v in payload.items() if v is not None}
        answer = self.backend.solve(payload)

        solution = {
            'format': SOLUTION_FORMAT, 'version': VERSION,
            'created': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
            'scenario': {'id': self.s.id, 'hash': self.s.dataHash()},
            'problem': {**problem.model_dump(exclude_none=True), 'parameters': self.par},
            'status': answer.get('status'), 'message': answer.get('message'),
            'units': self.s.units.model_dump(),
        }
        if self.valueUnit:
            solution['valueUnit'] = self.valueUnit         # unit of objVal and of the values of the connections
        if self.matrixInfo:
            solution['matrixInfo'] = self.matrixInfo
        if answer.get('status') == 'solution':
            native = answer['results']
            results = {'objVal': native['objVal']}
            results.update(mapResults(native))
            results['solvingTime'] = native.get('solvingTime')
            results['native'] = native
            solution['results'] = results
        if self.warnings:
            solution['warnings'] = self.warnings
        return solution

    def _role(self, role, default):
        role = (self.par.get('roles') or {}).get(role, default)
        nodes = [ n for n in self.nodes.values() if role in n.roles ]
        if not nodes:
            raise ScenarioException(f'problem {self.problem.name}: no active nodes with role {role}')
        return nodes

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
        kind = self._kind()
        C = self._costFactors(self._matrix(S, D, kind), D, kind)
        par = self.par
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
                   'objSense': par.get('objSense', 'min'), 'isSingleSource': par.get('isSingleSource', False),
                   'minBlock': par.get('minBlock'), 'maxBlock': par.get('maxBlock'),
                   'sourceNames': [ n.id for n in S ], 'destinationNames': [ n.id for n in D ], **self._common()}
        if par.get('useSupplyRanges'):
            payload['minSupplies'] = [ n.minSupply or 0 for n in S ]
            payload['maxSupplies'] = [ n.supply if n.maxSupply is None else n.maxSupply for n in S ]
        if par.get('useDemandRanges'):
            payload['minDemands'] = [ n.minDemand or 0 for n in D ]
            payload['maxDemands'] = [ n.demand if n.maxDemand is None else n.maxDemand for n in D ]
        if par.get('useCapacities'):
            payload['capacities'] = pairMatrix('capacity', 'M')
        if par.get('useFixedCosts'):
            payload['fixedCosts'] = pairMatrix('fixedCost', 0)

        def results(r):
            flows = r['flows']
            return {
                'summary': {k: r[k] for k in ('totalCosts', 'totalVarCosts', 'totalFixedCosts', 'totalFlow',
                                              'minCostRate', 'maxCostRate') if k in r},
                'nodes': {**{ n.id: {'flow': f} for n, f in zip(S, r['sourceFlows']) },
                          **{ n.id: {'flow': f} for n, f in zip(D, r['destinationFlows']) }},
                'assignments': [ {'from': S[i].id, 'to': D[j].id, 'flow': flows[i][j], 'rate': C[i][j]}
                                 for i in range(len(S)) for j in range(len(D)) if flows[i][j] > 1e-9 ]}
        return payload, results

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
        F = [ n for n in self.nodes.values() if 'facility' in n.roles ]
        par = self.par
        p = par.get('p', len(F))
        if not p:
            raise ScenarioException(f'problem {self.problem.name}: p or nodes with role facility are needed')
        isCap = par.get('isCapacitated', False)
        weighted = par.get('isDemandWeighted', True)
        demands = [ n.demand if n.demand is not None else 1 for n in D ]
        payload = {'type': type, 'p': p, 'coordinates': [ n.coordinates for n in D ],
                   'isSingleSource': par.get('isSingleSource', True), 'nrOfStarts': par.get('nrOfStarts'),
                   **self._common()}
        if isCap:
            if len(F) != p or any(unlimited(f.capacity) for f in F):
                raise ScenarioException(f'problem {self.problem.name}: capacitated - {p} facilities with a capacity needed')
            payload['capacities'] = [ f.capacity for f in F ]
            payload['demands'] = demands
            if not weighted:
                self.warnings.append('isDemandWeighted false with capacities: the costs are weighted with the demands')
        elif weighted or type == 'contpcentre':
            payload['demands'] = demands
        if type == 'contpmedian' and any(n.costFactor != 1 for n in D):
            payload['costFactors'] = [ n.costFactor for n in D ]
        elif type == 'contpcentre':
            self._warnIgnored(D, ['costFactor'])
        if self.opts.matrixSource != 'beeline':
            self.warnings.append('continuous location problems use great-circle distances, not the road network')
        scale = 1000 / TO_M[self.s.units.distance]                  # results in km
        self.valueUnit = self.s.units.distance
        ids = [ f.id for f in F ] if len(F) == p else [ f'F{k+1}' for k in range(p) ]

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
        # startNode / endNode None: open start / open end
        start = self.par['startNode'] if 'startNode' in self.par else nodes[0].id
        end = self.par['endNode'] if 'endNode' in self.par else start
        pos = { n.id: i for i, n in enumerate(nodes) }
        # OR-Tools needs integers - m, s or 1/100 of the costs, without a connection a very long one
        scale = {'distances': TO_M[self.s.units.distance], 'times': TO_S[self.s.units.time], 'costs': 100}[kind]
        M = [ [ 10**12 if v == 'M' else round(v * scale) for v in row ] for row in self._matrix(nodes, nodes, kind) ]
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
            out = {'objVal': r['objVal'] / scale, 'routes': [ {'nodes': route} ]}
            if self.problem.network and self.problem.networkMode == 'shortestPaths':
                path = [route[0]]
                for a, b in zip(route, route[1:]):
                    path += self._path(a, b)[1:]
                out['routes'][0]['path'] = path
            return out
        return payload, results

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
        payload = {'type': 'cpp', 'edges': edges, 'edgeWeights': weights, 'edgeTypes': types,
                   'startNode': pos[self._node(start, 'startNode').id], **self._common()}

        def results(r):
            return {'routes': [ {'nodes': [ ids[i] for i in r['eulerTour'] ]} ],
                    'edges': [ {'from': e.from_, 'to': e.to, 'usages': u, 'value': w}
                               for e, u, w in zip(net.edges, r['edgeUsages'], weights) ]}
        return payload, results

    def _vrp(self):
        depots = [ n for n in self.nodes.values() if 'depot' in n.roles ]
        depotId = self.par.get('depot') or (self.s.vehicles[0].depot if self.s.vehicles and self.s.vehicles[0].depot
                                             else (depots[0].id if len(depots) == 1 else None))
        if depotId is None:
            raise ScenarioException(f'problem {self.problem.name}: no depot - parameter depot or one node with role depot')
        depot = self._node(depotId, 'depot')
        customers = [ n for n in self._role('destinations', 'customer') if n.id != depot.id ]
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
        # OR-Tools needs integers - meters and seconds
        payload = {'type': 'vrp', 'distances': [ [ round(v) for v in row ] for row in D ],
                   'demands': [0] + [ n.demand or 0 for n in customers ], 'capacities': capacities, 'depot': 0,
                   'maxSolvingTime': par.get('maxSolvingTime')}
        usesTimes = useTW or par.get('maxTime') is not None
        if usesTimes:
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
                    entry['times'] = [ t / tm for t in r['routeTimes'][k] ]
                routes.append(entry)
            return {'objVal': r['objVal'] / dm, 'routes': routes, 'summary': {'nrOfRoutes': len(routes)}}
        return payload, results

    #*********** network flows ************
    def _flows(self, type):
        if not self.problem.network:
            raise ScenarioException(f'problem {self.problem.name}: {type} needs a network')
        net = self.s.networks[self.problem.network]
        kind = self._kind('costs' if (self.opts.costPerKm or self.opts.costPerHour) else 'distances')
        values = self._edgeValues(net, kind)
        par = self.par

        # nodes with a throughput limit are split into in and out - the arc in -> out carries the throughput
        ids = sorted({ e.from_ for e in net.edges } | { e.to for e in net.edges })
        split = { i for i in ids if not unlimited(self.nodes[i].maxThroughput) and self.nodes[i].maxThroughput > 0
                  or self.nodes[i].minThroughput > 0 }
        names = []
        for i in ids:
            names += [i + '#in', i + '#out'] if i in split else [i]
        pos = { n: k for k, n in enumerate(names) }
        inNode = lambda i: pos[i + '#in'] if i in split else pos[i]
        outNode = lambda i: pos[i + '#out'] if i in split else pos[i]

        arcs, costs, minCaps, maxCaps, fixedCosts, origin = [], [], [], [], [], []
        for e in net.edges:
            directed = net.directed if e.directed is None else e.directed
            for a, b in ((e.from_, e.to),) if directed else ((e.from_, e.to), (e.to, e.from_)):
                arcs.append([outNode(a), inNode(b)])
                costs.append(values[(a, b)])
                minCaps.append(e.minFlow)
                maxCaps.append('M' if unlimited(e.capacity) else e.capacity)
                fixedCosts.append(e.fixedCost or 0)
                origin.append((a, b))
        for i in sorted(split):
            n = self.nodes[i]
            arcs.append([pos[i + '#in'], pos[i + '#out']])
            costs.append(0)
            minCaps.append(n.minThroughput)
            maxCaps.append('M' if unlimited(n.maxThroughput) or n.maxThroughput == 0 else n.maxThroughput)
            fixedCosts.append(0)
            origin.append((i, None))

        # supplies at the node or its in node, demands at the node or its out node
        supplies, demands = [0] * len(names), [0] * len(names)
        for i in ids:
            n = self.nodes[i]
            if not unlimited(n.supply) and n.supply:
                supplies[inNode(i)] = n.supply
            if not unlimited(n.demand) and n.demand:
                demands[outNode(i)] = n.demand

        if type == 'mincostflow':
            payload = {'type': 'mincostflow', 'edges': arcs, 'costs': costs, 'supplies': supplies, 'demands': demands,
                       'minCaps': minCaps, 'maxCaps': maxCaps, **self._common()}
            if par.get('useFixedCosts'):
                payload['fixedCosts'] = fixedCosts
        else:
            payload = {'type': 'maxflow', 'edges': arcs, 'source': outNode(self._node(par['source'], 'source').id),
                       'sink': inNode(self._node(par['sink'], 'sink').id), 'maxCaps': maxCaps, 'minCaps': minCaps,
                       'nrOfNodes': len(names), 'maxSolvingTime': par.get('maxSolvingTime')}

        def results(r):
            edges, nodes = [], {}
            for (a, b), f, c, k in zip(origin, r['flows'], costs, range(len(origin))):
                if b is None:
                    nodes[a] = {'throughput': f}
                elif f > 1e-9:
                    entry = {'from': a, 'to': b, 'flow': f, 'rate': c}
                    if r.get('usages'):
                        entry['used'] = r['usages'][k]
                    edges.append(entry)
            out = {'edges': edges}
            if nodes:
                out['nodes'] = nodes
            if 'totalVarCosts' in r:
                out['summary'] = {'totalVarCosts': r['totalVarCosts'], 'totalFixedCosts': r['totalFixedCosts']}
            return out
        return payload, results

    def _mincostflow(self): return self._flows('mincostflow')
    def _maxflow(self): return self._flows('maxflow')
