""" creates the api keys of the server tests and writes them to tests/serverTests/.env

    python createTestKeys.py [--url http://127.0.0.1:8000/v1/] [--keyFile FILE]
    python createTestKeys.py --remove

    Two keys are created (existing ones with these names are replaced - every run creates new keys):
        serverTests              all services                  -> LOGLAB_API_KEY
        serverTestsRestricted    only tsp, i.e. without others -> LOGLAB_API_KEY_RESTRICTED
    The key file of the server contains only the hashes, the keys themselves are only in .env (not versioned).
    For a remote server the script has to run on the server (--keyFile of the server), then copy .env to the client.

    In addition the fixed example key of tests/serverExamples is registered (name localExample). The key is in the
    code of the examples, i.e. public - it is only registered in the key file of the local server, never with
    --keyFile of another server. --noExampleKey skips it.
"""

import argparse
import os
import sys

serverDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'logisticsLabServer')
sys.path.insert(0, os.path.abspath(serverDir))

from manageKeys import readKeys, writeKeys, defaultKeyFile
from apiKeys import ApiKey, newKey, hashKey


ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
KEYS = {'serverTests': None, 'serverTestsRestricted': ['tsp']}     # name -> allowed services (None: all)

# example key of tests/serverExamples - public, only for the local server
EXAMPLE_NAME = 'localExample'
EXAMPLE_KEY = 'loglab-local-example-key'


def removeTestKeys(keyFile):
    entries = readKeys(keyFile)
    rest = [ e for e in entries if e.get('name') not in KEYS and e.get('name') != EXAMPLE_NAME ]
    if len(rest) != len(entries):
        writeKeys(keyFile, rest)
    return rest


def main():
    parser = argparse.ArgumentParser(description='creates the api keys of the server tests')
    parser.add_argument('--url', default='http://127.0.0.1:8000/v1/', help='server address for the tests')
    parser.add_argument('--keyFile', default=defaultKeyFile, help='key file of the server')
    parser.add_argument('--remove', action='store_true', help='removes the test keys and .env')
    parser.add_argument('--noExampleKey', action='store_true', help='without the example key of tests/serverExamples')
    args = parser.parse_args()
    isLocalKeyFile = os.path.abspath(args.keyFile) == os.path.abspath(defaultKeyFile)

    entries = removeTestKeys(args.keyFile)
    if args.remove:
        if os.path.exists(ENV_FILE):
            os.remove(ENV_FILE)
        print(f'test keys removed from {args.keyFile}, {ENV_FILE} deleted')
        return

    keys = {}
    for name, allowed in KEYS.items():
        key = newKey()
        entry = {'name': name, 'hash': hashKey(key)}
        if allowed:
            entry['allowed'] = allowed
        ApiKey(entry, 0)                # checks the entry
        entries.append(entry)
        keys[name] = key
    if not args.noExampleKey:
        if isLocalKeyFile:
            entries.append({'name': EXAMPLE_NAME, 'hash': hashKey(EXAMPLE_KEY)})
        else:
            print(f'example key {EXAMPLE_NAME} not registered - it is public and only for the local server')
    writeKeys(args.keyFile, entries)

    # .env only readable by the owner - it contains the keys in clear text
    fd = os.open(ENV_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write('# created by createTestKeys.py - not versioned\n')
        f.write(f'LOGLAB_URL={args.url}\n')
        f.write(f"LOGLAB_API_KEY={keys['serverTests']}\n")
        f.write(f"LOGLAB_API_KEY_RESTRICTED={keys['serverTestsRestricted']}\n")
    os.chmod(ENV_FILE, 0o600)

    print(f'test keys serverTests and serverTestsRestricted written to {args.keyFile} (hashes) and {ENV_FILE}')


if __name__ == '__main__':
    main()
