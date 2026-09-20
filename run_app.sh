#!/bin/bash
# NEXUS // eAMS TERMINAL V241.0 LAUNCHER
cd "$(dirname "$0")"

if [ "$1" == "--server-only" ]; then
    echo "Starting NEXUS // eAMS Backend on http://127.0.0.1:8765 ..."
    exec python3 app.py
else
    exec ./nexus-ams-launcher.sh "$@"
fi
