""" handlers of the network flow problems: mincostflow, maxflow, multicommodity, multimodal, multistagewlp

    flows are lists in the order of the edges ([edges x commodities] or [edges x modes] for the multi problems)
"""

import pyLogisticsLab as ll
from .exception import *
from .problemHandler import *
import sys


class FlowHandler(ProblemHandler):
    """ base class - checks the size, creates the problem of the library, solves it and reads the flows """

    def __init__(self, problemData, logger, conf):
        super().__init__(problemData, logger, conf)
        self._type = problemData.type
        self._logger.debug(self._type, f'init {self._type}')

        d = self._data = problemData
        if not isinstance(d.edges, list) or not d.edges:
            raise LogLabCoreException('no edges are available')
        nrOfNodes = self._nrOfNodes(d)
        self._checkNrOfNodes(nrOfNodes)
        self._size = f'{nrOfNodes} nodes, {len(d.edges)} edges'

        try:
            self._problem = self._createProblem(d)
        except ll.LogLabException as e:
            raise LogLabCoreException(e)

    def _nrOfNodes(self, d):
        return len(d.supplies)

    def _createProblem(self, d):
        raise NotImplementedError

    def _setResults(self, p):
        self._results['flows'] = p.getFlows()

    def _nodeResults(self, p, d):
        """ throughput with node capacities, unused supply and unmet demand with balance auto """
        if d.nodeMinCaps is not None or d.nodeMaxCaps is not None:
            self._results['nodeFlows'] = p.getNodeFlows()
        # the balance only if a surplus has been balanced
        total = lambda v: sum(sum(x) if isinstance(x, list) else x for x in v)
        if getattr(d, 'balance', 'exact') == 'auto' and (total(p.getUnusedSupplies()) > 1e-9 or total(p.getUnmetDemands()) > 1e-9):
            self._results['unusedSupplies'] = p.getUnusedSupplies()
            self._results['unmetDemands'] = p.getUnmetDemands()
            self._results['totalShortageCosts'] = p.getShortageCosts()

    def solve(self):
        try:
            self._logger.debug(self._type, 'solve')
            self._problem.solve()
        except ll.LogLabException as e:
            raise LogLabCoreException(e)
        except Exception:
            raise LogLabCoreException(str(sys.exc_info()))

        self._isSolution = self._problem.isSolution()
        if self._isSolution:
            self._objVal = self._problem.getObjValue()
            self._setResults(self._problem)
            self._nodeResults(self._problem, self._data)
        else:
            self._logger.info(self._type, f'no solution - {self._problem.getMessage()}')


class MinCostFlowHandler(FlowHandler):
    def _createProblem(self, d):
        return ll.MinCostFlow(d.edges, d.costs, d.supplies, d.demands, d.minCaps, d.maxCaps,
                              maxSolvingTime=self._maxSolvingTime(d.maxSolvingTime),
                              fixedCosts=d.fixedCosts, mipGap=d.mipGap, nodeMinCaps=d.nodeMinCaps,
                              nodeMaxCaps=d.nodeMaxCaps, balance=d.balance, shortageCosts=d.shortageCosts)

    def _setResults(self, p):
        self._results['flows'] = p.getFlows()
        if p.isFixedCosts():
            self._results['usages'] = p.getUsages()
            self._results['totalVarCosts'] = p.getVarCosts()
            self._results['totalFixedCosts'] = p.getFixedCosts()


class MaxFlowHandler(FlowHandler):
    def _nrOfNodes(self, d):
        if d.nrOfNodes is not None:
            return d.nrOfNodes
        nodes = [ n for e in d.edges if isinstance(e, list) for n in e if isinstance(n, int) ]
        return max(nodes) + 1 if nodes else 0

    def _createProblem(self, d):
        return ll.MaxFlow(d.edges, d.source, d.sink, d.maxCaps, d.minCaps, nrOfNodes=d.nrOfNodes,
                          maxSolvingTime=self._maxSolvingTime(d.maxSolvingTime),
                          nodeMinCaps=d.nodeMinCaps, nodeMaxCaps=d.nodeMaxCaps)


class MultiCommodityHandler(FlowHandler):
    def _createProblem(self, d):
        return ll.MultiCommodityFlow(d.edges, d.costs, d.supplies, d.demands, d.minCaps, d.maxCaps, d.capacityFactors,
                                     maxSolvingTime=self._maxSolvingTime(d.maxSolvingTime), nodeMinCaps=d.nodeMinCaps,
                                     nodeMaxCaps=d.nodeMaxCaps, balance=d.balance, shortageCosts=d.shortageCosts,
                                     nodeCapacityFactors=d.nodeCapacityFactors, isInteger=d.isInteger,
                                     mipGap=d.mipGap)


class MultiStageWlpHandler(FlowHandler):
    def _createProblem(self, d):
        return ll.MultiStageWlp(d.edges, d.costs, d.supplies, d.demands, nodeFixedCosts=d.nodeFixedCosts,
                                nodeMaxCaps=d.nodeMaxCaps, nodeMinCaps=d.nodeMinCaps, minCaps=d.minCaps,
                                maxCaps=d.maxCaps, fixedCosts=d.fixedCosts, isSingleSource=d.isSingleSource,
                                maxSolvingTime=self._maxSolvingTime(d.maxSolvingTime), mipGap=d.mipGap,
                                balance=d.balance, shortageCosts=d.shortageCosts)

    def _setResults(self, p):
        self._results['flows'] = p.getFlows()
        self._results['usages'] = p.getUsages()
        self._results['openNodes'] = p.getOpenNodes()
        self._results['nodeFlows'] = p.getNodeFlows()
        self._results['totalVarCosts'] = p.getVarCosts()
        self._results['totalFixedCosts'] = p.getFixedCosts()
        self._results['totalOpeningCosts'] = p.getOpeningCosts()


class MultiModalHandler(FlowHandler):
    def _createProblem(self, d):
        return ll.MultiModalFlow(d.edges, d.costs, d.supplies, d.demands, d.fixedCosts, d.minCaps, d.maxCaps,
                                 mipGap=d.mipGap, maxSolvingTime=self._maxSolvingTime(d.maxSolvingTime),
                                 nodeMinCaps=d.nodeMinCaps, nodeMaxCaps=d.nodeMaxCaps, balance=d.balance,
                                 shortageCosts=d.shortageCosts)

    def _setResults(self, p):
        self._results['flows'] = p.getFlows()
        self._results['usages'] = p.getUsages()
        self._results['totalVarCosts'] = p.getVarCosts()
        self._results['totalFixedCosts'] = p.getFixedCosts()
