#***********************************************************************
 #  This code is part of pyLogisticsLab
 #
 #  Mike Steglich - Technical University of Applied Sciences
 #  Wildau, Germany
 #
 #  pyLogisticsLab is a project of the Technical University of
 #  Applied Sciences Wildau
 #
 #  pyLogisticsLab is free software; you can redistribute it and/or modify it
 #  under the terms of the GNU Lesser General Public License as published by
 #  the Free Software Foundation; either version 3 of the License, or
 #  (at your option) any later version.
 #
 #  pyLogisticsLab is distributed in the hope that it will be useful, but WITHOUT
 #  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 #  or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public
 #  License for more details.
 #
 #  You should have received a copy of the GNU Lesser General Public License
 #  along with this program; if not, see <http://www.gnu.org/licenses/>.
 #
 #**********************************************************************

import math
from .exception import *

def osmRouteToXy(osmRoute, mapCentre):
    if type (mapCentre) is not tuple:
        raise LogLabException("Wrong type of the map centre: " + str(type(mapCentre)) + " - tuple expected")

    xyRoute = []
    for c in osmRoute:
        y = greatCircleDistance( c[0], mapCentre[1], mapCentre[0], mapCentre[1] )
        if c[0] < mapCentre[0]:
            y*=-1
        x = greatCircleDistance( mapCentre[0], c[1] , mapCentre[0], mapCentre[1] )
        if c[1] < mapCentre[1]:
            x*=-1
        xyRoute.append( (x,y) )

    return xyRoute

def greatCircleDistance(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1))* math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    dist = 6378.137 * c * 1000
    return dist 
    