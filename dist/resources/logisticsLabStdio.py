""" entry point of the binary logisticsLabStdio (dist/buildStdio.py) - the same as python -m logisticsLabCore.stdio

    The binary lies in bin/ of the distribution, the configuration in confs/ next to bin/ - without
    LOGLAB_CONF_DIR it is set to this confs/, without LOGLAB_LOG_DIR to a directory of the user
    (an app should pass --logPath anyway).
"""

import multiprocessing
import os
import sys

# Nuitka: __file__ of the main module is <dist>/bin/logisticsLabStdio.py
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.environ.get('LOGLAB_CONF_DIR') and os.path.isdir(os.path.join(_root, 'confs')):
    os.environ['LOGLAB_CONF_DIR'] = os.path.join(_root, 'confs')
if not os.environ.get('LOGLAB_LOG_DIR'):
    if sys.platform == 'win32':
        _logs = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'LogisticsLab', 'logs')
    elif sys.platform == 'darwin':
        _logs = os.path.join(os.path.expanduser('~'), 'Library', 'Logs', 'LogisticsLab')
    else:
        _logs = os.path.join(os.environ.get('XDG_STATE_HOME') or os.path.expanduser('~/.local/state'), 'logisticsLab')
    os.environ['LOGLAB_LOG_DIR'] = _logs

from logisticsLabCore.stdio import main

if __name__ == '__main__':
    multiprocessing.freeze_support()    # the solver processes (spawn) start this binary again
    main()
