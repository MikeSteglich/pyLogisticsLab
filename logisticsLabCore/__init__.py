""" core of LogisticsLab - optimisation problems and geo services without a transport layer

    used by the REST server (logisticsLabServer) and by the local stdio interface (python -m logisticsLabCore.stdio)
"""

__version__ = '1.0.0'

from . import startTrace
startTrace.step('import logisticsLabCore')

from .exception import *
from .items import *
from .logger import *
from .jobs import FINISHED, OPEN
from .core import *
