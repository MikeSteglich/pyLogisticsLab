""" handlers of the location and covering problems: wlp, pmedian, pcentre, contpmedian, contpcentre, scp, mcp

    All results use 0-based indices:
        activeSources   0/1 for every source
        assignments     index of the source that supplies a destination, -1 if none
        coveringSources (scp, mcp) indices of all open sources that cover a destination
"""

import pyLogisticsLab as ll
from pyCmpl import CmplException
from .exception import *
from .problemHandler import *
import sys


class LocationHandler(ProblemHandler):
    """ base class - matrix [sources x destinations], problem object of the library, solve and results """

    matrixField = 'varCosts'

    def __init__(self, problemData, logger, conf):
        super().__init__(problemData, logger, conf)
        self._type = problemData.type
        self._logger.debug(self._type, f'init {self._type}')

        self._matrix, self._isMatrixCalculated = self._bipartiteMatrix(problemData, self.matrixField)
        self._nrOfSources = len(self._matrix)
        self._nrOfDestinations = len(self._matrix[0])
        if not all(len(row) == self._nrOfDestinations for row in self._matrix):
            raise LogLabCoreException(f'{self.matrixField} must be a matrix [sources x destinations] - rows of different length')

        self._checkNrOfNodes(self._nrOfSources + self._nrOfDestinations)
        self._size = f'{self._nrOfSources}x{self._nrOfDestinations}'

        try:
            self._problem = self._createProblem(problemData)
        except ll.LogLabException as e:
            raise LogLabCoreException(e)

        self._logger.debug(self._type, 'init done')

    def _createProblem(self, problemData):
        raise NotImplementedError

    def _setResults(self, p):
        raise NotImplementedError

    def solve(self):
        try:
            self._logger.debug(self._type, 'solve')
            self._problem.solve()
        except ll.LogLabException as e:
            if 'No solution' in str(e):
                self._isSolution = False
                return
            raise LogLabCoreException(e)
        except CmplException as e:
            # CMPL reports infeasible models of HiGHS as error - the models are fixed and the data are checked before
            self._logger.info(self._type, f'no solution - {e}')
            self._isSolution = False
            return
        except Exception:
            raise LogLabCoreException(str(sys.exc_info()))

        self._isSolution = self._problem.isSolution()
        if self._isSolution:
            self._objVal = self._problem.getObjValue()
            self._setResults(self._problem)
            if self._isMatrixCalculated:
                self._results[self.matrixField] = self._matrix

    def _assignmentResults(self, p):
        self._results['activeSources'] = list(p.getActiveSources())
        self._results['assignments'] = [ self._zeroBased(i) for i in p.getDestSourceMapping() ]

    def _coveringResults(self, p):
        self._results['activeSources'] = list(p.getActiveSources())
        self._results['coveringSources'] = [ [ self._zeroBased(i) for i in sources ] for sources in p.getDestSourceMapping() ]
        self._results['assignments'] = [ self._zeroBased(i) for i in p.getDestSourceMappingSingleSource() ]


class WlpHandler(LocationHandler):
    def _createProblem(self, d):
        fixedCosts = self._checkLength(d.fixedCosts, self._nrOfSources, 'fixedCosts')
        demands = self._checkLength(d.demands, self._nrOfDestinations, 'demands')
        supplies = self._checkLength(d.supplies, self._nrOfSources, 'supplies', default=None if d.isCapacitated else 0)
        return ll.Wlp(self._matrix, fixedCosts, supplies, demands, d.isCapacitated,
                      mipGap=d.mipGap, maxSolvingTime=self._maxSolvingTime(d.maxSolvingTime))

    def _setResults(self, p):
        self._assignmentResults(p)


class PMedianHandler(LocationHandler):
    model = ll.PMedian

    def _createProblem(self, d):
        if d.p < 1 or d.p > self._nrOfSources:
            raise LogLabCoreException(f'wrong p {d.p} - between 1 and the number of sources {self._nrOfSources} expected')
        needsDemands = d.isDemandWeighted or d.isCapacitated
        demands = self._checkLength(d.demands, self._nrOfDestinations, 'demands', default=None if needsDemands else 1)
        supplies = self._checkLength(d.supplies, self._nrOfSources, 'supplies', default=None if d.isCapacitated else 0)
        return self.model(d.p, self._matrix, supplies, demands, d.isCapacitated, d.isDemandWeighted,
                          mipGap=d.mipGap, maxSolvingTime=self._maxSolvingTime(d.maxSolvingTime))

    def _setResults(self, p):
        self._assignmentResults(p)


class PCentreHandler(PMedianHandler):
    model = ll.PCentre


class ScpHandler(LocationHandler):
    matrixField = 'distances'

    def _createProblem(self, d):
        problem = ll.Scp(self._matrix, d.radius, mipGap=d.mipGap, maxSolvingTime=self._maxSolvingTime(d.maxSolvingTime))
        if d.fixedCosts is not None:
            problem.setFixedCosts(self._checkLength(d.fixedCosts, self._nrOfSources, 'fixedCosts'))
        return problem

    def _setResults(self, p):
        self._coveringResults(p)


class McpHandler(LocationHandler):
    matrixField = 'distances'

    def _createProblem(self, d):
        demands = self._checkLength(d.demands, self._nrOfDestinations, 'demands')
        problem = ll.Mcp(self._matrix, d.radius, d.maxSrcCost, demands,
                         mipGap=d.mipGap, maxSolvingTime=self._maxSolvingTime(d.maxSolvingTime))
        if d.fixedCosts is not None:
            problem.setFixedCosts(self._checkLength(d.fixedCosts, self._nrOfSources, 'fixedCosts'))
        return problem

    def _setResults(self, p):
        self._coveringResults(p)


class ContLocationHandler(ProblemHandler):
    """ continuous p-median and p-centre - results: locations [lat, lon] of the facilities, assignments (facility with
        the largest flow), customerDistances (km), flows [facilities x customers] if the demands can be split
    """

    model = ll.ContPMedian

    def __init__(self, problemData, logger, conf):
        super().__init__(problemData, logger, conf)
        self._type = problemData.type
        self._logger.debug(self._type, f'init {self._type}')

        d = problemData
        if not isinstance(d.coordinates, list) or not d.coordinates:
            raise LogLabCoreException('no coordinates are available')
        self._checkNrOfNodes(len(d.coordinates))
        self._size = f'p={d.p}, {len(d.coordinates)} customers'
        self._isSplit = d.capacities is not None and not d.isSingleSource

        try:
            self._problem = self.model(d.p, d.coordinates, d.demands, d.capacities, isSingleSource=d.isSingleSource,
                                       nrOfStarts=d.nrOfStarts, mipGap=d.mipGap,
                                       maxSolvingTime=self._maxSolvingTime(d.maxSolvingTime), costFactors=d.costFactors,
                                       isDemandWeighted=d.isDemandWeighted)
        except ll.LogLabException as e:
            raise LogLabCoreException(e)

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
            p = self._problem
            self._objVal = p.getObjValue()
            self._results['locations'] = p.getLocations()
            self._results['assignments'] = p.getAssignments()
            self._results['customerDistances'] = p.getCustomerDistances()
            if self._isSplit:
                self._results['flows'] = p.getFlows()
        else:
            self._logger.info(self._type, f'no solution - {self._problem.getMessage()}')


class ContPCentreHandler(ContLocationHandler):
    model = ll.ContPCentre
