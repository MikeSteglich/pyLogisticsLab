#***********************************************************************
 #  This code is part of pyLogisticsLab
 #
 #  Copyright (C) 2019 -
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



import io

#*************** LLException ***********************************
class OsmException(Exception):
	
	def __init__(self, msg, module=''):
		self.__msgStr=io.StringIO()
		if 'OsmData error:' not in msg:
			self.__msgStr.write('OsmData error: ')
		if module!='':
			self.__msgStr.write(' ',module,' :')
		self.__msgStr.write(msg)
		

	def __str__(self):
		return 'OsmData error error:'
	
	def __del__(self):
		self.__msgStr.close()

	def getMsg(self):
		return self.__msgStr.getvalue()

	msg = property(getMsg)
#*************** end LLException *******************************


		
		
		
		

		