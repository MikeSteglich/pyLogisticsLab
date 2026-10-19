#!/bin/bash
# runs the server regression test against a local server
#
#   PYTHON=/opt/anaconda3/envs/pyLogisticsLab/bin/python ./runServerTests.sh [script.py ...]
#
# 1. creates new test keys (createTestKeys.py -> .env, not versioned)
# 2. starts the server on port 8000 if it is not running (and stops it at the end)
# 3. runs checkServer.py or the given scripts, e.g. findContPCentreServer.py

PYTHON=${PYTHON:-python3}
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$TESTS_DIR/../.." && pwd)"
URL=http://127.0.0.1:8000/v1/

"$PYTHON" "$TESTS_DIR/createTestKeys.py" --url "$URL" || exit 1

SERVER_PID=
if ! curl -s -o /dev/null "${URL}results"; then
    echo "starting the server - log: $TESTS_DIR/server.log"
    (cd "$PROJECT_DIR/logisticsLabServer" && \
     exec "$PYTHON" -m uvicorn main:app --host 127.0.0.1 --port 8000) > "$TESTS_DIR/server.log" 2>&1 &
    SERVER_PID=$!
    trap 'kill $SERVER_PID 2>/dev/null; wait $SERVER_PID 2>/dev/null' EXIT
    for i in $(seq 1 60); do
        curl -s -o /dev/null "${URL}results" && break
        if ! kill -0 $SERVER_PID 2>/dev/null; then
            echo "the server has stopped - see $TESTS_DIR/server.log"; exit 1
        fi
        sleep 0.5
    done
fi

cd "$TESTS_DIR"
status=0
for script in "${@:-checkServer.py}"; do
    "$PYTHON" "$script" || status=1
done
exit $status
