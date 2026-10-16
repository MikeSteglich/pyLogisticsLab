
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal, Union, Annotated


#*************** base items ***********************************

class LogLabItem(BaseModel):
    """ base of all items - unknown fields are rejected """
    model_config = ConfigDict(extra='forbid')

class GeoInput(LogLabItem):
    """ options for calculating a distance or time matrix from coordinates via OSM """
    travelmode:  Optional[Literal["car", "foot", "wheelchair"] ] = "car"
    matrixMode: Optional[ Literal["distances", "times"] ]=  "distances"

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

class TppItem(GeoInput, SolverOptions):
    type: Literal["tpp"] = "tpp"
    supplies: list
    demands: list
    varCosts: Optional[list] = None
    sourceCoordinates: Optional[list] = None
    destinationCoordinates: Optional[list] = None
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

# all problems for the generic endpoint - the field type selects the item
ProblemItem = Annotated[Union[TspItem, TppItem], Field(discriminator='type')]


#*************** other items **********************************

class ResultItem(LogLabItem):
    id : str

class MatrixItem(LogLabItem):
    coordinates: list
    travelmode:  Optional[Literal["car", "foot", "wheelchair"] ] = "car"
    matrixMode: Optional[ Literal["distances", "durations", "both"] ] =  "distances"
    sources: Optional[list] = None
    destinations: Optional[list] = None
    rounded: Optional[bool] = False

class RouteItem(LogLabItem):
    coordinates: list
    travelmode:  Optional[Literal["car", "foot", "wheelchair"] ] = "car"
    details: Optional[ Literal["simplified", "full"] ] =  "simplified"

class SearchCoordinatesItem(LogLabItem):
    adresses: list

class SearchItem(LogLabItem):
    adress: str

class ReverseItem(LogLabItem):
    coordinate: list

