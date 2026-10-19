""" the JSON-RPC protocol of the local interface without a helper module - every message is printed

    python rawProtocol.py

    1. start the local interface as child process and wait for the notification ready
    2. request solve - the answer contains the id of the problem
    3. the process sends jobStatus for every change of the status (waiting, running, solution ...)
    4. request result - the answer contains the results, the problem is deleted afterwards
    5. request shutdown
"""

import json
import subprocess
import sys


# stdout of the child process is only used for the protocol, its log output goes to stderr
process = subprocess.Popen([sys.executable, '-m', 'logisticsLabCore.stdio'],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           text=True, encoding='utf-8', bufsize=1)


def send(id, method, params):
    """ one request = one line of JSON """
    line = json.dumps({"jsonrpc": "2.0", "id": id, "method": method, "params": params})
    print('->', line)
    process.stdin.write(line + '\n')
    process.stdin.flush()


def receive():
    """ next message of the process - an answer (with id) or a notification (with method) """
    line = process.stdout.readline()
    print('<-', line.strip()[:200])
    return json.loads(line)


# 1. ready
while receive().get('method') != 'ready':
    pass

# 2. solve - a transportation problem
send(1, 'solve', {"type": "tpp", "varCosts": [[3, 2, 7, 6], [7, 5, 2, 3], [2, 5, 4, 5]],
                  "supplies": [5000, 6000, 2500], "demands": [6000, 4000, 2000, 1500]})

# 3. wait for the answer of solve and for jobStatus solution / noSolution / error - in any order
problemId = None
finished = False
while problemId is None or not finished:
    msg = receive()
    if msg.get('id') == 1:
        if 'error' in msg:
            print('rejected:', msg['error'])
            raise SystemExit(1)
        problemId = msg['result']['id']
    elif msg.get('method') == 'jobStatus' and msg['params']['status'] in ('solution', 'noSolution', 'error', 'cancelled'):
        finished = True

# 4. result
send(2, 'result', {"id": problemId})
msg = receive()
while msg.get('id') != 2:
    msg = receive()
answer = msg['result']
print('\nstatus:', answer['status'], '- objVal:', answer.get('results', {}).get('objVal'))
print('flows:', answer.get('results', {}).get('flows'), '\n')

# 5. shutdown - the process stops after the answer
send(3, 'shutdown', {})
while receive().get('id') != 3:
    pass
process.stdin.close()
process.wait(10)
