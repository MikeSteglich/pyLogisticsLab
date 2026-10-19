
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal, Union, Annotated


#*************** base items ***********************************

class LogLabItem(BaseModel):
    """ base of all items - unknown fields are rejected """
    model_config = ConfigDict(extra='forbid')

class MatrixOptions(LogLabItem):
    """ options for calculating a matrix from coordinates [lat, lon] - see matrixService.py """
    travelmode:  Optional[Literal["car", "foot", "wheelchair"] ] = "car"
    matrixSource: Optional[Literal["osm", "beeline"]] = "osm"     # beeline: great-circle distance x detourFactor
    detourFactor: Optional[float] = Field(1.3, gt=0)              # only beeline
    averageSpeed: Optional[float] = Field(None, gt=0)             # km/h for beeline times - default by travelmode
    timeFactor: Optional[float] = Field(1.0, gt=0)                # factor on the travel times, e.g. 1.2 for trucks
    noCache: Optional[bool] = False                               # True: new matrix from the OSM servers

class CostOptions(LogLabItem):
    """ cost matrix: km x costPerKm + h x timeFactor x costPerHour """
    costPerKm: Optional[float] = Field(None, ge=0)
    costPerHour: Optional[float] = Field(None, ge=0)

class GeoInput(MatrixOptions, CostOptions):
    """ matrix of a problem from coordinates: distances (m), times (s) or costs """
    matrixMode: Optional[ Literal["distances", "times", "costs"] ]=  "distances"

class SolverOptions(LogLabItem):
    """ options for MIP solvers """
    mipGap: Optional[float] = 0.001
    maxSolvingTime: Optional[int] = 300


#*************** problem items ********************************

class TspItem(GeoInput):
    type: Literal["tsp"] = "tsp"
    startNode : Optional[int] = 0
    endNode : Optional[int] = 0
    openRoute: Optional[bool] = False
    distances: Optional[list] =  None
    edges: Optional[list] =  None
    coordinates: Optional[list] =  None

class BipartiteGeoInput(GeoInput):
    """ cost or distance matrix [sources x destinations] from the coordinates of the sources and destinations """
    sourceCoordinates: Optional[list] = None
    destinationCoordinates: Optional[list] = None

class TppItem(BipartiteGeoInput, SolverOptions):
    type: Literal["tpp"] = "tpp"
    supplies: list
    demands: list
    varCosts: Optional[list] = None
    fixedCosts: Optional[list] = None
    capacities: Optional[list] = None
    minSupplies: Optional[list] = None
    maxSupplies: Optional[list] = None
    minDemands: Optional[list] = None
    maxDemands: Optional[list] = None
    objSense: Optional[ Literal["min", "max", "minimax"] ] = "min"
    isSingleSource: Optional[bool] = False
    minBlock: Optional[Union[int, float]] = None
    maxBlock: Optional[Union[int, float, str]] = None
    sourceNames: Optional[list] = None
    destinationNames: Optional[list] = None

class WlpItem(BipartiteGeoInput, SolverOptions):
    """ warehouse location problem """
    type: Literal["wlp"] = "wlp"
    varCosts: Optional[list] = None             # cost rates per unit of demand [sources x destinations]
    fixedCosts: list                            # fixed costs of the sources
    demands: list
    supplies: Optional[list] = None             # capacities of the sources - needed if isCapacitated
    isCapacitated: Optional[bool] = False

class PLocationFields(BipartiteGeoInput, SolverOptions):
    """ fields of the p-median and the p-centre problem """
    p: int                                      # number of sources to open
    varCosts: Optional[list] = None             # costs or distances [sources x destinations]
    demands: Optional[list] = None              # default 1 - needed if isDemandWeighted or isCapacitated
    supplies: Optional[list] = None             # capacities of the sources - needed if isCapacitated
    isCapacitated: Optional[bool] = False
    isDemandWeighted: Optional[bool] = False

class PMedianItem(PLocationFields):
    type: Literal["pmedian"] = "pmedian"

class PCentreItem(PLocationFields):
    type: Literal["pcentre"] = "pcentre"

class ContLocationFields(SolverOptions):
    """ fields of the continuous p-median and p-centre problem - facilities anywhere, great-circle distances in km """
    p: int                                      # number of facilities
    coordinates: list                           # [[lat, lon], ...] of the customers
    demands: Optional[list] = None              # default 1 - needed with capacities
    capacities: Optional[Union[int, float, list]] = None   # null: uncapacitated, a number or p numbers: capacitated
    isSingleSource: Optional[bool] = True       # False: the demand of a customer can be split
    nrOfStarts: Optional[int] = 20              # start solutions of the heuristic
    costFactors: Optional[list] = None          # contpmedian: factor of every customer on its costs (default 1)

class ContPMedianItem(ContLocationFields):
    type: Literal["contpmedian"] = "contpmedian"

class ContPCentreItem(ContLocationFields):
    type: Literal["contpcentre"] = "contpcentre"

class ScpItem(BipartiteGeoInput, SolverOptions):
    """ set covering problem - every destination within radius of an open source """
    type: Literal["scp"] = "scp"
    distances: Optional[list] = None            # [sources x destinations]
    radius: Union[int, float]
    fixedCosts: Optional[list] = None           # default 1 - minimal number of sources

class McpItem(BipartiteGeoInput, SolverOptions):
    """ maximal covering problem - maximal demand within radius of the open sources """
    type: Literal["mcp"] = "mcp"
    distances: Optional[list] = None            # [sources x destinations]
    radius: Union[int, float]
    demands: list
    maxSrcCost: Union[int, float]               # budget for the fixed costs of the open sources (fixedCosts 1: number of sources)
    fixedCosts: Optional[list] = None           # default 1

class CppItem(SolverOptions):
    """ chinese postman problem """
    type: Literal["cpp"] = "cpp"
    edges: list                                 # [[i, j], ...]
    edgeWeights: list
    edgeTypes: Optional[list] = None            # 0 directed, 1 undirected - default: all undirected
    startNode: int

class VrpItem(MatrixOptions):
    """ vehicle routing problem - integer values, numbers are rounded """
    type: Literal["vrp"] = "vrp"
    distances: Optional[list] = None            # square matrix of all nodes incl. the depot
    times: Optional[list] = None                # travel times - needed for timeWindows and maxTime
    coordinates: Optional[list] = None          # instead of distances (and times)
    demands: list
    capacities: list                            # one capacity per vehicle
    depot: Optional[int] = 0
    timeWindows: Optional[list] = None          # [[earliest, latest], ...] for every node
    serviceTimes: Optional[list] = None         # default 0
    maxTime: Optional[int] = None               # maximal duration of a route
    maxDist: Optional[int] = None               # maximal distance of a route
    maxWaitingTime: Optional[int] = None
    maxSolvingTime: Optional[int] = 10          # search time of OR-Tools in seconds

class FlowOptions(LogLabItem):
    """ network flow problems - nodes are 0-based indices, capacities null or "M" mean unlimited """
    edges: list                                 # [[i, j], ...]
    maxSolvingTime: Optional[int] = 60
    nodeMinCaps: Optional[list] = None          # minimal flow through every node (incl. its own supply and demand)
    nodeMaxCaps: Optional[list] = None          # maximal flow through every node - null or "M": unlimited

class BalanceOptions(LogLabItem):
    """ unequal totals of supply and demand """
    balance: Optional[Literal["exact", "auto"]] = "auto"    # auto: surplus supply remains, surplus demand is unmet,
                                                             # exact: the totals must be equal
    shortageCosts: Optional[list] = None        # costs per unit of unmet demand of every node - default 0

class MinCostFlowItem(FlowOptions, BalanceOptions):
    type: Literal["mincostflow"] = "mincostflow"
    costs: list                                 # cost rate of every edge
    supplies: list                              # supply of every node
    demands: Optional[list] = None              # demand of every node - default 0, totals equal or balance auto
    minCaps: Optional[list] = None              # minimal flow of every edge - default 0
    maxCaps: Optional[list] = None              # maximal flow of every edge - default unlimited
    fixedCosts: Optional[list] = None           # fixed costs of every edge if it is used - MIP
    mipGap: Optional[float] = 0.001             # only with fixedCosts

class MaxFlowItem(FlowOptions):
    type: Literal["maxflow"] = "maxflow"
    source: int
    sink: int
    maxCaps: list                               # maximal flow of every edge
    minCaps: Optional[list] = None
    nrOfNodes: Optional[int] = None             # default: largest node index of the edges + 1

class MultiCommodityItem(FlowOptions, BalanceOptions):
    type: Literal["multicommodity"] = "multicommodity"
    costs: list                                 # [edges x commodities]
    supplies: list                              # [nodes x commodities]
    demands: Optional[list] = None              # [nodes x commodities] - default 0
    minCaps: Optional[list] = None              # joint minimal capacity of every edge
    maxCaps: Optional[list] = None              # joint maximal capacity of every edge
    capacityFactors: Optional[list] = None      # [edges x commodities] capacity used by one unit - default 1

class MultiModalItem(FlowOptions, BalanceOptions):
    type: Literal["multimodal"] = "multimodal"
    costs: list                                 # [edges x modes] - null: mode not available on the edge
    supplies: list                              # supply of every node
    demands: Optional[list] = None
    fixedCosts: Optional[list] = None           # [edges x modes] - default 0
    minCaps: Optional[list] = None              # [edges x modes] minimal flow if the mode is used
    maxCaps: Optional[list] = None              # [edges x modes]
    mipGap: Optional[float] = 0.001

# all problems for the generic endpoint - the field type selects the item
ProblemItem = Annotated[Union[TspItem, TppItem, WlpItem, PMedianItem, PCentreItem, ContPMedianItem, ContPCentreItem,
                              ScpItem, McpItem, CppItem, VrpItem,
                              MinCostFlowItem, MaxFlowItem, MultiCommodityItem, MultiModalItem],
                        Field(discriminator='type')]


#*************** other items **********************************

class ResultItem(LogLabItem):
    id : str

class MatrixItem(MatrixOptions, CostOptions):
    """ both: distances and durations, all: distances, durations and costs """
    coordinates: list
    matrixMode: Optional[ Literal["distances", "durations", "costs", "both", "all"] ] =  "distances"
    sources: Optional[list] = None
    destinations: Optional[list] = None
    rounded: Optional[bool] = False

class RouteItem(LogLabItem):
    coordinates: list
    travelmode:  Optional[Literal["car", "foot", "wheelchair"] ] = "car"
    details: Optional[ Literal["simplified", "full"] ] =  "simplified"

class SearchCoordinatesItem(LogLabItem):
    """ coordinates of addresses - coordinates: first hit or null, hits: up to limit hits per address """
    adresses: list
    limit: Optional[int] = Field(1, ge=1, le=10)  # hits per address
    countrycodes: Optional[list[str]] = None      # e.g. ["DE"] - only hits in these countries
    near: Optional[list] = None                   # [lat, lon] - hits near this location first

class SearchItem(LogLabItem):
    adress: str

class ReverseItem(LogLabItem):
    coordinate: list


# problem type -> item, geo service -> item
PROBLEM_ITEMS = {'tsp': TspItem, 'tpp': TppItem, 'wlp': WlpItem, 'pmedian': PMedianItem, 'pcentre': PCentreItem,
                 'contpmedian': ContPMedianItem, 'contpcentre': ContPCentreItem,
                 'scp': ScpItem, 'mcp': McpItem, 'cpp': CppItem, 'vrp': VrpItem,
                 'mincostflow': MinCostFlowItem, 'maxflow': MaxFlowItem, 'multicommodity': MultiCommodityItem,
                 'multimodal': MultiModalItem}
GEO_ITEMS = {'matrix': MatrixItem, 'routing': RouteItem, 'coordinates': SearchCoordinatesItem,
             'search': SearchItem, 'reverse': ReverseItem}
