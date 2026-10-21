""" network flow problems

    MinCostFlow          min cost flow problem                                           - LP, minCostFlow.cmpl
                         with fixed costs of the edges                                   - MIP, minCostFlowFixed.cmpl
    MaxFlow              maximal flow from source to sink                                - LP, maxFlow.cmpl
    MultiCommodityFlow   min cost flow of several commodities with joint arc capacities  - LP, multiCommodity.cmpl
    MultiModalFlow       min cost flow with several modes (e.g. truck, train) and fixed costs - MIP, multimodal.cmpl

    All models are solved with CMPL and HiGHS.

    Nodes are 0-based indices, edges are lists [[i, j], ...] of node indices.
    Capacities None or 'M' mean unlimited. Results are lists in the order of the edges.

    All classes accept capacities of the nodes and (except MaxFlow) unequal totals of supply and demand:
        nodeMinCaps, nodeMaxCaps   minimal and maximal flow through a node (incl. its own supply and demand)
        balance                    'auto' (default): a surplus of supply remains at the sources, a surplus of demand
                                   remains unmet at the sinks, 'exact': the totals must be equal
        shortageCosts              costs per unit of unmet demand of every sink (default 0, balance 'auto')
    Internally the network is extended - a node with a capacity is split into an in and an out node, dummy nodes
    take the surplus. The results refer to the original nodes and edges only.
"""

from .tools import *
from .exception import *

from pyCmpl import *

import os
import tempfile
import shutil
import pathlib
import logging

logger = logging.getLogger(__name__)


def _isUnlimited(val):
    return val is None or (isinstance(val, str) and val.strip().upper() == 'M')

def _vector(vector, length, name, default):
    """ optional vector of numbers - None gives the default for every element """
    if vector is None:
        return [default] * length
    if not isinstance(vector, (list, tuple)) or len(vector) != length:
        raise LogLabException(f'LogisticsLab error: Wrong {name} - {length} values expected')
    return list(vector)

def _matrix(matrix, rows, cols, name, default):
    """ optional matrix [rows x cols] - None gives the default for every element """
    if matrix is None:
        return [ [default] * cols for _ in range(rows) ]
    if not isinstance(matrix, (list, tuple)) or len(matrix) != rows or \
       not all(isinstance(r, (list, tuple)) and len(r) == cols for r in matrix):
        raise LogLabException(f'LogisticsLab error: Wrong {name} - matrix [{rows} x {cols}] expected')
    return [ list(r) for r in matrix ]

def _numbers(values, name, allowUnlimited=False):
    for v in values:
        if allowUnlimited and _isUnlimited(v):
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise LogLabException(f'LogisticsLab error: Wrong {name} <{v}>')

def _checkBalance(supplies, demands, name=''):
    if abs(sum(supplies) - sum(demands)) > 1e-9:
        raise LogLabException(f'LogisticsLab error: Total supply {sum(supplies)} unequal to total demand {sum(demands)}{name} '
                              '- add a dummy node to balance the problem')

def _checkUniqueEdges(edges):
    if len(set(map(tuple, edges))) != len(edges):
        raise LogLabException('LogisticsLab error: Parallel edges (i,j) are not supported by this model')


#*************** CMPL base ************************************************
class _CmplFlow(object):
    """ common part of the flow problems solved with CMPL and HiGHS """

    def __init__(self, edges, nrOfNodes, cmplFile, mipGap, maxSolvingTime):
        self._nrOfNodes = nrOfNodes
        self._edges = [ tuple(e) for e in setEdges(edges, nrOfNodes) ]
        _checkUniqueEdges(self._edges)
        self._nrOfEdges = len(self._edges)

        self._mipGap = setMipGap(mipGap)
        self._maxSolvingTime = setMaxSolvingTime(maxSolvingTime)

        self._model = None
        self._modelName = str(pathlib.Path(__file__).parent.absolute())+os.sep+cmplFile
        self._cmplFile = cmplFile

        self._solutionStatus = False
        self._objValue = 0
        self._message = ''

    def _sets(self, nrOfIndices=None, name=None):
        """ N nodes, A arcs and optionally an index set 0..nrOfIndices-1 (commodities, modes) """
        nodes = CmplSet('N')
        nodes.setValues(0, self._nrOfNodes-1)
        arcs = CmplSet('A', 2)
        arcs.setValues(self._edges)
        if name is None:
            return nodes, arcs
        idx = CmplSet(name)
        idx.setValues(0, nrOfIndices-1)
        return nodes, arcs, idx

    def _parameters(self, definitions):
        """ CMPL parameters of (name, sets, values) - sets () for a scalar """
        par = []
        for name, s, values in definitions:
            p = CmplParameter(name, *s)
            p.setValues(values)
            par.append(p)
        return par

    def _run(self, sets, parameters):
        # own directory for every run - parallel jobs of the server must not share the model file
        tmpDir = tempfile.mkdtemp(prefix='nwf_')
        modelName = os.path.join(tmpDir, self._cmplFile)
        shutil.copyfile(self._modelName, modelName)

        self._model = Cmpl(modelName)
        self._model.setSets(*sets)
        self._model.setParameters(*parameters)
        self._model.setOutput(False)
        self._model.setOption('-solver highs')
        self._model.setOption(f'-opt highs time_limit={self._maxSolvingTime}')
        if self._mipGap > 0:
            self._model.setOption(f'-opt highs mip_rel_gap={self._mipGap}')

        try:
            self._model.solve()
            ok = self._model.solverStatus == SOLVER_OK
            self._message = self._model.solverMessage if not ok else 'optimal'
        except CmplException as e:
            # CMPL reports infeasible models of HiGHS as error
            ok = False
            self._message = str(e).strip() or 'infeasible or no solution within the time limit'
        finally:
            shutil.rmtree(tmpDir, ignore_errors=True)

        self._solutionStatus = ok
        if ok:
            self._objValue = self._model.solution.value
        else:
            logger.info(f'    ... no solution has been found ({self._message})')
        return ok

    def _activity(self, var, key):
        """ activity of a variable - with %display nonZeros variables with activity 0 are missing """
        try:
            return var[key].activity
        except Exception:
            return 0

    def isSolution(self):
        return self._solutionStatus

    def getObjValue(self):
        return self._objValue

    def getMessage(self):
        return self._message
#*************** end CMPL base ********************************************




#*************** single commodity flows ************************************************
class _SingleFlow(_CmplFlow):
    """ flow of one commodity with minimal and maximal capacities of the edges - LP, MIP with fixed costs """

    def __init__(self, edges, nrOfNodes, cmplFile, minCaps, maxCaps, maxSolvingTime, mipGap=0.0):
        super().__init__(edges, nrOfNodes, cmplFile, mipGap, maxSolvingTime)
        self._minCaps = _vector(minCaps, self._nrOfEdges, 'minimal capacities', 0)
        self._maxCaps = _vector(maxCaps, self._nrOfEdges, 'maximal capacities', None)
        _numbers(self._minCaps, 'minimal capacity')
        _numbers(self._maxCaps, 'maximal capacity', allowUnlimited=True)

        # outgoing edges of every node
        self._out = [ [] for _ in range(nrOfNodes) ]
        for e, (a, b) in enumerate(self._edges):
            self._out[a].append(e)

        self._flows = [ 0 for _ in range(self._nrOfEdges) ]

    def _capacities(self, bound):
        """ CMPL needs numbers - unlimited capacities are replaced by bound, a value that is never exceeded """
        return [ bound if _isUnlimited(c) else c for c in self._maxCaps ]

    def _readFlows(self):
        self._flows = [ self._activity(self._model.x, (i, j)) for (i, j) in self._edges ]

    def getFlows(self):
        """ flow on every edge, in the order of the edges """
        return self._flows
#*************** end single commodity flows ********************************************


#*************** MinCostFlow ************************************************
class _MinCostFlowModel(_SingleFlow):
    """ min cost flow problem (minCostFlow.cmpl), with fixed costs (minCostFlowFixed.cmpl)

        edges       [[i, j], ...], nodes 0..len(supplies)-1, no parallel edges
        costs       cost rate of every edge
        supplies    supply of every node, demands: demand of every node (default 0) - totals must be equal
        minCaps     minimal flow of every edge (default 0), maxCaps: maximal flow (default unlimited)
        fixedCosts  optional fixed costs of every edge - paid if the edge carries flow (MIP, mipGap)
                    a minimal flow minCaps > 0 forces the use of the edge
    """

    #*********** constructor **********
    def __init__(self, edges, costs, supplies, demands=None, minCaps=None, maxCaps=None, maxSolvingTime=10,
                 fixedCosts=None, mipGap=0.001):
        self._supplies = setNumVector(supplies)
        n = len(self._supplies)
        self._demands = _vector(demands, n, 'demands', 0)
        _numbers(self._demands, 'demand')
        _checkBalance(self._supplies, self._demands)

        self._isFixedCosts = fixedCosts is not None
        super().__init__(edges, n, 'minCostFlowFixed.cmpl' if self._isFixedCosts else 'minCostFlow.cmpl',
                         minCaps, maxCaps, maxSolvingTime, mipGap if self._isFixedCosts else 0.0)
        self._costs = _vector(costs, self._nrOfEdges, 'costs', None)
        _numbers(self._costs, 'cost')
        self._fixedCosts = _vector(fixedCosts, self._nrOfEdges, 'fixed costs', 0)
        _numbers(self._fixedCosts, 'fixed cost')
        self._usages = [ 0 for _ in range(self._nrOfEdges) ]
    #*********** end constructor ******

    def solve(self):
        logger.info('    ... solving min cost flow problem' + (' with fixed costs' if self._isFixedCosts else ''))
        nodes, arcs = self._sets()
        # no flow on an edge exceeds the total supply and the flows forced by minimal capacities
        maxCaps = self._capacities(sum(self._supplies) + sum(self._minCaps))
        definitions = [('c', (arcs,), self._costs), ('minKap', (arcs,), self._minCaps), ('maxKap', (arcs,), maxCaps),
                       ('a', (nodes,), self._supplies), ('b', (nodes,), self._demands)]
        if self._isFixedCosts:
            definitions.append(('F', (arcs,), self._fixedCosts))
        if self._run((nodes, arcs), self._parameters(definitions)):
            self._readFlows()
            # used: the edge carries flow or its fixed costs are paid - without fixed costs y can be 1 without flow
            self._usages = [ 1 if self._flows[e] > 1e-9 or (self._isFixedCosts and self._fixedCosts[e] > 0
                                                             and round(self._activity(self._model.y, (i, j))) == 1) else 0
                             for e, (i, j) in enumerate(self._edges) ]

    def isFixedCosts(self):
        return self._isFixedCosts

    def getUsages(self):
        """ 1 if the edge is used """
        return self._usages

    def getVarCosts(self):
        return sum(c * f for c, f in zip(self._costs, self._flows))

    def getFixedCosts(self):
        return sum(fc * u for fc, u in zip(self._fixedCosts, self._usages))
#*************** end MinCostFlow ********************************************


#*************** MaxFlow ************************************************
class _MaxFlowModel(_SingleFlow):
    """ maximal flow from source to sink (maxFlow.cmpl)

        edges       [[i, j], ...], nodes 0..nrOfNodes-1 (default: largest node index of the edges + 1), no parallel edges
        maxCaps     maximal flow of every edge, minCaps: minimal flow (default 0)
        objective value: the maximal flow from source to sink
    """

    #*********** constructor **********
    def __init__(self, edges, source, sink, maxCaps, minCaps=None, nrOfNodes=None, maxSolvingTime=10):
        if nrOfNodes is None:
            nodes = [ n for e in setEdges(edges) for n in e ]
            nrOfNodes = max(nodes) + 1 if nodes else 0
        for name, node in (('source', source), ('sink', sink)):
            if not isinstance(node, int) or not 0 <= node < nrOfNodes:
                raise LogLabException(f'LogisticsLab error: Wrong {name} <{node}>')
        if source == sink:
            raise LogLabException('LogisticsLab error: Source and sink must be different')

        super().__init__(edges, nrOfNodes, 'maxFlow.cmpl', minCaps, maxCaps, maxSolvingTime)
        self._source = source
        self._sink = sink
    #*********** end constructor ******

    def solve(self):
        logger.info('    ... solving maximal flow problem')
        if self.__unlimitedPath():
            raise LogLabException('LogisticsLab error: The maximal flow is unbounded - there is a path from source to sink '
                                  'without capacity limits')
        nodes, arcs = self._sets()
        # every path from source to sink has a finite capacity - no flow exceeds the sum of all finite capacities
        maxCaps = self._capacities(sum(c for c in self._maxCaps if not _isUnlimited(c)) + sum(self._minCaps))
        par = self._parameters((('minKap', (arcs,), self._minCaps), ('maxKap', (arcs,), maxCaps),
                                ('q', (), self._source), ('s', (), self._sink)))
        if self._run((nodes, arcs), par):
            self._readFlows()

    def __unlimitedPath(self):
        """ True if the sink can be reached from the source only via edges without capacity limits """
        reached, todo = {self._source}, [self._source]
        while todo:
            i = todo.pop()
            for e in self._out[i]:
                j = self._edges[e][1]
                if _isUnlimited(self._maxCaps[e]) and j not in reached:
                    reached.add(j)
                    todo.append(j)
        return self._sink in reached
#*************** end MaxFlow ********************************************


#*************** MultiCommodityFlow ************************************************
class _MultiCommodityModel(_CmplFlow):
    """ min cost flow problem of several commodities with joint capacities of the edges

        edges            [[i, j], ...], nodes 0..len(supplies)-1, no parallel edges
        costs            [edges x commodities] cost rates
        supplies         [nodes x commodities], demands: [nodes x commodities] (default 0) - totals per commodity must be equal
        minCaps          joint minimal capacity of every edge (default 0), maxCaps: joint maximal capacity (default unlimited)
        capacityFactors  [edges x commodities] capacity used by one unit of a commodity (default 1)
        isInteger        integer flows (MIP with mipGap) instead of the LP
    """

    #*********** constructor **********
    def __init__(self, edges, costs, supplies, demands=None, minCaps=None, maxCaps=None, capacityFactors=None,
                 maxSolvingTime=60, isInteger=False, mipGap=0.001):
        if not isinstance(supplies, (list, tuple)) or not supplies or not isinstance(supplies[0], (list, tuple)):
            raise LogLabException('LogisticsLab error: Wrong supplies - matrix [nodes x commodities] expected')
        n = len(supplies)
        self._nrOfCommodities = len(supplies[0])
        k = self._nrOfCommodities

        self._isInteger = bool(isInteger)
        super().__init__(edges, n, 'multiCommodity.cmpl', mipGap if self._isInteger else 0.0, maxSolvingTime)

        self._supplies = _matrix(supplies, n, k, 'supplies', 0)
        self._demands = _matrix(demands, n, k, 'demands', 0)
        self._costs = _matrix(costs, self._nrOfEdges, k, 'costs', None)
        self._capacityFactors = _matrix(capacityFactors, self._nrOfEdges, k, 'capacity factors', 1)
        for name, m in (('supply', self._supplies), ('demand', self._demands), ('cost', self._costs),
                        ('capacity factor', self._capacityFactors)):
            for row in m:
                _numbers(row, name)
        for c in range(k):
            _checkBalance([r[c] for r in self._supplies], [r[c] for r in self._demands], f' of commodity {c}')

        self._minCaps = _vector(minCaps, self._nrOfEdges, 'minimal capacities', 0)
        self._maxCaps = _vector(maxCaps, self._nrOfEdges, 'maximal capacities', None)
        _numbers(self._minCaps, 'minimal capacity')
        _numbers(self._maxCaps, 'maximal capacity', allowUnlimited=True)
        # unlimited: the capacity used by the total supply of all commodities is never exceeded
        bound = sum(max(self._capacityFactors[e]) for e in range(self._nrOfEdges)) * sum(map(sum, self._supplies)) + 1
        self._maxCaps = [ bound if _isUnlimited(c) else c for c in self._maxCaps ]

        self._flows = [ [0] * k for _ in range(self._nrOfEdges) ]
    #*********** end constructor ******

    def solve(self):
        logger.info('    ... solving multi-commodity flow problem')
        nodes, arcs, commodities = self._sets(self._nrOfCommodities, 'K')
        par = self._parameters((('c', (arcs, commodities), self._costs), ('cf', (arcs, commodities), self._capacityFactors),
                                ('a', (nodes, commodities), self._supplies), ('b', (nodes, commodities), self._demands),
                                ('minKap', (arcs,), self._minCaps), ('maxKap', (arcs,), self._maxCaps),
                                ('isInteger', (), int(self._isInteger))))

        if self._run((nodes, arcs, commodities), par):
            self._flows = [ [ self._activity(self._model.x, (i, j, c)) for c in range(self._nrOfCommodities) ]
                            for (i, j) in self._edges ]

    def getFlows(self):
        """ [edges x commodities] flows """
        return self._flows
#*************** end MultiCommodityFlow ********************************************


#*************** MultiModalFlow ************************************************
class _MultiModalModel(_CmplFlow):
    """ min cost flow problem with several modes (e.g. truck, train, ship) on the edges and fixed costs

        edges       [[i, j], ...], nodes 0..len(supplies)-1, no parallel edges
        costs       [edges x modes] cost rates - None: the mode is not available on this edge
        supplies    supply of every node, demands: demand of every node (default 0) - totals must be equal
        fixedCosts  [edges x modes] fixed costs if a mode is used on an edge (default 0)
        minCaps     [edges x modes] minimal flow if a mode is used (default 0), maxCaps: maximal flow (default unlimited)
    """

    #*********** constructor **********
    def __init__(self, edges, costs, supplies, demands=None, fixedCosts=None, minCaps=None, maxCaps=None,
                 mipGap=0.001, maxSolvingTime=60):
        self._supplies = setNumVector(supplies)
        n = len(self._supplies)
        self._demands = _vector(demands, n, 'demands', 0)
        _numbers(self._demands, 'demand')
        _checkBalance(self._supplies, self._demands)

        super().__init__(edges, n, 'multimodal.cmpl', mipGap, maxSolvingTime)

        if not isinstance(costs, (list, tuple)) or not costs or not isinstance(costs[0], (list, tuple)):
            raise LogLabException('LogisticsLab error: Wrong costs - matrix [edges x modes] expected')
        self._nrOfModes = len(costs[0])
        v = self._nrOfModes
        self._costs = _matrix(costs, self._nrOfEdges, v, 'costs', None)
        self._fixedCosts = _matrix(fixedCosts, self._nrOfEdges, v, 'fixed costs', 0)
        self._minCaps = _matrix(minCaps, self._nrOfEdges, v, 'minimal capacities', 0)
        self._maxCaps = _matrix(maxCaps, self._nrOfEdges, v, 'maximal capacities', None)
        for row in self._costs:
            _numbers([c for c in row if c is not None], 'cost')
        for name, m in (('fixed cost', self._fixedCosts), ('minimal capacity', self._minCaps)):
            for row in m:
                _numbers(row, name)
        for row in self._maxCaps:
            _numbers(row, 'maximal capacity', allowUnlimited=True)

        # unlimited: the flow on an edge never exceeds the total supply
        bound = sum(self._supplies)
        for e in range(self._nrOfEdges):
            for m in range(v):
                if self._costs[e][m] is None:
                    # mode not available on this edge
                    self._costs[e][m], self._fixedCosts[e][m], self._minCaps[e][m], self._maxCaps[e][m] = 0, 0, 0, 0
                elif _isUnlimited(self._maxCaps[e][m]):
                    self._maxCaps[e][m] = bound

        self._flows = [ [0] * v for _ in range(self._nrOfEdges) ]
        self._usages = [ [0] * v for _ in range(self._nrOfEdges) ]
    #*********** end constructor ******

    def solve(self):
        logger.info('    ... solving multi-modal flow problem')
        nodes, arcs, modes = self._sets(self._nrOfModes, 'V')
        par = self._parameters((('c', (arcs, modes), self._costs), ('F', (arcs, modes), self._fixedCosts),
                                ('minKap', (arcs, modes), self._minCaps), ('maxKap', (arcs, modes), self._maxCaps),
                                ('a', (nodes,), self._supplies), ('b', (nodes,), self._demands)))

        if self._run((nodes, arcs, modes), par):
            self._flows = [ [ self._activity(self._model.x, (i, j, m)) for m in range(self._nrOfModes) ] for (i, j) in self._edges ]
            # used: the mode carries flow or its fixed costs are paid - without fixed costs y can be 1 without flow
            self._usages = [ [ 1 if self._flows[e][m] > 1e-9 or
                                    (self._fixedCosts[e][m] > 0 and round(self._activity(self._model.y, (i, j, m))) == 1) else 0
                               for m in range(self._nrOfModes) ] for e, (i, j) in enumerate(self._edges) ]

    def getFlows(self):
        """ [edges x modes] flows """
        return self._flows

    def getUsages(self):
        """ [edges x modes] 1 if the mode is used on the edge """
        return self._usages

    def getVarCosts(self):
        return sum(self._costs[e][m] * self._flows[e][m] for e in range(self._nrOfEdges) for m in range(self._nrOfModes))

    def getFixedCosts(self):
        return sum(self._fixedCosts[e][m] * self._usages[e][m] for e in range(self._nrOfEdges) for m in range(self._nrOfModes))
#*************** end MultiModalFlow ********************************************


#*************** extended network: node capacities and balance ************************************************
class _Extension:
    """ extended network of a flow problem

        A node v with a capacity is split into v (in) and an out node: all edges leaving v leave the out node, the edge
        v -> out carries the throughput (inflow + own supply = outflow + own demand). Own supplies stay at v,
        own demands move to the out node.
        balance 'auto': a dummy sink takes a surplus of supply (edges from the sources, costs 0), a dummy source
        delivers a surplus of demand (edges to the sinks, costs shortageCosts) - per commodity.
        The added edges follow the original ones - kinds[k] = (kind, node) of the added edge E + k.
    """

    def __init__(self, edges, n, supplies, demands, nodeMinCaps, nodeMaxCaps, balance, shortageCosts):
        self.orig = [ tuple(e) for e in setEdges(edges, n) ]
        self.n, self.E, self.K = n, len(self.orig), len(supplies[0])
        self.supplies, self.demands = supplies, demands
        self.nodeMin = _vector(nodeMinCaps, n, 'minimal capacities of the nodes', 0)
        self.nodeMax = _vector(nodeMaxCaps, n, 'maximal capacities of the nodes', None)
        _numbers(self.nodeMin, 'minimal capacity of a node')
        _numbers(self.nodeMax, 'maximal capacity of a node', allowUnlimited=True)
        if balance not in ('exact', 'auto'):
            raise LogLabException(f"LogisticsLab error: Wrong balance <{balance}> - 'exact' or 'auto' expected")
        K = self.K
        if shortageCosts is None:
            self.shortage = [ [0] * K for _ in range(n) ]
        elif shortageCosts and isinstance(shortageCosts[0], (list, tuple)):
            self.shortage = _matrix(shortageCosts, n, K, 'shortage costs', 0)
        else:
            self.shortage = [ [c] * K for c in _vector(shortageCosts, n, 'shortage costs', 0) ]
        for row in self.shortage:
            _numbers(row, 'shortage cost')

        self.split = [ v for v in range(n) if not _isUnlimited(self.nodeMax[v]) or self.nodeMin[v] > 0 ]
        self.outOf = list(range(n))
        for k, v in enumerate(self.split):
            self.outOf[v] = n + k
        N = n + len(self.split)
        self.edges = [ [self.outOf[i], j] for i, j in self.orig ]
        self.kinds = []
        for v in self.split:
            self.edges.append([v, self.outOf[v]])
            self.kinds.append(('node', v))
        S = [ [0] * K for _ in range(N) ]
        D = [ [0] * K for _ in range(N) ]
        for v in range(n):
            S[v] = list(supplies[v])
            D[self.outOf[v]] = list(demands[v])

        self.sink = self.source = None
        if balance == 'auto':
            surplus = [ sum(r[k] for r in supplies) - sum(r[k] for r in demands) for k in range(K) ]
            if any(s > 1e-9 for s in surplus):
                self.sink = N
                N += 1
                S.append([0] * K)
                D.append([ max(0, s) for s in surplus ])
                for v in range(n):
                    if any(supplies[v][k] > 0 and surplus[k] > 1e-9 for k in range(K)):
                        self.edges.append([v, self.sink])
                        self.kinds.append(('surplus', v))
            if any(s < -1e-9 for s in surplus):
                self.source = N
                N += 1
                S.append([ max(0, -s) for s in surplus ])
                D.append([0] * K)
                for v in range(n):
                    if any(demands[v][k] > 0 and surplus[k] < -1e-9 for k in range(K)):
                        self.edges.append([self.source, self.outOf[v]])
                        self.kinds.append(('shortage', v))
        self.N, self.S, self.D = N, S, D

    def addedRow(self, kind, v, node, surplus, shortage):
        """ value of an added edge - node, surplus and shortage are functions of the node """
        return {'node': node, 'surplus': surplus, 'shortage': shortage}[kind](v)

    def results(self, flows):
        """ flows [extended edges x K] -> original flows, throughput, unused supply and unmet demand per node """
        K, n = self.K, self.n
        flows = [ f if isinstance(f, list) else [f] for f in flows ]
        unused = [ [0] * K for _ in range(n) ]
        unmet = [ [0] * K for _ in range(n) ]
        for k, (kind, v) in enumerate(self.kinds):
            if kind == 'surplus':
                unused[v] = flows[self.E + k]
            elif kind == 'shortage':
                unmet[v] = flows[self.E + k]
        through = [ [ self.supplies[v][k] - unused[v][k] for k in range(K) ] for v in range(n) ]
        for e, (i, j) in enumerate(self.orig):
            for k in range(K):
                through[j][k] += flows[e][k]
        return flows[:self.E], through, unused, unmet


class _Extended:
    """ common part of the public flow classes - the model of the extended network is self._model """

    _isSingle = True

    def solve(self):
        self._model.solve()
        if self._model.isSolution():
            self._flows, self._through, self._unused, self._unmet = self._x.results(self._model.getFlows())

    def isSolution(self):
        return self._model.isSolution()

    def getObjValue(self):
        return self._model.getObjValue()

    def getMessage(self):
        return self._model.getMessage()

    def __out(self, rows):
        if not self._model.isSolution():
            return []
        return [ r[0] for r in rows ] if self._isSingle else rows

    def getFlows(self):
        """ flow on every original edge """
        return self.__out(self._flows)

    def getNodeFlows(self):
        """ flow through every node: inflow + own supply (= outflow + own demand) """
        return self.__out(self._through)

    def getUnusedSupplies(self):
        """ balance 'auto': supply that remains at a node """
        return self.__out(self._unused)

    def getUnmetDemands(self):
        """ balance 'auto': demand of a node that is not delivered """
        return self.__out(self._unmet)

    def getShortageCosts(self):
        return sum(c * u for row, urow in zip(self._x.shortage, self._unmet) for c, u in zip(row, urow)) \
               if self._model.isSolution() else 0


#*************** MinCostFlow ************************************************
class MinCostFlow(_Extended):
    """ min cost flow problem (minCostFlow.cmpl), with fixed costs (minCostFlowFixed.cmpl)

        edges       [[i, j], ...], nodes 0..len(supplies)-1, no parallel edges
        costs       cost rate of every edge
        supplies    supply of every node, demands: demand of every node (default 0)
        minCaps     minimal flow of every edge (default 0), maxCaps: maximal flow (default unlimited)
        fixedCosts  optional fixed costs of every edge - paid if the edge carries flow (MIP, mipGap)
                    a minimal flow minCaps > 0 forces the use of the edge
        nodeMinCaps, nodeMaxCaps, balance, shortageCosts - see the description of the module
    """

    def __init__(self, edges, costs, supplies, demands=None, minCaps=None, maxCaps=None, maxSolvingTime=10,
                 fixedCosts=None, mipGap=0.001, nodeMinCaps=None, nodeMaxCaps=None, balance='auto', shortageCosts=None):
        supplies = setNumVector(supplies)
        n = len(supplies)
        demands = _vector(demands, n, 'demands', 0)
        _numbers(demands, 'demand')
        x = self._x = _Extension(edges, n, [ [s] for s in supplies ], [ [d] for d in demands ],
                                 nodeMinCaps, nodeMaxCaps, balance, shortageCosts)
        costs = _vector(costs, x.E, 'costs', None)
        minCaps = _vector(minCaps, x.E, 'minimal capacities', 0)
        maxCaps = _vector(maxCaps, x.E, 'maximal capacities', None)
        fixed = None if fixedCosts is None else _vector(fixedCosts, x.E, 'fixed costs', 0)
        for kind, v in x.kinds:
            costs.append(x.addedRow(kind, v, lambda v: 0, lambda v: 0, lambda v: x.shortage[v][0]))
            minCaps.append(x.nodeMin[v] if kind == 'node' else 0)
            maxCaps.append(x.nodeMax[v] if kind == 'node' else None)
            if fixed is not None:
                fixed.append(0)
        self._costs = costs
        self._model = _MinCostFlowModel(x.edges, costs, [ r[0] for r in x.S ], [ r[0] for r in x.D ], minCaps, maxCaps,
                                        maxSolvingTime, fixed, mipGap)

    def isFixedCosts(self):
        return self._model.isFixedCosts()

    def getUsages(self):
        """ 1 if the edge is used """
        return self._model.getUsages()[:self._x.E]

    def getVarCosts(self):
        return sum(c * f for c, f in zip(self._costs, self.getFlows()))

    def getFixedCosts(self):
        return self._model.getFixedCosts()
#*************** end MinCostFlow ********************************************


#*************** MaxFlow ************************************************
class MaxFlow(_Extended):
    """ maximal flow from source to sink (maxFlow.cmpl)

        edges       [[i, j], ...], nodes 0..nrOfNodes-1 (default: largest node index of the edges + 1), no parallel edges
        maxCaps     maximal flow of every edge, minCaps: minimal flow (default 0)
        nodeMinCaps, nodeMaxCaps   minimal and maximal flow through a node, also through source and sink
        objective value: the maximal flow from source to sink
    """

    def __init__(self, edges, source, sink, maxCaps, minCaps=None, nrOfNodes=None, maxSolvingTime=10,
                 nodeMinCaps=None, nodeMaxCaps=None):
        if nrOfNodes is None:
            nodes = [ n for e in setEdges(edges) for n in e ]
            nrOfNodes = max(nodes) + 1 if nodes else 0
        for name, node in (('source', source), ('sink', sink)):
            if not isinstance(node, int) or not 0 <= node < nrOfNodes:
                raise LogLabException(f'LogisticsLab error: Wrong {name} <{node}>')
        if source == sink:
            raise LogLabException('LogisticsLab error: Source and sink must be different')
        zeros = [ [0] for _ in range(nrOfNodes) ]
        x = self._x = _Extension(edges, nrOfNodes, zeros, zeros, nodeMinCaps, nodeMaxCaps, 'exact', None)
        maxCaps = _vector(maxCaps, x.E, 'maximal capacities', None)
        minCaps = _vector(minCaps, x.E, 'minimal capacities', 0)
        for kind, v in x.kinds:
            minCaps.append(x.nodeMin[v])
            maxCaps.append(x.nodeMax[v])
        # the flow leaves the source at its in node and reaches the sink at its out node - both pass their node edge
        self._model = _MaxFlowModel(x.edges, source, x.outOf[sink], maxCaps, minCaps, x.N, maxSolvingTime)
        self._source = source

    def solve(self):
        super().solve()
        if self._model.isSolution():
            # the flow from the source is no supply - throughput = inflow, at the source the outflow
            self._through[self._source] = [self._model.getObjValue()]
#*************** end MaxFlow ********************************************


#*************** MultiCommodityFlow ************************************************
class MultiCommodityFlow(_Extended):
    """ min cost flow problem of several commodities with joint capacities of the edges

        edges            [[i, j], ...], nodes 0..len(supplies)-1, no parallel edges
        costs            [edges x commodities] cost rates
        supplies         [nodes x commodities], demands: [nodes x commodities] (default 0)
        minCaps          joint minimal capacity of every edge (default 0), maxCaps: joint maximal capacity (default unlimited)
        capacityFactors  [edges x commodities] capacity used by one unit of a commodity (default 1)
        nodeMinCaps, nodeMaxCaps   joint capacities of the nodes
        nodeCapacityFactors        [nodes x commodities] capacity of a node used by one unit of a commodity (default 1)
        balance, shortageCosts     per commodity - shortageCosts [nodes] or [nodes x commodities]
        isInteger, mipGap          integer flows (MIP) - with several commodities or capacity factors <> 1 the LP
                                   solution is in general not integral, even for integral supplies and demands
        results [edges x commodities] or [nodes x commodities]
    """

    _isSingle = False

    def __init__(self, edges, costs, supplies, demands=None, minCaps=None, maxCaps=None, capacityFactors=None,
                 maxSolvingTime=60, nodeMinCaps=None, nodeMaxCaps=None, balance='auto', shortageCosts=None,
                 nodeCapacityFactors=None, isInteger=False, mipGap=0.001):
        if not isinstance(supplies, (list, tuple)) or not supplies or not isinstance(supplies[0], (list, tuple)):
            raise LogLabException('LogisticsLab error: Wrong supplies - matrix [nodes x commodities] expected')
        n, K = len(supplies), len(supplies[0])
        supplies = _matrix(supplies, n, K, 'supplies', 0)
        demands = _matrix(demands, n, K, 'demands', 0)
        for name, m in (('supply', supplies), ('demand', demands)):
            for row in m:
                _numbers(row, name)
        x = self._x = _Extension(edges, n, supplies, demands, nodeMinCaps, nodeMaxCaps, balance, shortageCosts)
        costs = _matrix(costs, x.E, K, 'costs', None)
        factors = _matrix(capacityFactors, x.E, K, 'capacity factors', 1)
        nodeFactors = _matrix(nodeCapacityFactors, n, K, 'capacity factors of the nodes', 1)
        for row in nodeFactors:
            _numbers(row, 'capacity factor of a node')
        minCaps = _vector(minCaps, x.E, 'minimal capacities', 0)
        maxCaps = _vector(maxCaps, x.E, 'maximal capacities', None)
        for kind, v in x.kinds:
            costs.append(x.shortage[v] if kind == 'shortage' else [0] * K)
            # the edge v -> out of a split node carries the joint capacity of the node
            factors.append(list(nodeFactors[v]) if kind == 'node' else [1] * K)
            minCaps.append(x.nodeMin[v] if kind == 'node' else 0)
            maxCaps.append(x.nodeMax[v] if kind == 'node' else None)
        self._model = _MultiCommodityModel(x.edges, costs, x.S, x.D, minCaps, maxCaps, factors, maxSolvingTime,
                                           isInteger, mipGap)
#*************** end MultiCommodityFlow ********************************************


#*************** MultiModalFlow ************************************************
class MultiModalFlow(_Extended):
    """ min cost flow problem with several modes (e.g. truck, train, ship) on the edges and fixed costs

        edges       [[i, j], ...], nodes 0..len(supplies)-1, no parallel edges
        costs       [edges x modes] cost rates - None: the mode is not available on this edge
        supplies    supply of every node, demands: demand of every node (default 0)
        fixedCosts  [edges x modes] fixed costs if a mode is used on an edge (default 0)
        minCaps     [edges x modes] minimal flow if a mode is used (default 0), maxCaps: maximal flow (default unlimited)
        nodeMaxCaps, balance, shortageCosts - see the description of the module
        nodeMinCaps are not supported - minimal flows of the model apply only if a mode is used
    """

    def __init__(self, edges, costs, supplies, demands=None, fixedCosts=None, minCaps=None, maxCaps=None,
                 mipGap=0.001, maxSolvingTime=60, nodeMinCaps=None, nodeMaxCaps=None, balance='auto', shortageCosts=None):
        supplies = setNumVector(supplies)
        n = len(supplies)
        demands = _vector(demands, n, 'demands', 0)
        _numbers(demands, 'demand')
        if nodeMinCaps is not None and any(c for c in nodeMinCaps):
            raise LogLabException('LogisticsLab error: Minimal capacities of the nodes are not supported by MultiModalFlow')
        x = self._x = _Extension(edges, n, [ [s] for s in supplies ], [ [d] for d in demands ],
                                 None, nodeMaxCaps, balance, shortageCosts)
        if not isinstance(costs, (list, tuple)) or not costs or not isinstance(costs[0], (list, tuple)):
            raise LogLabException('LogisticsLab error: Wrong costs - matrix [edges x modes] expected')
        V = len(costs[0])
        costs = _matrix(costs, x.E, V, 'costs', None)
        fixed = _matrix(fixedCosts, x.E, V, 'fixed costs', 0)
        minCaps = _matrix(minCaps, x.E, V, 'minimal capacities', 0)
        maxCaps = _matrix(maxCaps, x.E, V, 'maximal capacities', None)
        for kind, v in x.kinds:
            # the added edges use the first mode - the others are not available there
            costs.append([x.shortage[v][0] if kind == 'shortage' else 0] + [None] * (V - 1))
            fixed.append([0] * V)
            minCaps.append([0] * V)
            maxCaps.append([x.nodeMax[v] if kind == 'node' else None] + [0] * (V - 1))
        self._costs, self._nrOfModes = costs, V
        self._model = _MultiModalModel(x.edges, costs, [ r[0] for r in x.S ], [ r[0] for r in x.D ], fixed, minCaps,
                                       maxCaps, mipGap, maxSolvingTime)

    def solve(self):
        self._model.solve()
        if self._model.isSolution():
            # flows per mode on the original edges, the node and balance flows summed over the modes
            modeFlows = self._model.getFlows()
            _, self._through, self._unused, self._unmet = self._x.results([ [sum(f)] for f in modeFlows ])
            self._flows = modeFlows[:self._x.E]

    def getFlows(self):
        """ [edges x modes] flows """
        return self._flows if self._model.isSolution() else []

    def getUsages(self):
        """ [edges x modes] 1 if the mode is used on the edge """
        return self._model.getUsages()[:self._x.E]

    def getVarCosts(self):
        return sum(self._costs[e][m] * f for e, row in enumerate(self.getFlows()) for m, f in enumerate(row)
                   if self._costs[e][m] is not None)

    def getFixedCosts(self):
        return self._model.getFixedCosts()
#*************** end MultiModalFlow ********************************************
