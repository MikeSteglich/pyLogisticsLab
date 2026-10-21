#!/bin/sh
#
# @NAME@ - Teil der LogisticsLab-Distribution (Linux/macOS)
# @WHAT@

HERE="$(cd "$(dirname "$0")" && pwd)"

# Logs und Matrix-Cache im Benutzerverzeichnis, nicht im (evtl. schreibgeschuetzten) Programmverzeichnis
if [ -z "$LOGLAB_LOG_DIR" ]; then
	if [ "$(uname)" = "Darwin" ]; then
		LOGLAB_LOG_DIR="$HOME/Library/Logs/LogisticsLab"
	else
		LOGLAB_LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/logisticsLab"
	fi
	export LOGLAB_LOG_DIR
fi

# -I bzw. -E -s: keine PYTHON*-Variablen, kein User-site-packages - nur das, was in der Distribution liegt
exec "$HERE/python/bin/python3" @PYARGS@ "$@"
