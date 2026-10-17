from .tools import *
from .exception import *

from pyCmpl import *
import os
import shutil
import tempfile
import pathlib
import random
import time
import logging

logger = logging.getLogger(__name__)


class TppException(LogLabException):
    pass

#Big M used for the TPP model
bigM = 1000000000


def _toNumM(val):
    """ converts 'M' or None to bigM, all other values are returned unchanged """
    if val is None or (isinstance(val, str) and val.strip().upper() == 'M'):
        return bigM
    return val

def _toNumMVector(vector):
    if not isinstance(vector, (list, tuple)):
        raise TppException('LogisticsLab error: Wrong vector ')
    return [ _toNumM(v) for v in vector ]

def _toNumMMatrix(matrix):
    if not isinstance(matrix, (list, tuple)) or not all( isinstance(row, (list, tuple)) for row in matrix ):
        raise TppException('LogisticsLab error: Wrong matrix. It is not an array.')
    return [ [ _toNumM(v) for v in row ] for row in matrix ]


#*************** Source *************************************
class Source(object):

    #*********** constructor **********
    def __init__(self, idx, name, supply, minSupply=0, maxSupply=bigM):
        self.__idx = idx
        self.__name = name
        self.__supply = setNum(supply)
        self.__minSupply = setNum(minSupply)
        self.__maxSupply = setNum(maxSupply)
        self.__flow = 0
    #*********** end constructor ******

    @property
    def idx(self):
        return self.__idx

    @property
    def name(self):
        return self.__name

    @property
    def supply(self):
        return self.__supply

    @property
    def minSupply(self):
        return self.__minSupply

    @property
    def maxSupply(self):
        return self.__maxSupply

    @property
    def flow(self):
        return self.__flow

    def resetFlow(self):
        self.__flow = 0

    def incFlow(self, flow):
        self.__flow += setNum(flow)

#*************** end Source **********************************


#*************** Destination *************************************
class Destination(object):

    #*********** constructor **********
    def __init__(self, idx, name, demand, minDemand=0, maxDemand=bigM):
        self.__idx = idx
        self.__name = name
        self.__demand = setNum(demand)
        self.__minDemand = setNum(minDemand)
        self.__maxDemand = setNum(maxDemand)
        self.__flow = 0
    #*********** end constructor ******

    @property
    def idx(self):
        return self.__idx

    @property
    def name(self):
        return self.__name

    @property
    def demand(self):
        return self.__demand

    @property
    def minDemand(self):
        return self.__minDemand

    @property
    def maxDemand(self):
        return self.__maxDemand

    @property
    def flow(self):
        return self.__flow

    def resetFlow(self):
        self.__flow = 0

    def incFlow(self, flow):
        self.__flow += setNum(flow)

#*************** end Destination **********************************


#*************** Tpp  ************************************************
class Tpp(object):
    """ Transportation problem

        varCosts            matrix [sources x destinations] of cost rates; 'M' or None = no connection
        supplies            vector of supplies per source
        demands             vector of demands per destination
        fixedCosts          optional matrix [sources x destinations] of fixed costs   -> VarAndFixedCosts
        capacities          optional matrix [sources x destinations] of capacities    -> SubjectTo Capacities
        minSupplies         optional vector of min supplies                           -> SubjectTo SupplyRanges
        maxSupplies         optional vector of max supplies ('M' allowed)             -> SubjectTo SupplyRanges
        minDemands          optional vector of min demands                            -> SubjectTo DemandRanges
        maxDemands          optional vector of max demands ('M' allowed)              -> SubjectTo DemandRanges
        objSense            'min', 'max' or 'minimax' (bottleneck)
        isSingleSource      every destination is supplied by exactly one source       -> SubjectTo SingleSource
        minBlock, maxBlock  optional bounds for the cost rates of used edges ('M' allowed) -> Blocking
        sourceNames, destinationNames   optional names
        solverLogFile       file for the HiGHS log (default: HiGHS.log in the temp directory)
    """

    #*********** constructor **********
    def __init__(self, varCosts, supplies, demands, fixedCosts=None, capacities=None,
                 minSupplies=None, maxSupplies=None, minDemands=None, maxDemands=None,
                 objSense='min', isSingleSource=False, minBlock=None, maxBlock=None,
                 sourceNames=None, destinationNames=None, mipGap=0.001, maxSolvingTime=300, solverLogFile=None):

        self.__model = None

        self.__maxSolvingTime = setMaxSolvingTime(maxSolvingTime)
        self.__mipGap = setMipGap(mipGap)

        self.__costs = setNumMatrix(_toNumMMatrix(varCosts))
        supplies = setNumVector(supplies)
        demands = setNumVector(demands)

        self.__nrOfSources = len(supplies)
        self.__nrOfDestinations = len(demands)

        self.__checkMatrix(self.__costs, 'cost rates')

        # objective sense: 0 - min, 1 - max, 2 - minimax (bottleneck)
        sense = str(objSense).strip().upper()
        if sense == 'MIN':
            self.__objSense = 0
        elif sense == 'MAX':
            self.__objSense = 1
        elif sense == 'MINIMAX':
            self.__objSense = 2
        elif sense == 'MAXIMIN':
            raise TppException('Bottleneck max is not implemented')
        else:
            raise TppException(f'Wrong objective sense <{objSense}>')

        self.__isFixedCosts = fixedCosts is not None
        if self.__isFixedCosts:
            self.__fixCosts = setNumMatrix(_toNumMMatrix(fixedCosts))
            self.__checkMatrix(self.__fixCosts, 'fixed costs')
        else:
            self.__fixCosts = [ [ 0 for j in range(self.__nrOfDestinations) ] for i in range(self.__nrOfSources) ]

        if self.__objSense > 1 and self.__isFixedCosts:
            raise TppException('Bottleneck and fixed cost cannot be combined')

        self.__isCapCon = capacities is not None
        if self.__isCapCon:
            self.__caps = setNumMatrix(_toNumMMatrix(capacities))
            self.__checkMatrix(self.__caps, 'capacities')
        else:
            self.__caps = [ [ bigM for j in range(self.__nrOfDestinations) ] for i in range(self.__nrOfSources) ]

        self.__isSupplyCon = minSupplies is not None or maxSupplies is not None
        minSupplies = self.__rangeVector(minSupplies, [0] * self.__nrOfSources, 'min supplies')
        maxSupplies = self.__rangeVector(maxSupplies, supplies, 'max supplies')

        self.__isDemandCon = minDemands is not None or maxDemands is not None
        minDemands = self.__rangeVector(minDemands, [0] * self.__nrOfDestinations, 'min demands')
        maxDemands = self.__rangeVector(maxDemands, demands, 'max demands')

        self.__isSingleSourceCon = bool(isSingleSource)

        self.__isBlockCon = minBlock is not None or maxBlock is not None
        self.__minBlock = setNum(minBlock) if minBlock is not None else 0
        self.__maxBlock = setNum(_toNumM(maxBlock))

        sourceNames = self.__names(sourceNames, self.__nrOfSources, 'S', 'source names')
        destinationNames = self.__names(destinationNames, self.__nrOfDestinations, 'D', 'destination names')

        self.__sources = [ Source(i+1, sourceNames[i], supplies[i], minSupplies[i], maxSupplies[i]) for i in range(self.__nrOfSources) ]
        self.__destinations = [ Destination(j+1, destinationNames[j], demands[j], minDemands[j], maxDemands[j]) for j in range(self.__nrOfDestinations) ]

        self.__totalSupply = sum(supplies)
        self.__totalDemand = sum(demands)

        # cost statistics per source (connections with 'M' are ignored)
        self.__costTolAdder = 0
        self.__maxCostSrc = []
        self.__minCostSrc = []
        self.__avgCostSrc = []
        self.__costTolSrc = []

        for c in self.__costs:
            vals = [ v for v in c if v < bigM ]
            self.__minCostSrc.append(min(vals) if vals else bigM)
            self.__maxCostSrc.append(max(vals) if vals else 0)
            self.__avgCostSrc.append(sum(vals)/self.__nrOfDestinations)

        self.__edges = []
        self.__fixedEdges = []

        self.__nrOfNodes = self.__nrOfSources + self.__nrOfDestinations

        if self.__mipGap == 0:
            if self.__nrOfNodes < 50:
                self.__mipGap = 0
            elif self.__nrOfNodes < 100:
                self.__mipGap = 0.01
            else:
                self.__mipGap = 0.02

        self.__NodeHeuristics = 100
        self.__debug = False

        self.__resetSolution()

        self.__modelName = str(pathlib.Path(__file__).parent.absolute())+os.sep+'Tpp.cmpl'
        self.__tmpPath = tempfile.gettempdir()+os.sep
        self.__solverLogFile = solverLogFile if solverLogFile else self.__tmpPath+'HiGHS.log'

    #*********** end constructor ******

    #*********** checks ************
    def __checkMatrix(self, matrix, name):
        if len(matrix) != self.__nrOfSources or not all( len(row) == self.__nrOfDestinations for row in matrix ):
            raise TppException(f'LogisticsLab error: Wrong dimension of {name}. Expected {self.__nrOfSources} x {self.__nrOfDestinations}')

    def __rangeVector(self, vector, default, name):
        if vector is None:
            return list(default)
        vector = setNumVector(_toNumMVector(vector))
        if len(vector) != len(default):
            raise TppException(f'LogisticsLab error: Wrong length of {name}. Expected {len(default)}')
        return vector

    def __names(self, names, length, prefix, name):
        if names is None:
            return [ f'{prefix}{i+1}' for i in range(length) ]
        if not isinstance(names, (list, tuple)) or len(names) != length:
            raise TppException(f'LogisticsLab error: Wrong {name}. Expected {length} names')
        return [ str(n) for n in names ]
    #*********** end checks ************

    #*********** getter ************
    def getObjValue(self):
        return self.__objValue

    def getTotalCosts(self):
        return self.__totalCosts

    def getTotalVarCosts(self):
        return self.__totalVarCosts

    def getTotalFixedCosts(self):
        return self.__totalFixedCosts

    def getFlows(self):
        """ matrix [sources x destinations] of the optimal flows """
        return self.__flows

    def getTotalFlow(self):
        return self.__totalFlow

    def getSourceFlows(self):
        return [ s.flow for s in self.__sources ]

    def getDestinationFlows(self):
        return [ d.flow for d in self.__destinations ]

    def getMinMaxCostRate(self):
        return (self.__minCostRate, self.__maxCostRate)

    def getSources(self):
        return self.__sources

    def getDestinations(self):
        return self.__destinations

    def getTotalSupply(self):
        return self.__totalSupply

    def getTotalDemand(self):
        return self.__totalDemand

    def getSolutionStatus(self):
        return self.__solutionStatusMsg

    def isSolution(self):
        return self.solutionStatus
    #*********** end getter ************

    def __resetSolution(self):
        self.solutionStatus = False
        self.__solutionStatusMsg = ''
        self.__objValue = 0
        self.__totalCosts = 0
        self.__totalVarCosts = 0
        self.__totalFixedCosts = 0
        self.__totalFlow = 0
        self.__minCostRate = bigM
        self.__maxCostRate = 0
        self.__flows = [ [ 0 for j in range(self.__nrOfDestinations) ] for i in range(self.__nrOfSources) ]
        for s in self.__sources:
            s.resetFlow()
        for d in self.__destinations:
            d.resetFlow()

    def __setCostTol(self):
        factor = 1.25
        self.__costTolSrc = []
        for i in range(self.__nrOfSources):
            if self.__maxCostSrc[i] == 0:
                self.__costTolSrc.append(factor)
            elif self.__avgCostSrc[i] > self.__minCostSrc[i]:
                self.__costTolSrc.append( self.__avgCostSrc[i]/self.__maxCostSrc[i] * factor)
            else:
                self.__costTolSrc.append( self.__minCostSrc[i]/self.__maxCostSrc[i] * factor )


    #*********** __setEdges     ************
    def __setEdges(self ):

        self.__edges = []
        self.__vCosts = []
        self.__fCosts = []
        self.__capacities = []

        for ii,s in enumerate(self.__sources):
            self.__costTolSrc[ii] += self.__costTolAdder
            maxCost = self.__maxCostSrc[ii] * self.__costTolSrc[ii]

            for d in self.__destinations:
                i = s.idx-1
                j = d.idx-1

                if self.__costs[i][j] <= maxCost and self.__costs[i][j] >= self.__minBlock and self.__costs[i][j]<= self.__maxBlock and self.__costs[i][j]<bigM:
                    self.__addEdge(i, j)

        self.__checkEdges()

    #*********** __setEdges     ************

    def __addEdge(self, i, j):
        self.__edges.append((i+1,j+1))
        self.__vCosts.append(self.__costs[i][j])

        if self.__isFixedCosts:
            self.__fCosts.append(self.__fixCosts[i][j])
        else:
            self.__fCosts.append(0)

        if self.__isCapCon:
            self.__capacities.append(self.__caps[i][j])
        else:
            self.__capacities.append(bigM)

    def __checkEdges(self):

        for d in self.__destinations:
            destAssigned = False
            for s in self.__sources:
                if (s.idx,d.idx) in self.__edges:
                    destAssigned = True
                    break

            if not destAssigned:
                for s in self.__sources:
                    self.__addEdge(s.idx-1, d.idx-1)


    #*********** __fixVariables  ************

    def __fixVariables(self):
        self.__fixedEdges = []

        for i,j in self.__edges:
            try:
                if self.__model.y[(i,j)].activity == 0:
                    if abs(self.__model.supplies[i].marginal) == 0:
                        if random.random()<self.__fixVarProb:
                            self.__fixedEdges.append((i,j))
            except Exception as err:
                raise TppException("Error while fixing vars <" +str( err)+">" )

    #*********** __fixVariables  ************

    def __checkCostTol(self):
        ok = False
        for tol in self.__costTolSrc:
            if tol < 1:
                ok = True
        return ok


    #*********** solve ************
    def solve(self):

        sTime=time.time()
        timeLimit = self.__maxSolvingTime

        self.__resetSolution()

        self.__fixedEdges= [(-1,-1)]
        fEdges = CmplSet("fixedEdges",2)
        fEdges.setValues(self.__fixedEdges )

        sources = CmplSet("sources")
        sources.setValues(1,self.__nrOfSources)

        destinations = CmplSet("destinations")
        destinations.setValues(1,self.__nrOfDestinations)

        totalDemand=0
        totalSupply=0

        minSupplyVals=[]
        maxSupplyVals=[]
        minDemandVals=[]
        maxDemandVals=[]

        for source in self.__sources:
            if self.__isSupplyCon:
                minSupplyVals.append(source.minSupply)
                maxSupplyVals.append(source.maxSupply)
                totalSupply+=source.maxSupply
            else:
                minSupplyVals.append(0)
                maxSupplyVals.append(source.supply)
                totalSupply+=source.supply

        minS = CmplParameter('minS', sources)
        minS.setValues(minSupplyVals)
        maxS = CmplParameter('maxS', sources)
        maxS.setValues(maxSupplyVals)

        for dest in self.__destinations:
            if self.__isDemandCon:
                minDemandVals.append(dest.minDemand)
                maxDemandVals.append(dest.maxDemand)
                totalDemand+=dest.maxDemand
            else:
                minDemandVals.append(0)
                maxDemandVals.append(dest.demand)
                totalDemand+=dest.demand

        minD = CmplParameter('minD', destinations)
        minD.setValues(minDemandVals)
        maxD = CmplParameter('maxD', destinations)
        maxD.setValues(maxDemandVals)

        objSense = CmplParameter('objSense')
        objSense.setValues(self.__objSense)

        valMode = CmplParameter('valueMode')
        if totalDemand<totalSupply:
            valMode.setValues(0)
        elif totalDemand>totalSupply:
            valMode.setValues(1)
        else:
            valMode.setValues(2)

        maxBlock = CmplParameter('maxBlock')
        minBlock = CmplParameter('minBlock')
        costBlockMode = CmplParameter('costBlockMode')
        if self.__isBlockCon:
            costBlockMode.setValues(1)
            minBlock.setValues(self.__minBlock)
            maxBlock.setValues(self.__maxBlock)
        else:
            costBlockMode.setValues(0)
            minBlock.setValues(0)
            maxBlock.setValues(bigM)

        singleSourceMode = CmplParameter('singleSourceMode')
        singleSourceMode.setValues(1 if self.__isSingleSourceCon else 0)

        supplyConMode = CmplParameter('supplyConMode')
        supplyConMode.setValues(1 if self.__isSupplyCon else 0)

        demandConMode = CmplParameter('demandConMode')
        demandConMode.setValues(1 if self.__isDemandCon else 0)

        fixedCostMode = CmplParameter('fixedCostMode')
        fixedCostMode.setValues(1 if self.__isFixedCosts else 0)

        relaxedMode = CmplParameter('relaxedMode')
        relaxedMode.setValues(1)

        bM = CmplParameter("M")
        bM.setValues(bigM)

        edges = CmplSet("edges",2)
        costs = CmplParameter("c", edges )
        fc = CmplParameter("fc",edges )
        caps = CmplParameter("caps",edges )

        shutil.copyfile(self.__modelName, self.__tmpPath+"Tpp.cmpl")
        modelName=self.__tmpPath+"Tpp.cmpl"

        if (self.__isFixedCosts or self.__isSingleSourceCon or self.__objSense == 2 ) and self.__nrOfNodes > self.__NodeHeuristics:

            logger.info('    ... solving relaxtion ')

            self.__costTolAdder = 0
            self.__setCostTol()

            while True:
                self.__model = Cmpl(modelName)
                self.__model.debug(self.__debug)
                self.__model.setOutput(False)

                logger.info(f'        ... with cost tolerance adder of {self.__costTolAdder} ')

                self.__setEdges()

                edges.setValues(self.__edges)
                costs.setValues(self.__vCosts)
                fc.setValues(self.__fCosts)
                caps.setValues(self.__capacities)

                self.__model.setSets(fEdges, edges, sources,destinations)

                self.__model.setParameters( objSense,valMode,fixedCostMode,singleSourceMode,supplyConMode,demandConMode)
                self.__model.setParameters(costs, bM , minS,maxS,minD,maxD, caps,fc, relaxedMode)
                self.__model.setParameters(costBlockMode, minBlock, maxBlock)

                self.__model.setOption('-solver highs')
                self.__model.setOption(f'-opt highs log_file={self.__solverLogFile}')

                if not self.__solveModel():
                    logger.info('        ... No solution has been found')
                    if not self.__checkCostTol():
                        raise TppException(' No solution has been found with relaxation')
                else:
                    logger.info(f'        ... Solution has been found with obj value {self.__model.solution.value} ')
                    break

                self.__costTolAdder += 0.1

                if (time.time()-sTime) > timeLimit:
                    raise TppException(' No solution has been found  with relaxation')

            logger.info('    ... solving fixed model ')

            self.__fixVarProb = 0.6
            self.__fixVariables()

            fEdges.setValues(self.__fixedEdges )

            timeLimit -= round(time.time()-sTime)
            if timeLimit<0:
                raise TppException('No solution has been found with relaxation')

        else:
            logger.info('    ... solving model ')

            self.__costTolAdder = 1
            self.__setCostTol()

            #für exakte Loesung ein maxCost=M setzen
            self.__setEdges()

            edges.setValues(self.__edges)
            costs.setValues(self.__vCosts)
            fc.setValues(self.__fCosts)
            caps.setValues(self.__capacities)

        relaxedMode.setValues(0)

        self.__model = Cmpl(modelName)

        self.__model.setOption('-solver highs')
        self.__model.setOption(f'-opt highs log_file={self.__solverLogFile}')
        self.__model.setOption(f'-opt highs time_limit={timeLimit}')
        self.__model.setOption(f'-opt highs mip_rel_gap={self.__mipGap}')

        self.__model.setSets(fEdges, edges, sources,destinations)
        self.__model.setParameters( objSense,valMode,fixedCostMode,singleSourceMode,supplyConMode,demandConMode)
        self.__model.setParameters(costs, bM , minS,maxS,minD,maxD, caps,fc, relaxedMode)
        self.__model.setParameters(costBlockMode, minBlock, maxBlock)

        self.__model.debug(self.__debug)
        self.__model.setOutput(False)
        isSolved = self.__solveModel()

        try:
            os.remove( modelName)
        except:
            pass

        if not isSolved:
            raise TppException('No solution has been found')

        logger.info(f'    ... Solution has been found with obj value {self.__model.solution.value} ')
        self.__readSolution()

    #*********** end solve **************

    #*********** __solveModel ************
    def __solveModel(self):
        """ solves the current model, CMPL raises an exception (e.g. HiGHS) for infeasible models """
        try:
            self.__model.solve()
        except CmplException as e:
            self.__solutionStatusMsg = str(e)
            return False

        if self.__model.solverStatus != SOLVER_OK:
            self.__solutionStatusMsg = self.__model.solverMessage
            return False
        return True
    #*********** end __solveModel ************


    #*********** __readSolution ************
    def __readSolution(self):

        self.solutionStatus = True
        self.__solutionStatusMsg = self.__model.solution.status
        self.__objValue = self.__model.solution.value

        for i,j in self.__edges:
            try:
                if self.__isSingleSourceCon:
                    flow = self.__model.y[(i,j)].activity * self.__destinations[j-1].demand
                else:
                    flow = self.__model.x[(i,j)].activity
            except Exception as err:
                raise TppException("Can't read the solution <" +str( err)+">" )

            if flow > 1e-9:
                cost = self.__costs[i-1][j-1]
                if cost>self.__maxCostRate:
                    self.__maxCostRate=cost
                if cost<self.__minCostRate:
                    self.__minCostRate=cost

                self.__flows[i-1][j-1] = flow
                self.__totalFlow += flow

                self.__sources[i-1].incFlow(flow)
                self.__destinations[j-1].incFlow(flow)

                self.__totalVarCosts += flow*cost
                if self.__isFixedCosts:
                    self.__totalFixedCosts += self.__fixCosts[i-1][j-1]

        self.__totalCosts = self.__totalVarCosts + self.__totalFixedCosts

    #*********** end __readSolution ************

#************** end Tpp  **********************************************
