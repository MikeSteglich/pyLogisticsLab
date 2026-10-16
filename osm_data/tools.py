from .exception import *

import pickle
import tempfile
import os
import sys

dumpFile = tempfile.gettempdir() + os.sep + "logisticslab-backend.dump"


def dumpConf(conf):
    checkConfig(conf)
    #dumpFile = tempfile.gettempdir() + os.sep + "logisticslab-backend.dump"
    try:
        with open(dumpFile, 'wb') as _dumpFile:
            pickle.dump(conf, _dumpFile)
    except:
        raise OsmException(f'Something went wrong while writing configuration to dump file: {str(sys.exc_info()[0])}')

def readConf():
    #dumpFile = tempfile.gettempdir() + os.sep + "logisticslab-backend.dump"
    try:
        with open(dumpFile, 'rb') as _dumpFile:
            conf = pickle.load(_dumpFile)
            checkConfig(conf)
        return conf
    except:
        raise OsmException(f'Something went wrong while reading configuration to dump file: {str(sys.exc_info()[0])}')


def checkConfig(conf):
    if not isinstance(conf, dict):
        raise OsmException(f'OsmTools error: Wrong configuration object')

def checkLog(log):
     if not 'osm_data.logging.Logging' in str(type(log)):
        raise OsmException(f'OsmTools error: Wrong logging object')
     
def checkStrList(vec):
    if not isinstance(vec, list):
        raise OsmException(f'OsmTools error: Wrong vector. It is not an array.')
        
    if not all( isinstance(e,str) for e in vec  ):
        raise OsmException(f'OsmTools error: Wrong vector. Contains more than just strings.')

    return vec

def checkIntVector(vec):
    if not isinstance(vec, list):
        raise OsmException(f'OsmTools error: Wrong vector. It is not an array.')
        
    if not all( isinstance(e,int) for e in vec  ):
        raise OsmException(f'OsmTools error: Wrong vector. Contains more than just integers.')
    
    return vec
       
def checkIntMatrix(matrix):
    if not isinstance(matrix, (list,tuple)):
        raise OsmException(f'OsmTools error: Wrong matrix. It is not an array.')
        
    if not all ( isinstance(row,(list,tuple) ) for row in matrix  ):
        raise OsmException(f'OsmTools error: Wrong matrix. It is not an array.')
        
    if not all( isinstance(element,int) for row in matrix for element in row ):
        raise OsmException(f'OsmTools error: Wrong matrix. Contains more than just integers.')
        
    return matrix

def checkSingleCoordinates(coordinates):

    if not isinstance(coordinates,(tuple,list)) :
        raise OsmException(f'OsmTools error: Wrong coordinates list. Contains more than just 2-tuples.')
    
    if len(coordinates) != 2:
        raise OsmException(f'OsmTools error: Wrong coordinates list. Contains more than just 2-tuples.')

    lat=coordinates[0]    
    lon=coordinates[1]   
    if not ( isinstance(lat, (float,int) ) and isinstance(lon, (float,int)) ):
        raise OsmException(f'Wrong coordinate: ({lat};{lon})')
    if not (abs(lat)<=90 and abs(lon)<= 180):
        raise OsmException(f'Wrong coordinate: ({lat};{lon})')

def checkCoordinates(coordinates):  
    if not isinstance(coordinates, (list,tuple)):
        raise OsmException(f'OsmTools error: Wrong coordinates list. It is not an array.')
    
    if not all( isinstance(e,(tuple,list)) for e in coordinates  ):
        raise OsmException(f'OsmTools error: Wrong coordinates list. Contains more than just 2-tuples.')
    
    if not all( len(e)==2 for e in coordinates  ):
        raise OsmException(f'OsmTools error: Wrong coordinates list. Contains more than just 2-tuples.')
    
    for c in coordinates:
        lat=c[0]    
        lon=c[1]   
        if not ( isinstance(lat, (float,int) ) and isinstance(lon, (float,int)) ):
            raise OsmException(f'Wrong coordinate: ({lat};{lon})')
        if not (abs(lat)<=90 and abs(lon)<= 180):
            raise OsmException(f'Wrong coordinate: ({lat};{lon})')
        
def transformCoords(coordinates):
    return [ (i,j) for (j,i) in coordinates]
    

    
  