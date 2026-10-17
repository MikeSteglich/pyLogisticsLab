import pyLogisticsLab as ll
from .exception import *
from .problemHandler import *
import sys


class TppHandler(ProblemHandler):
    def __init__(self, problemData, logger, conf):
        super().__init__(problemData, logger, conf)

        self._logger.debug('tpp','init tpp')

        self.__varCosts, self.__isCostMatrixCalculated = self._bipartiteMatrix(problemData, 'varCosts')

        self._checkNrOfNodes(len(problemData.supplies) + len(problemData.demands))
        self._size=f'{len(problemData.supplies)}x{len(problemData.demands)}'

        try:
            self.__problem=ll.Tpp(self.__varCosts, problemData.supplies, problemData.demands,
                                  fixedCosts=problemData.fixedCosts, capacities=problemData.capacities,
                                  minSupplies=problemData.minSupplies, maxSupplies=problemData.maxSupplies,
                                  minDemands=problemData.minDemands, maxDemands=problemData.maxDemands,
                                  objSense=problemData.objSense, isSingleSource=problemData.isSingleSource,
                                  minBlock=problemData.minBlock, maxBlock=problemData.maxBlock,
                                  sourceNames=problemData.sourceNames, destinationNames=problemData.destinationNames,
                                  mipGap=problemData.mipGap, maxSolvingTime=self._maxSolvingTime(problemData.maxSolvingTime),
                                  solverLogFile=self._conf.get('solverLogFile'))

        except ll.LogLabException as e:
            raise LogLabCoreException(e)

        self._logger.debug('tpp','init done')

    def solve(self):
        try:
            self._logger.debug('tpp','solve')
            self.__problem.solve()
        except ll.LogLabException as e:
            if 'No solution' in str(e):
                self._isSolution=False
                return
            raise LogLabCoreException(e)
        except:
            raise LogLabCoreException(str(sys.exc_info()))

        self._isSolution = self.__problem.isSolution()
        if self._isSolution:
            p = self.__problem
            self._objVal = p.getObjValue()
            self._results['totalCosts'] = p.getTotalCosts()
            self._results['totalVarCosts'] = p.getTotalVarCosts()
            self._results['totalFixedCosts'] = p.getTotalFixedCosts()
            self._results['totalFlow'] = p.getTotalFlow()
            self._results['flows'] = p.getFlows()
            self._results['sourceFlows'] = p.getSourceFlows()
            self._results['destinationFlows'] = p.getDestinationFlows()
            minCostRate, maxCostRate = p.getMinMaxCostRate()
            self._results['minCostRate'] = minCostRate
            self._results['maxCostRate'] = maxCostRate
            if self.__isCostMatrixCalculated:
                self._results['varCosts'] = self.__varCosts
