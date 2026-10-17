from .exception import *
from . import matrixService


# matrixMode of /v1/matrix -> (field of the answer, kind of matrixService)
MATRICES = {'distances': [('distances', 'distances')],
            'durations': [('durations', 'times')],
            'costs':     [('costs', 'costs')],
            'both':      [('distances', 'distances'), ('durations', 'times')],
            'all':       [('distances', 'distances'), ('durations', 'times'), ('costs', 'costs')]}

MESSAGES = {'distances': 'distance matrix received', 'durations': 'duration matrix received',
            'costs': 'cost matrix received', 'both': 'time and distance matrix received',
            'all': 'distance, time and cost matrix received'}


class MatrixHandler:
    """ /v1/matrix - distances (m), durations (s) and costs from the OSM servers (cached) or as bee line

        content: the matrices of matrixMode and matrixInfo
    """
    def __init__(self, problemData, logger):
        self.__logger = logger
        self.__logger.debug('matrix', 'init')

        self.__content = {}
        self.__httpStatus = 200
        self.__status = 'ok'
        self.__message = 'ok'

        d = problemData
        if not d.coordinates:
            raise LogLabCoreException('no coordinates available')
        info = None
        try:
            for field, kind in MATRICES[d.matrixMode]:
                m, i = matrixService.matrix(d.coordinates, d, kind, d.sources, d.destinations, rounded=d.rounded)
                self.__content[field] = m
                info = matrixService.mergeInfo(info, i)
            self.__content['matrixInfo'] = info
            self.__message = MESSAGES[d.matrixMode]
        except LogLabCoreException as e:
            self.__status = 'error'
            self.__message = str(e)
            self.__httpStatus = e.httpStatus
            self.__logger.error('matrix', str(e))

        self.__logger.debug('matrix', 'done')

    def getContent(self):
        return self.__content
    content = property(getContent)

    def getStatus(self):
        return self.__status
    status = property(getStatus)

    def getHttpStatus(self):
        return self.__httpStatus
    httpStatus = property(getHttpStatus)

    def getMessage(self):
        return self.__message
    message = property(getMessage)
