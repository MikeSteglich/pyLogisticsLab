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

from .exception import *

import osm_data as osm
import math

UNDEFINED = 100
OPTIMAL = 101

class Nwf:
    def __init__(self, osmData, edges=None, ):

        if str(type(osmData)) != "<class 'osm_data.osm_data.Data'>":
            raise LogLabException("Wrong nodes : osm_data.osm_data.Data expected instead of: " + str(type(osmData)))
        
        self.__osmData = osmData
        self.__coordinates = []

        self.__status = UNDEFINED

        self.__OsmRoutes = []
   
    @property
    def status(self):
        return self.__status

    def getOsmRoutes(self):
        return self.__OsmRoutes

    routes = property(getOsmRoutes)

    def shortesPathOsm(self, i, j, details='full' ):
        return self.__osmData.getRoute(nodes = [i,j], details=details)
