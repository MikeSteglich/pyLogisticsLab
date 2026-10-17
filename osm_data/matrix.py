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
from .logging import *
from .scheduler import *
from .tools import *

import sys
import math


class Matrix:
    def __init__(self, coords, sources=None, destinations=None, conf=None):

        if conf:
            checkConfig(conf)
            self.__config = conf
        else:
            self.__config = readConf()

        self.__log = Logging(self.__config.get('logFile'),self.__config['logging'])
        self.__osmScheduler = Scheduler(self.__config, self.__log) 
        
        self.__nrOfDestinations=0
        self.__destinations=None
        self.__nrOfSources=0
        self.__sources=None
        self.__nrOfNodes=0

        self.__maxTableSize = self.__config['servers']['maxTableSize']

        checkCoordinates(coords)
        self.__origCoords = coords
        self.__coordinates=transformCoords(coords)
        self.__nrOfNodes=len(coords)

        if sources!=None: 
            checkIntVector(sources)
            self.__nrOfSources=len(sources)
            self.__sources=sources
            if min(sources)<0 or max(sources)>len(coords)-1:
                raise OsmException(f'Wrong source indices - out of range')
            if destinations==None:
                self.__nrOfDestinations=self.__nrOfNodes
                self.__destinations=list(range(self.__nrOfDestinations))

        if destinations!=None: 
            checkIntVector(destinations)
            self.__nrOfDestinations=len(destinations)
            self.__destinations=destinations
            if min(destinations)<0 or max(destinations)>len(coords)-1:
                raise OsmException(f'Wrong destinations indices - out of range')
            if sources==None:
                self.__nrOfSources=self.__nrOfNodes
                self.__sources=list(range(self.__nrOfSources))        
        
        if self.__nrOfSources==0 and self.__nrOfDestinations==0:
            self.__nrOfSources=self.__nrOfDestinations=self.__nrOfNodes
            self.__sources=list(range(self.__nrOfSources))
            self.__destinations=list(range(self.__nrOfDestinations))
           
        if self.__nrOfDestinations>self.__maxTableSize:
            raise OsmException(f'Size of request is to big. Max table size is {self.__maxTableSize}')

        self.__beeLineDistances = []
        self.__distMatrix = []
        self.__durasMatrix = []
          
        self.__matrixStatus = 'exact'
        self.__fillFactors = None

       
    def __checkDistances(self):
        self.__matrixStatus = 'exact'
        self.__fillFactors = None
        self.__greatCircleDistances()
        sDistOsm = 0
        sDistGc = 0
        sTime = 0

        pIndices = []

        for i,row in enumerate(self.__distMatrix):
            for j, dist in enumerate(row):
                if dist!=None: 
                    if dist == 0:
                        if self.__coordinates[self.__sources[i]]!=self.__coordinates[self.__destinations[j]]:
                            pIndices.append((i,j))
                    else:
                        if dist*1.01 < self.__beeLineDistances[i][j] :
                            pIndices.append([i,j])
                        else:
                            sDistGc += self.__beeLineDistances[i][j]
                            sDistOsm += dist
                            sTime += self.__durasMatrix[i][j]
                else:
                    pIndices.append([i,j])
                     
        if sDistGc!=0:
            detourFactor = sDistOsm/sDistGc
            timeFactor = sTime/sDistGc
        else:
            detourFactor = 1
            timeFactor = 1

        for i,j in pIndices:
            self.__distMatrix[i][j] = self.__beeLineDistances[i][j] * detourFactor
            self.__durasMatrix[i][j] = self.__beeLineDistances[i][j] * timeFactor

        if len(pIndices)>0:
            self.__matrixStatus = 'unexact'
            # missing or implausible values: bee line distance x average detour (distance) or time factor (s/m)
            self.__fillFactors = {'detourFactor': detourFactor, 'timeFactor': timeFactor, 'nrOfFilledValues': len(pIndices)}

        for i,row in enumerate(self.__durasMatrix):
            for j, tTime in enumerate(row):
                if self.__sources[i]!=self.__destinations[j] and tTime==0:
                   self.__durasMatrix[i][j] = self.__beeLineDistances[i][j] * timeFactor

       
    def __greatCircleDistance(self, i, j ):
        '''calculates the great circle distance between to nodes depending on its coordinates'''
        lat1, lon1 = self.__origCoords[i] 
        lat2, lon2 = self.__origCoords[j] 
        dlat = math.radians(lat2-lat1)
        dlon = math.radians(lon2-lon1)
        a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1))* math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return ( 6378.137 * c * 1000)
        

    def __greatCircleDistances(self):
        '''Calculates great circle distances for checking distances retrieved from osr or osrm'''
        self.__beeLineDistances = [ [ self.__greatCircleDistance(i,j) for j in self.__destinations ] for i in self.__sources]

    
    def __initMatrices(self):
        self.__distMatrix = [ [ 0 for j in range(self.__nrOfDestinations)]  for i in range(self.__nrOfSources)]
        self.__durasMatrix = [ [ 0 for j in range(self.__nrOfDestinations)]  for i in range(self.__nrOfSources)]

    def getMatrixstatus(self):
        return self.__matrixStatus
    
    matrixStatus = property(getMatrixstatus)

    def getFillFactors(self):
        """ None or the factors used for the missing or implausible values of an unexact matrix """
        return self.__fillFactors

    fillFactors = property(getFillFactors)

    def getDistanceMatrix(self):
        return self.__distMatrix

    distanceMatrix = property(getDistanceMatrix)

    def getTimeMatrix(self):
        return self.__durasMatrix

    timeMatrix = property(getTimeMatrix)

    
    def loadMatrix(self, travelmode='car'):
        
        self.__initMatrices()
        msg='OK'

        maxRowPerStep = math.floor( self.__maxTableSize/self.__nrOfDestinations)
        nrOfSteps = math.ceil(self.__nrOfSources/maxRowPerStep)

        if travelmode not in ('car','bike','foot','wheelchair'):
            raise OsmException(f"Wrong travelmode {travelmode} -'car', 'bike', 'foot' or 'wheelchair' expected.", 400)
          
        if not self.__coordinates:
            raise OsmException("No coordinates available. Cannot generate distance or time matrix ")

        try:
            for step in range(nrOfSteps):
                self.__log.logging('getMatrix',f'request {step+1} of {nrOfSteps}','start')
                payload = {}
                payload['locations']=self.__coordinates
                payload['destinations']=self.__destinations 
                payload['travelmode']=travelmode
            
                stepStart = step*maxRowPerStep
                stepEnd = stepStart+maxRowPerStep
                if stepEnd>=self.__nrOfSources:
                    stepEnd = self.__nrOfSources
                payload['sources'] = self.__sources[stepStart:stepEnd]

                dists = []
                duras = []

                serverTyp, status, data = self.__osmScheduler.openUrl(payload=payload, mode='matrix')
                
                if not data:
                    raise OsmException('Something went wrong while getting OSM distances ')
                
                if status!=200:
                    msg='failed'
                    if serverTyp=='osrm':
                        msg=f"Something went wrong while getting OSM distances : {status, data['code'], data['message'] } "
                    elif serverTyp=='ors':
                        msg=f"Something went wrong while getting OSM distances : {status, data['error']['code'], data['error']['message'] } "
                    raise OsmException(msg, status_code=status) 
                
                dists =  data['distances']
                duras =  data['durations']

                for ii,i in enumerate(range(stepStart,stepEnd)):
                    self.__distMatrix[i]= dists[ii]
                    self.__durasMatrix[i] = duras[ii]

                self.__log.logging('getMatrix',f'request {step+1} of {nrOfSteps}','done')
               
            self.__checkDistances()

            return status,msg

        except OsmException as e:
            raise OsmException(str(e), status_code=e.status_code)
        except:
            raise OsmException(f'Something went wrong while getting OSM data: {str(sys.exc_info()[0])}')

  
   

    

