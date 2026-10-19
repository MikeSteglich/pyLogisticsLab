""" network flow problems

    MinCostFlow          min cost flow problem                                           - LP, minCostFlow.cmpl
                         with fixed costs of the edges                                   - MIP, minCostFlowFixed.cmpl
    MaxFlow              maximal flow from source to sink                                - LP, maxFlow.cmpl
    MultiCommodityFlow   min cost flow of several commodities with joint arc capacities  - LP, multiCommodity.cmpl
    MultiModalFlow       min cost flow with several modes (e.g. truck, train) and fixed costs - MIP, multimodal.cmpl

    All models are solved with CMPL and HiGHS.

    Nodes are 0-based indices, edges are lists [[i, j], ...] of node indices.
    Capacities None or 'M' mean unlimited. Results are lists in the order of the edges.
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
class MinCostFlow(_SingleFlow):
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
class MaxFlow(_SingleFlow):
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
class MultiCommodityFlow(_CmplFlow):
    """ min cost flow problem of several commodities with joint capacities of the edges

        edges            [[i, j], ...], nodes 0..len(supplies)-1, no parallel edges
        costs            [edges x commodities] cost rates
        supplies         [nodes x commodities], demands: [nodes x commodities] (default 0) - totals per commodity must be equal
        minCaps          joint minimal capacity of every edge (default 0), maxCaps: joint maximal capacity (default unlimited)
        capacityFactors  [edges x commodities] capacity used by one unit of a commodity (default 1)
    """

    #*********** constructor **********
    def __init__(self, edges, costs, supplies, demands=None, minCaps=None, maxCaps=None, capacityFactors=None,
                 maxSolvingTime=60):
        if not isinstance(supplies, (list, tuple)) or not supplies or not isinstance(supplies[0], (list, tuple)):
            raise LogLabException('LogisticsLab error: Wrong supplies - matrix [nodes x commodities] expected')
        n = len(supplies)
        self._nrOfCommodities = len(supplies[0])
        k = self._nrOfCommodities

        super().__init__(edges, n, 'multiCommodity.cmpl', 0.0, maxSolvingTime)

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
                                ('minKap', (arcs,), self._minCaps), ('maxKap', (arcs,), self._maxCaps)))

        if self._run((nodes, arcs, commodities), par):
            self._flows = [ [ self._activity(self._model.x, (i, j, c)) for c in range(self._nrOfCommodities) ]
                            for (i, j) in self._edges ]

    def getFlows(self):
        """ [edges x commodities] flows """
        return self._flows
#*************** end MultiCommodityFlow ********************************************


#*************** MultiModalFlow ************************************************
class MultiModalFlow(_CmplFlow):
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
