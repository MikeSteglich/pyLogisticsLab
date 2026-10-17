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
from .config import *
from .logging import *
from .scheduler import *
from .tools import *

import sys
import math
from simplification.cutil import simplify_coords



class Routing:
    def __init__(self, coords, conf=None):

        if conf:
            checkConfig(conf)
            self.__config = conf
        else:
            self.__config = readConf()

        self.__log = Logging(self.__config.get('logFile'),self.__config['logging'])
        self.__osmScheduler = Scheduler(self.__config, self.__log) 

        self.__maxNodesInRoute = self.__config['servers']['maxNodesInRoute']

        checkCoordinates(coords)
        self.__coordinates=transformCoords(coords)
        self.__nrOfNodes=len(coords)
        
        self.__isOrs=False
        self.__travelmode='car'
        self.__orsWayPoints=[]
        self.__route=[]

    def getRoute(self):
        if self.__isOrs and not (self.__travelmode=='foot' or self.__travelmode=='wheelchair'):
            if len(self.__route)<1000:
                return simplify_coords(self.__route, .0001)
            else:
                return simplify_coords(self.__route, .0006)
        else:
            return self.__route
    route = property(getRoute)


    def loadRoute(self, travelmode='car', details='simplified' ):
        
        msg='OK'

        nrOfSteps = math.ceil(self.__nrOfNodes/self.__maxNodesInRoute)
        self.__travelmode=travelmode
       
        if self.__travelmode not in ('car','bike','foot','wheelchair'):
            raise OsmException(f"Wrong travelmode {self.__travelmode} - 'car', 'bike', 'foot' or 'wheelchair' expected.", 400)
          
        if not self.__coordinates:
            raise OsmException("No coordinates available. Cannot generate distance or time matrix ")

        try:
            for step in range(nrOfSteps):
                self.__log.logging('getRoute',f'request {step+1} of {nrOfSteps}','start')

                if step == 0:
                    coords = self.__coordinates[step*self.__maxNodesInRoute:(step+1)*self.__maxNodesInRoute]
                    
                else:
                    coords = self.__coordinates[step*self.__maxNodesInRoute-1:(step+1)*self.__maxNodesInRoute]

                payload = {}
                payload['coordinates']=coords
                payload['travelmode']=self.__travelmode
                if details=='simplified':
                    payload["geometry_simplify"]= "true"
                else:
                    payload["geometry_simplify"]= "false"
            
                dists = []
                duras = []

                serverTyp, status, data = self.__osmScheduler.openUrl(payload=payload, mode='routing')
                
                if not data:
                    raise OsmException('Something went wrong while getting OSM routes ')
                

                if status!=200:
                    msg='Failed'
                    if serverTyp=='osrm':
                        msg=f"Something went wrong while getting OSM routes : {data['code'], data['message'] } "
                    elif serverTyp=='ors':
                        msg=f"Something went wrong while getting OSM routes : {data['error']['code'], data['error']['message'] } "
                    raise OsmException(msg, status_code=status) 
                else:
                    if serverTyp=='osrm':
                        legs = data["routes"][0]["geometry"]["coordinates"]
                    elif serverTyp=='ors':
                        legs= data['features'][0]['geometry']['coordinates']     
                        tmpWayPoints=data['features'][0]['properties']['way_points']   
                        if len(self.__orsWayPoints)>0:
                            last=self.__orsWayPoints[-1]
                            tmpWayPoints = list(map(lambda x: x + last, tmpWayPoints))
                        self.__orsWayPoints+=tmpWayPoints
                        self.__isOrs=True  
                
                    self.__route+=transformCoords(legs)
                                         
                self.__log.logging('getRoute',f'request {step+1} of {nrOfSteps}','done')



            return status,msg

        except OsmException as e:
            raise OsmException(str(e), status_code=e.status_code)
        except:
            raise OsmException(f'Something went wrong while getting OSM routes: {str(sys.exc_info()[0])}')

  
   

    

