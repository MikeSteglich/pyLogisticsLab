""" places of a binary distribution of LogisticsLab (dist/buildStdio.py, dist/buildCli.py)

    The program lies in bin/ of the distribution, the configuration in confs/ next to bin/.
    Without LOGLAB_CONF_DIR it is set to this confs/, without LOGLAB_LOG_DIR to a directory of the user.
    Must be imported before logisticsLabCore and osm_data.
"""

import os
import sys


def setup(mainFile):
    # Nuitka: __file__ of the main module is <dist>/bin/<name>.py
    root = os.path.dirname(os.path.dirname(os.path.abspath(mainFile)))
    if not os.environ.get('LOGLAB_CONF_DIR') and os.path.isdir(os.path.join(root, 'confs')):
        os.environ['LOGLAB_CONF_DIR'] = os.path.join(root, 'confs')
    if not os.environ.get('LOGLAB_LOG_DIR'):
        if sys.platform == 'win32':
            logs = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'LogisticsLab', 'logs')
        elif sys.platform == 'darwin':
            logs = os.path.join(os.path.expanduser('~'), 'Library', 'Logs', 'LogisticsLab')
        else:
            logs = os.path.join(os.environ.get('XDG_STATE_HOME') or os.path.expanduser('~/.local/state'),
                                'logisticsLab')
        os.environ['LOGLAB_LOG_DIR'] = logs
