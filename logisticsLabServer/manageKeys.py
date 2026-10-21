""" manages the api keys of the LogisticsLab server

    python manageKeys.py add NAME [--expires 2027-03-31] [--allowed tsp,tpp] [--maxOpenProblems 3]
    python manageKeys.py list
    python manageKeys.py disable NAME
    python manageKeys.py enable NAME
    python manageKeys.py remove NAME

    The key is shown only once by 'add'. The key file contains only its sha256 hash.
    The server reloads the key file automatically - a restart is not necessary.
"""

import os
import sys

from apiKeys import *
from logisticsLabCore import paths

import argparse
import datetime
import yaml


defaultKeyFile = paths.confFile('apiKeys.yml')


def readKeys(keyFile):
    if not os.path.isfile(keyFile):
        return []
    with open(keyFile, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or []

def writeKeys(keyFile, entries):
    tmpFile = keyFile + '.tmp'
    with open(tmpFile, 'w', encoding='utf-8') as f:
        yaml.safe_dump(entries, f, sort_keys=False, allow_unicode=True)
    os.chmod(tmpFile, 0o600)
    # atomic replace - the server never reads a half written file
    os.replace(tmpFile, keyFile)

def findEntry(entries, name):
    for e in entries:
        if e.get('name') == name:
            return e
    sys.exit(f'api key {name} not found')


def add(args):
    entries = readKeys(args.keyFile)
    if any(e.get('name') == args.name for e in entries):
        sys.exit(f'api key {args.name} exists already')

    key = newKey()
    entry = {'name': args.name, 'hash': hashKey(key)}
    if args.expires:
        entry['expires'] = datetime.date.fromisoformat(args.expires)
    if args.allowed:
        entry['allowed'] = [s.strip() for s in args.allowed.split(',')]
    if args.maxOpenProblems:
        entry['maxOpenProblems'] = args.maxOpenProblems

    ApiKey(entry, 0)    # checks the entry
    entries.append(entry)
    writeKeys(args.keyFile, entries)

    print(f'api key for {args.name} (shown only once):')
    print(key)

def listKeys(args):
    for e in readKeys(args.keyFile):
        k = ApiKey(e, 0)
        state = 'valid' if k.isValid() else ('disabled' if k.disabled else 'expired')
        print(f"{k.name:25} {state:9} expires: {str(k.expires or '-'):10}  allowed: {','.join(k.allowed)}"
              + (f"  maxOpenProblems: {e['maxOpenProblems']}" if 'maxOpenProblems' in e else ''))

def setDisabled(args, disabled):
    entries = readKeys(args.keyFile)
    findEntry(entries, args.name)['disabled'] = disabled
    writeKeys(args.keyFile, entries)
    print(f"api key {args.name} {'disabled' if disabled else 'enabled'}")

def remove(args):
    entries = readKeys(args.keyFile)
    findEntry(entries, args.name)
    writeKeys(args.keyFile, [e for e in entries if e.get('name') != args.name])
    print(f'api key {args.name} removed')


parser = argparse.ArgumentParser(description='manages the api keys of the LogisticsLab server')
parser.add_argument('--keyFile', default=defaultKeyFile, help='default: confs/apiKeys.yml (or LOGLAB_CONF_DIR)')
sub = parser.add_subparsers(dest='command', required=True)

p = sub.add_parser('add', help='creates a new key')
p.add_argument('name')
p.add_argument('--expires', help='last valid day, e.g. 2027-03-31')
p.add_argument('--allowed', help=f"comma separated list of {','.join(SERVICES)} (default: all)")
p.add_argument('--maxOpenProblems', type=int, help='default: maxOpenProblemsPerKey of the server config')
p.set_defaults(func=add)

sub.add_parser('list', help='lists all keys').set_defaults(func=listKeys)

p = sub.add_parser('disable', help='blocks a key')
p.add_argument('name')
p.set_defaults(func=lambda a: setDisabled(a, True))

p = sub.add_parser('enable', help='unblocks a key')
p.add_argument('name')
p.set_defaults(func=lambda a: setDisabled(a, False))

p = sub.add_parser('remove', help='deletes a key')
p.add_argument('name')
p.set_defaults(func=remove)

if __name__ == '__main__':
    args = parser.parse_args()
    try:
        args.func(args)
    except LogLabServerException as e:
        sys.exit(str(e))
