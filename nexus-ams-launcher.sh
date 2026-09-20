#!/bin/bash
# ==============================================================================
# NEXUS // eAMS TERMINAL STANDALONE APPLICATION LAUNCHER
# Standard: AlVG & Radical Objectivity (Roland Sauer, PSTNR: 4368522)
# ==============================================================================

set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8765
URL="http://127.0.0.1:${PORT}"
LOG_FILE="/tmp/nexus_ams_app.log"
APP_PROFILE="${APP_DIR}/.app-profile"

mkdir -p "${APP_PROFILE}"

# 1. Prüfe ob Backend läuft
is_running() {
    curl -s --max-time 1 "${URL}/api/status" > /dev/null 2>&1
}

if ! is_running; then
    echo "⚡ Starte NEXUS eAMS Backend Server auf Port ${PORT}..."
    cd "${APP_DIR}"
    nohup python3 app.py > "${LOG_FILE}" 2>&1 &
    
    # Warte bis Server antwortet (max 10s)
    RETRIES=20
    while [ $RETRIES -gt 0 ]; do
        if is_running; then
            echo "✓ Server erfolgreich gestartet!"
            break
        fi
        sleep 0.5
        RETRIES=$((RETRIES - 1))
    done

    if [ $RETRIES -eq 0 ]; then
        echo "❌ Fehler: Server konnte nicht rechtzeitig gestartet werden. Siehe ${LOG_FILE}"
        exit 1
    fi
else
    echo "✓ Backend-Server läuft bereits auf ${URL}"
fi

# 2. Öffne eigenständiges App-Fenster
echo "🚀 Öffne NEXUS eAMS Standalone-App-Fenster..."

if command -v google-chrome >/dev/null 2>&1; then
    nohup google-chrome \
        --app="${URL}" \
        --class="nexus-ams" \
        --name="nexus-ams" \
        --user-data-dir="${APP_PROFILE}" \
        --window-size=1400,900 \
        "$@" >/dev/null 2>&1 &
elif command -v chromium >/dev/null 2>&1; then
    nohup chromium \
        --app="${URL}" \
        --class="nexus-ams" \
        --name="nexus-ams" \
        --user-data-dir="${APP_PROFILE}" \
        --window-size=1400,900 \
        "$@" >/dev/null 2>&1 &
else
    echo "Öffne im Standard-Browser..."
    xdg-open "${URL}"
fi
