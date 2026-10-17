import os as _os

# CMPL for pyCmpl: if CMPLHOME is not set, the CMPL installation in <project>/cmpl is used (bin/cmpl, Thirdparty/...)
_cmplHome = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'cmpl')
if not _os.environ.get('CMPLHOME') and _os.path.isdir(_os.path.join(_cmplHome, 'bin')):
    _os.environ['CMPLHOME'] = _cmplHome

from .scp import *
from .mcp import *
from .tsp import *
from .cpp import *
from .vrp import *
from .pMedian import *
from .pCentre import *
from .wlp import *
from .Tpp import *
from .exception import *
