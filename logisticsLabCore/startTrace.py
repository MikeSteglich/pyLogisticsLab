""" diagnosis of a solver process that does not start (jobs.WorkerSlot)

    The parent sets LOGLAB_WORKER_TRACE to a file before it starts a solver process. The process writes its steps
    to it and - while it has not started - every TRACE_INTERVAL seconds the stacks of its threads (faulthandler).
    A process that does not start is so shown with the place where it hangs. Without the variable nothing happens.
"""

import os
import time

TRACE_INTERVAL = 20

_file = None


def step(message):
    """ a step of the start - the first step opens the file and starts the stack dumps """
    global _file
    path = os.environ.get('LOGLAB_WORKER_TRACE')
    if not path:
        return
    try:
        if _file is None:
            import faulthandler
            _file = open(path, 'a', buffering=1, encoding='utf-8')
            faulthandler.dump_traceback_later(TRACE_INTERVAL, repeat=True, file=_file)
        _file.write(f'{time.strftime("%H:%M:%S")} pid {os.getpid()} - {message}\n')
    except Exception:
        pass


def started():
    """ the process has started - no more stack dumps """
    if _file is not None:
        import faulthandler
        faulthandler.cancel_dump_traceback_later()
        step('started')
