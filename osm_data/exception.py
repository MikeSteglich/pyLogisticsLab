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
    def __init__(self, message, status_code=500):
        # Rufe den Konstruktor der Basisklasse auf
        super().__init__(message)
        # Speichere den zusätzlichen Status-Code
        self.status_code = status_code
#*************** end LLException *******************************


		
		
		
		

		