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


class Problem:
    def __init__(self, id, type='tsp'):
        self.__type = self.__setType(type)
        self.__status = None
        self.__results = None
        self.__message = ''

    def getType(self):
        return self.__type
    type = property(getType)

    def getStatus(self):
        return self.__status
    status = property(getStatus)

    def getResults(self):
        return self.__results
    results = property(getResults)

    def getMessage(self):
        return self.__message
    message = property(getMessage)

   
    def __setType(self, type):
        if not isinstance(type, str):
            raise LogLabServerException(f'wrong type {type}')
        if type.upper() not in ['tsp', 'cpp', 'tpp', 'nwf', 'clp', 'dlp', 'vrp' ]:
            raise LogLabServerException(f'wrong type {type}')



class ProblemQueue:
    def __init__(self, maxProblems):
        problems={}
        pass

    def addProblem(self):
        pass

