from .exception import *


def setMipGap(mGap):
    if isinstance(mGap, float):
        mipGap = mGap
    else:
        raise LogLabException(f'LogisticsLab error: Wrong mipGap: {mGap}' )
    return mipGap
            
        
def setMaxSolvingTime(maxTime):
    if isinstance(maxTime, int):
        maxSolvingTime = maxTime
    else:
        raise LogLabException(f'LogisticsLab error: Wrong maximal solving time: {maxTime}' )
    return maxSolvingTime


def setNumVector(vector, length=0):
    if not isinstance(vector,(list,tuple)):
        raise LogLabException(f'LogisticsLab error: Wrong vector ')
    
    if length>0 and len(vector)!=length:
        raise LogLabException(f'LogisticsLab error: Wrong vector ')
        
    elif not all( isinstance(element,(float,int)) for element in vector ):
        raise LogLabException(f'LogisticsLab error: Wrong vector, Contains more than just numbers.')
        
    return vector   

def setIntVector(vec):
    if not isinstance(vec, list):
        raise LogLabException(f'LogisticsLab error: Wrong vector. It is not an array.')
        
    if not all( isinstance(e,int) for e in vec  ):
        raise LogLabException(f'LogisticsLab error: Wrong vector. Contains more than just integers.')
    
    return vec


def setNum(num):
    if not isinstance(num,(float,int)):
        raise LogLabException(f'LogisticsLab error: Wrong number: {num}')
    return num
        


def setDistMatrix(matrix):
    """ set and checks the distance matrix """
    if not isinstance(matrix, (list,tuple)):
        raise LogLabException(f'LogisticsLab error: Wrong matrix. It is not an array.')
        
    if not all ( isinstance(row,(list,tuple) ) for row in matrix  ):
        raise LogLabException(f'LogisticsLabP error: Wrong matrix. It is not an array.')
        
    if not all( isinstance(element,(float,int)) for row in matrix for element in row ):
        raise LogLabException(f'LogisticsLab error: Wrong matrix. Contains more than just numbers.')
        
    return matrix


def coveringMatrix(matrix,radius):
    coveringMatrix = [[ 1 if distanz <= radius else 0 for distanz in zeile] for zeile in matrix]
    return coveringMatrix

def setEdges( edges, nrOfNodes=0):

    if edges!=None:
        if not isinstance(edges, (list, tuple)):
            raise LogLabException(f'LogisticsLab error: Wrong edges. It is not an list or tuple.')
        
        for t in edges:
            if not isinstance(t,(list, tuple)) or not all(isinstance(i,int) for i in t):
                raise LogLabException(f'LogisticsLab error: Wrong edges {t}')
            if nrOfNodes>0:
                if t[0]<0 or t[0]>=nrOfNodes:
                    raise LogLabException(f'LogisticsLab error: Wrong edges {t}')
                if t[1]<0 or t[1]>=nrOfNodes:
                    raise LogLabException(f'LogisticsLab error: Wrong edges {t}')
    return edges
    
       
def setNumMatrix(matrix):
         
    if not isinstance(matrix, (list,tuple)):
        raise LogLabException(f'LogisticsLab error: Wrong matrix. It is not an array.')
        
    if not all ( isinstance(row,(list,tuple) ) for row in matrix  ):
        raise LogLabException(f'LogisticsLab error: Wrong matrix. It is not an array.')
        
    if not all( isinstance(element,(int, float)) for row in matrix for element in row ):
        raise LogLabException(f'LogisticsLab error: Wrong matrix. Contains more than just integers.')
        
    return matrix
      
def setIntMatrix(matrix):

    if not isinstance(matrix, (list,tuple)):
        raise LogLabException(f'LogisticsLab error: Wrong matrix. It is not an array.')
        
    if not all ( isinstance(row,(list,tuple) ) for row in matrix  ):
        raise LogLabException(f'LogisticsLab error: Wrong matrix. It is not an array.')
        
    if not all( isinstance(element,int) for row in matrix for element in row ):
        raise LogLabException(f'LogisticsLab error: Wrong matrix. Contains more than just integers.')
        
    return matrix
    