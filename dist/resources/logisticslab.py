""" entry point of the binary logisticslab (dist/buildCli.py) - the same as python -m logisticsLabCli

    bin/logisticslab finds confs/ next to bin/ (distEnv.py).
"""

import multiprocessing
import sys

import distEnv
distEnv.setup(__file__)

from logisticsLabCli.cli import main

if __name__ == '__main__':
    multiprocessing.freeze_support()    # the solver processes (spawn) start this binary again
    sys.exit(main())
