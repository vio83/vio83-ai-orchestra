#!/bin/bash
# ============================================================
# VIO 83 AI ORCHESTRA — Auto-Distiller Installer
# ============================================================
# Installa e avvia il daemon di monitoraggio automatico del Mac.
# Ogni file nuovo/modificato viene distillato automaticamente.
#
# USO:
#   chmod +x install_auto_distiller.sh
#   ./install_auto_distiller.sh
#
# DISINSTALLAZIONE:
#   cd ~/Projects/vio83-ai-orchestra
#   python3 -m backend.rag.mac_auto_distiller uninstall
# ============================================================

set -e

echo "============================================================"
echo "VIO 83 AI ORCHESTRA — Auto-Distiller Installer"
echo "============================================================"
echo ""

# Verifica Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 non trovato. Installalo con: brew install python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo "✅ $PYTHON_VERSION"

# Directory del progetto
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "✅ Progetto: $SCRIPT_DIR"

# Installa dipendenze
echo ""
echo "📦 Installazione dipendenze..."
pip3 install httpx watchdog 2>/dev/null || pip3 install httpx watchdog --user 2>/dev/null || {
    echo "⚠️  pip install fallito, provo con --break-system-packages..."
    pip3 install httpx watchdog --break-system-packages 2>/dev/null || true
}

# Crea directory data
mkdir -p "$SCRIPT_DIR/data/logs"
echo "✅ Directory data create"

# Installa LaunchAgent
echo ""
echo "🔧 Installazione LaunchAgent..."
cd "$SCRIPT_DIR"
python3 -m backend.rag.mac_auto_distiller install

# Avvia daemon
echo ""
echo "🚀 Avvio daemon..."
python3 -m backend.rag.mac_auto_distiller start

# Verifica
echo ""
echo "📊 Verifica stato..."
sleep 2
python3 -m backend.rag.mac_auto_distiller status

echo ""
echo "============================================================"
echo "✅ INSTALLAZIONE COMPLETATA!"
echo ""
echo "Il daemon si avvierà automaticamente ad ogni login."
echo ""
echo "COMANDI UTILI:"
echo "  Stato:          python3 -m backend.rag.mac_auto_distiller status"
echo "  Stop:           python3 -m backend.rag.mac_auto_distiller stop"
echo "  Start:          python3 -m backend.rag.mac_auto_distiller start"
echo "  Disinstalla:    python3 -m backend.rag.mac_auto_distiller uninstall"
echo ""
echo "  Harvest API:    python3 -m backend.rag.run_harvest harvest --target 1000000"
echo "  Scan locale:    python3 -m backend.rag.run_harvest local --path ~/Documents"
echo "  Stato harvest:  python3 -m backend.rag.run_harvest status"
echo "============================================================"
