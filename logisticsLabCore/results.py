""" results of the problems - the field results of /v1/results and of the stdio method result

    {id, status, message, results}    results only with status solution, its fields depend on the problem type

    The models describe the answers for the JSON Schema (e.g. to generate the Dart models of the Flutter app) and are
    used by the tests to check the answers. All indices are 0-based, -1 means none.
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal, Union


Number = Union[int, float]
Vector = list[Number]
Matrix = list[list[Number]]


class MatrixInfo(BaseModel):
    """ origin of the matrices calculated from coordinates (matrixService.py) """
    model_config = ConfigDict(extra='forbid')
    source: Literal['osm', 'cache', 'beeline']
    status: Literal['exact', 'unexact', 'beeline']   # unexact: some values estimated with fillFactors
    travelmode: str
    matrices: list[Literal['distances', 'times', 'costs']]
    fillFactors: Optional[dict] = None          # detourFactor, timeFactor, nrOfFilledValues
    osmDate: Optional[str] = None               # data state of the OSM servers (osm_date of /ors/v2/status)
    detourFactor: Optional[float] = None        # beeline
    averageSpeed: Optional[float] = None        # beeline, km/h
    timeFactor: Optional[float] = None
    costPerKm: Optional[float] = None
    costPerHour: Optional[float] = None


class ResultFields(BaseModel):
    """ fields of all results - unknown fields are rejected, so that a test notices new fields """
    model_config = ConfigDict(extra='forbid')
    objVal: Number
    solvingTime: float                          # seconds in the solver process
    matrixInfo: Optional[MatrixInfo] = None     # only if a matrix has been calculated from coordinates


#*************** routing ************************************************

class TspResults(ResultFields):
    route: list[int]                            # node sequence

class CppResults(ResultFields):
    eulerTour: list[int]                        # node sequence
    edgeUsages: list[int]                       # number of usages of every given edge

class VrpResults(ResultFields):
    routes: list[list[int]]                     # node sequence of every vehicle, [depot, depot] if unused
    routeLoads: Matrix                          # load after every node of a route
    routeDistances: Matrix                      # distance after every node of a route
    routeTimes: Optional[Matrix] = None         # only with time windows
    distances: Optional[Matrix] = None          # only if calculated from coordinates
    times: Optional[Matrix] = None


#*************** transportation, location, covering ************************************************

class TppResults(ResultFields):
    totalCosts: Number
    totalVarCosts: Number
    totalFixedCosts: Number
    totalFlow: Number
    flows: Matrix                               # [sources x destinations]
    sourceFlows: Vector
    destinationFlows: Vector
    minCostRate: Number                         # of the used connections
    maxCostRate: Number
    varCosts: Optional[Matrix] = None           # only if calculated from coordinates

class LocationResults(ResultFields):
    """ wlp, pmedian, pcentre """
    activeSources: list[int]                    # 0/1 for every source
    assignments: list[int]                      # source of every destination
    varCosts: Optional[Matrix] = None           # only if calculated from coordinates

class CoveringResults(ResultFields):
    """ scp, mcp """
    activeSources: list[int]
    coveringSources: list[list[int]]            # all open sources within the radius of every destination
    assignments: list[int]                      # nearest of them, mcp: -1 for an uncovered destination
    distances: Optional[Matrix] = None          # only if calculated from coordinates

class ContLocationResults(ResultFields):
    """ contpmedian, contpcentre """
    locations: list[list[float]]                # [lat, lon] of every facility
    assignments: list[int]                      # facility with the largest flow to every customer
    customerDistances: list[float]              # km to the (farthest supplying) facility
    flows: Optional[Matrix] = None              # [facilities x customers], only with isSingleSource false


#*************** network flows ************************************************

class FlowResults(ResultFields):
    """ mincostflow, maxflow - objVal of maxflow is the maximal flow """
    flows: Vector                               # flow of every edge
    usages: Optional[list[int]] = None          # mincostflow with fixedCosts: 0/1 for every edge
    totalVarCosts: Optional[Number] = None      # mincostflow with fixedCosts
    totalFixedCosts: Optional[Number] = None

class MultiCommodityResults(ResultFields):
    flows: Matrix                               # [edges x commodities]

class MultiModalResults(ResultFields):
    flows: Matrix                               # [edges x modes]
    usages: list[list[int]]                     # 0/1 [edges x modes]
    totalVarCosts: Number
    totalFixedCosts: Number


#*************** answer ************************************************

class ProblemAnswer(BaseModel):
    """ answer of /v1/results and of the stdio methods solve, status, result and cancel """
    id: str
    status: Literal['waiting', 'running', 'solution', 'noSolution', 'error', 'cancelled']
    message: str
    results: Optional[dict] = None              # with status solution - see RESULT_ITEMS for the fields per type


# problem type -> results
RESULT_ITEMS = {'tsp': TspResults, 'tpp': TppResults, 'wlp': LocationResults, 'pmedian': LocationResults,
                'pcentre': LocationResults, 'contpmedian': ContLocationResults, 'contpcentre': ContLocationResults,
                'scp': CoveringResults, 'mcp': CoveringResults, 'cpp': CppResults, 'vrp': VrpResults,
                'mincostflow': FlowResults, 'maxflow': FlowResults, 'multicommodity': MultiCommodityResults,
                'multimodal': MultiModalResults}
