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


import osm_data as osm
import logisticslab as ll

import sys

logLabHome = '~/Nextcloud/Projekte/pyLogisticsLab/'
sys.path.append(logLabHome)

try:

    mapCentre = (52.32008512271094, 13.631385673205527)
    coords = [  (52.31772159070241, 13.630475995046083) , 
                (52.32066927545736, 13.6291325981096)  ,
                (52.31712458284014, 13.630607812960472), 
                (52.31898386034607, 13.633241742124378) ,
                (52.319347836765786, 13.632420986232365)
              ]

    osmData = osm.Data(coords=coords)

    m = ll.Nwf(osmData)

    osmRoute = m.shortesPathOsm(0,4)
    print('OSM route')
    print(osmRoute)

    xyRoute = ll.utils.osmRouteToXy(osmRoute, mapCentre)
    print('X,Y route for Carla')
    print(xyRoute)
    

   
 

except osm.OsmException as e:
    print(e.msg)
except ll.LogLabEception as e:
    print(e.msg)
except:
    print('Something went wrong: ' + str(sys.exc_info()[0]))
