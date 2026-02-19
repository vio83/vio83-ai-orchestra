#!/bin/zsh
# ============================================================
# 🎵 VIO 83 AI ORCHESTRA — Launcher Completo
# ============================================================
# Uso:
#   ./orchestra.sh          → Avvia TUTTO (frontend + backend + ollama + VS Code)
#   ./orchestra.sh start    → Avvia TUTTO
#   ./orchestra.sh dev      → Solo frontend (npm run dev)
#   ./orchestra.sh backend  → Solo backend Python
#   ./orchestra.sh build    → Build di produzione
#   ./orchestra.sh stop     → Ferma tutti i servizi
#   ./orchestra.sh status   → Mostra cosa è in esecuzione
#   ./orchestra.sh test     → Esegui tutti i test
#   ./orchestra.sh open     → Apri solo VS Code sul progetto
#   ./orchestra.sh help     → Mostra questo aiuto
# ============================================================

# Colori per output leggibile
GREEN='\033[0;32m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
DIM='\033[2m'
BOLD='\033[1m'
RESET='\033[0m'

# Percorso del progetto
PROJECT_DIR="/Users/padronavio/Projects/vio83-ai-orchestra"
FRONTEND_PORT=5173
BACKEND_PORT=4000
OLLAMA_PORT=11434

# File PID per tracciare i processi avviati
PID_DIR="$PROJECT_DIR/.pids"

# ============================================================
# FUNZIONI UTILITY
# ============================================================

banner() {
    echo ""
    echo "${GREEN}╔══════════════════════════════════════════════════╗${RESET}"
    echo "${GREEN}║${RESET}  ${MAGENTA}🎵${RESET}  ${BOLD}VIO 83 AI ORCHESTRA${RESET}  ${MAGENTA}🎵${RESET}                      ${GREEN}║${RESET}"
    echo "${GREEN}║${RESET}  ${DIM}One app. Every AI. Smart routing.${RESET}               ${GREEN}║${RESET}"
    echo "${GREEN}╚══════════════════════════════════════════════════╝${RESET}"
    echo ""
}

log_ok() {
    echo "${GREEN}  ✅ $1${RESET}"
}

log_info() {
    echo "${CYAN}  ℹ️  $1${RESET}"
}

log_warn() {
    echo "${YELLOW}  ⚠️  $1${RESET}"
}

log_error() {
    echo "${RED}  ❌ $1${RESET}"
}

log_step() {
    echo ""
    echo "${MAGENTA}  ▸ STEP $1: $2${RESET}"
    echo "${DIM}  ─────────────────────────────────────${RESET}"
}

# Controlla se una porta è in uso
port_in_use() {
    lsof -i :$1 > /dev/null 2>&1
}

# Salva PID di un processo
save_pid() {
    mkdir -p "$PID_DIR"
    echo "$2" > "$PID_DIR/$1.pid"
}

# Leggi PID salvato
get_pid() {
    local pidfile="$PID_DIR/$1.pid"
    if [ -f "$pidfile" ]; then
        cat "$pidfile"
    fi
}

# Controlla se un processo è vivo
is_running() {
    local pid=$(get_pid "$1")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        return 0
    fi
    return 1
}

# ============================================================
# COMANDI PRINCIPALI
# ============================================================

cmd_check() {
    log_step "0" "Verifico l'ambiente di sviluppo"
    
    local all_ok=true
    
    # Node.js
    if command -v node &> /dev/null; then
        log_ok "Node.js $(node --version)"
    else
        log_error "Node.js non trovato! Installa con: brew install node"
        all_ok=false
    fi
    
    # Python
    if command -v python3 &> /dev/null; then
        log_ok "Python $(python3 --version 2>&1 | cut -d' ' -f2)"
    else
        log_error "Python3 non trovato! Installa con: brew install python"
        all_ok=false
    fi
    
    # Rust
    if command -v rustc &> /dev/null; then
        log_ok "Rust $(rustc --version | cut -d' ' -f2)"
    else
        log_warn "Rust non trovato. Necessario solo per Tauri desktop app."
    fi
    
    # Ollama
    if command -v ollama &> /dev/null; then
        log_ok "Ollama $(ollama --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
    else
        log_error "Ollama non trovato! Installa con: brew install ollama"
        all_ok=false
    fi
    
    # Git
    if command -v git &> /dev/null; then
        log_ok "Git $(git --version | cut -d' ' -f3)"
    else
        log_error "Git non trovato!"
        all_ok=false
    fi
    
    # VS Code
    if command -v code &> /dev/null; then
        log_ok "VS Code $(code --version 2>/dev/null | head -1)"
    else
        log_warn "VS Code CLI non trovato. Puoi aprirlo manualmente."
    fi
    
    # node_modules
    if [ -d "$PROJECT_DIR/node_modules" ]; then
        log_ok "node_modules presente"
    else
        log_warn "node_modules mancante — installo ora..."
        cd "$PROJECT_DIR" && npm install
        if [ $? -eq 0 ]; then
            log_ok "node_modules installato"
        else
            log_error "Errore installazione npm"
            all_ok=false
        fi
    fi
    
    # LiteLLM
    if python3 -c "import litellm" 2>/dev/null; then
        log_ok "LiteLLM $(python3 -c 'import litellm; print(litellm.__version__)' 2>/dev/null)"
    else
        log_warn "LiteLLM non trovato — installo ora..."
        pip3 install litellm fastapi uvicorn --break-system-packages -q
        log_ok "LiteLLM installato"
    fi
    
    # Modelli Ollama
    local models=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}')
    if [ -n "$models" ]; then
        log_ok "Modelli Ollama disponibili:"
        echo "$models" | while read model; do
            echo "${DIM}        • $model${RESET}"
        done
    else
        log_warn "Nessun modello Ollama. Scarica con: ollama pull qwen2.5-coder:3b"
    fi
    
    echo ""
    if $all_ok; then
        log_ok "${BOLD}Ambiente OK — pronto per l'avvio!${RESET}"
    else
        log_error "Alcuni componenti mancano. Risolvi gli errori sopra."
    fi
}

cmd_start() {
    banner
    cmd_check
    
    cd "$PROJECT_DIR" || { log_error "Cartella progetto non trovata!"; exit 1; }
    
    # STEP 1: Ollama
    log_step "1" "Avvio Ollama (modelli AI locali)"
    if port_in_use $OLLAMA_PORT; then
        log_ok "Ollama già in esecuzione sulla porta $OLLAMA_PORT"
    else
        ollama serve > /dev/null 2>&1 &
        save_pid "ollama" $!
        sleep 2
        if port_in_use $OLLAMA_PORT; then
            log_ok "Ollama avviato (PID: $!)"
        else
            log_warn "Ollama potrebbe richiedere qualche secondo in più..."
        fi
    fi
    
    # STEP 2: Backend
    log_step "2" "Avvio Backend Python (FastAPI porta $BACKEND_PORT)"
    if port_in_use $BACKEND_PORT; then
        log_ok "Backend già in esecuzione sulla porta $BACKEND_PORT"
    else
        PYTHONPATH="$PROJECT_DIR" python3 -m uvicorn backend.api.server:app \
            --reload --host 0.0.0.0 --port $BACKEND_PORT \
            > "$PROJECT_DIR/.pids/backend.log" 2>&1 &
        save_pid "backend" $!
        sleep 3
        if port_in_use $BACKEND_PORT; then
            log_ok "Backend avviato (PID: $!) — http://localhost:$BACKEND_PORT"
        else
            log_error "Backend non avviato. Controlla: cat $PROJECT_DIR/.pids/backend.log"
        fi
    fi
    
    # STEP 3: Frontend
    log_step "3" "Avvio Frontend React (Vite porta $FRONTEND_PORT)"
    if port_in_use $FRONTEND_PORT; then
        log_ok "Frontend già in esecuzione sulla porta $FRONTEND_PORT"
    else
        npx vite --host > "$PROJECT_DIR/.pids/frontend.log" 2>&1 &
        save_pid "frontend" $!
        sleep 3
        if port_in_use $FRONTEND_PORT; then
            log_ok "Frontend avviato (PID: $!) — http://localhost:$FRONTEND_PORT"
        else
            log_error "Frontend non avviato. Controlla: cat $PROJECT_DIR/.pids/frontend.log"
        fi
    fi
    
    # STEP 4: VS Code
    log_step "4" "Apro VS Code sul progetto"
    if command -v code &> /dev/null; then
        code "$PROJECT_DIR"
        log_ok "VS Code aperto"
    else
        log_warn "Apri VS Code manualmente sulla cartella: $PROJECT_DIR"
    fi
    
    # STEP 5: Apri browser
    log_step "5" "Apro l'app nel browser"
    sleep 1
    open "http://localhost:$FRONTEND_PORT"
    log_ok "Browser aperto su http://localhost:$FRONTEND_PORT"
    
    # Riepilogo finale
    echo ""
    echo "${GREEN}╔══════════════════════════════════════════════════╗${RESET}"
    echo "${GREEN}║${RESET}  ${BOLD}🎵 ORCHESTRA PRONTA!${RESET}                             ${GREEN}║${RESET}"
    echo "${GREEN}║${RESET}                                                  ${GREEN}║${RESET}"
    echo "${GREEN}║${RESET}  Frontend:  ${CYAN}http://localhost:$FRONTEND_PORT${RESET}            ${GREEN}║${RESET}"
    echo "${GREEN}║${RESET}  Backend:   ${CYAN}http://localhost:$BACKEND_PORT${RESET}              ${GREEN}║${RESET}"
    echo "${GREEN}║${RESET}  Ollama:    ${CYAN}http://localhost:$OLLAMA_PORT${RESET}             ${GREEN}║${RESET}"
    echo "${GREEN}║${RESET}  Health:    ${CYAN}http://localhost:$BACKEND_PORT/health${RESET}       ${GREEN}║${RESET}"
    echo "${GREEN}║${RESET}                                                  ${GREEN}║${RESET}"
    echo "${GREEN}║${RESET}  ${DIM}Per fermare tutto: ./orchestra.sh stop${RESET}          ${GREEN}║${RESET}"
    echo "${GREEN}╚══════════════════════════════════════════════════╝${RESET}"
    echo ""
}

cmd_dev() {
    banner
    cd "$PROJECT_DIR" || exit 1
    log_step "1" "Avvio solo Frontend (npm run dev)"
    echo "${DIM}  Premi Ctrl+C per fermare${RESET}"
    echo ""
    npm run dev
}

cmd_backend() {
    banner
    cd "$PROJECT_DIR" || exit 1
    log_step "1" "Avvio solo Backend (FastAPI)"
    echo "${DIM}  Premi Ctrl+C per fermare${RESET}"
    echo ""
    PYTHONPATH="$PROJECT_DIR" python3 -m uvicorn backend.api.server:app \
        --reload --host 0.0.0.0 --port $BACKEND_PORT
}

cmd_build() {
    banner
    cd "$PROJECT_DIR" || exit 1
    
    log_step "1" "TypeScript check"
    npx tsc --noEmit
    if [ $? -eq 0 ]; then
        log_ok "TypeScript: nessun errore"
    else
        log_error "TypeScript: trovati errori! Correggili prima del build."
        exit 1
    fi
    
    log_step "2" "Vite build (produzione)"
    npx vite build
    if [ $? -eq 0 ]; then
        log_ok "Build completato! Output in ./dist/"
        echo ""
        ls -lh dist/assets/ 2>/dev/null
    else
        log_error "Build fallito!"
        exit 1
    fi
}

cmd_stop() {
    banner
    log_step "1" "Fermo tutti i servizi VIO 83"
    
    # Ferma frontend
    local frontend_pid=$(get_pid "frontend")
    if [ -n "$frontend_pid" ] && kill -0 "$frontend_pid" 2>/dev/null; then
        kill "$frontend_pid" 2>/dev/null
        log_ok "Frontend fermato (PID: $frontend_pid)"
    fi
    
    # Ferma backend
    local backend_pid=$(get_pid "backend")
    if [ -n "$backend_pid" ] && kill -0 "$backend_pid" 2>/dev/null; then
        kill "$backend_pid" 2>/dev/null
        log_ok "Backend fermato (PID: $backend_pid)"
    fi
    
    # Ferma ollama (opzionale — potrebbe servire ad altro)
    local ollama_pid=$(get_pid "ollama")
    if [ -n "$ollama_pid" ] && kill -0 "$ollama_pid" 2>/dev/null; then
        kill "$ollama_pid" 2>/dev/null
        log_ok "Ollama fermato (PID: $ollama_pid)"
    fi
    
    # Pulizia PID files
    rm -f "$PID_DIR"/*.pid 2>/dev/null
    
    # Kill su porte se ancora occupate
    lsof -ti :$FRONTEND_PORT 2>/dev/null | xargs kill -9 2>/dev/null
    lsof -ti :$BACKEND_PORT 2>/dev/null | xargs kill -9 2>/dev/null
    
    log_ok "Tutti i servizi fermati"
    echo ""
}

cmd_status() {
    banner
    echo "${BOLD}  Stato dei servizi:${RESET}"
    echo ""
    
    # Frontend
    if port_in_use $FRONTEND_PORT; then
        local fpid=$(lsof -ti :$FRONTEND_PORT 2>/dev/null | head -1)
        echo "  ${GREEN}●${RESET} Frontend (Vite)    ${GREEN}ATTIVO${RESET}  porta $FRONTEND_PORT  PID: $fpid"
    else
        echo "  ${RED}○${RESET} Frontend (Vite)    ${RED}FERMO${RESET}"
    fi
    
    # Backend
    if port_in_use $BACKEND_PORT; then
        local bpid=$(lsof -ti :$BACKEND_PORT 2>/dev/null | head -1)
        echo "  ${GREEN}●${RESET} Backend (FastAPI)  ${GREEN}ATTIVO${RESET}  porta $BACKEND_PORT   PID: $bpid"
    else
        echo "  ${RED}○${RESET} Backend (FastAPI)  ${RED}FERMO${RESET}"
    fi
    
    # Ollama
    if port_in_use $OLLAMA_PORT; then
        local opid=$(lsof -ti :$OLLAMA_PORT 2>/dev/null | head -1)
        echo "  ${GREEN}●${RESET} Ollama             ${GREEN}ATTIVO${RESET}  porta $OLLAMA_PORT  PID: $opid"
        echo ""
        echo "  ${DIM}Modelli installati:${RESET}"
        ollama list 2>/dev/null | tail -n +2 | awk '{printf "     • %s (%s)\n", $1, $3}'
    else
        echo "  ${RED}○${RESET} Ollama             ${RED}FERMO${RESET}"
    fi
    
    echo ""
}

cmd_test() {
    banner
    cd "$PROJECT_DIR" || exit 1
    
    log_step "1" "TypeScript check"
    npx tsc --noEmit
    [ $? -eq 0 ] && log_ok "TypeScript OK" || log_error "TypeScript ERRORI"
    
    log_step "2" "Build test"
    npx vite build > /dev/null 2>&1
    [ $? -eq 0 ] && log_ok "Build OK" || log_error "Build FALLITO"
    
    log_step "3" "Backend health check"
    if port_in_use $BACKEND_PORT; then
        local health=$(curl -s http://localhost:$BACKEND_PORT/health 2>/dev/null)
        if echo "$health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])" 2>/dev/null | grep -q "ok"; then
            log_ok "Backend health: OK"
        else
            log_warn "Backend risponde ma status non OK"
        fi
    else
        log_warn "Backend non in esecuzione — skip health check"
    fi
    
    log_step "4" "Ollama check"
    if port_in_use $OLLAMA_PORT; then
        local model_count=$(ollama list 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')
        log_ok "Ollama attivo con $model_count modelli"
    else
        log_warn "Ollama non in esecuzione"
    fi
    
    echo ""
    log_ok "${BOLD}Test completati!${RESET}"
    echo ""
}

cmd_open() {
    banner
    if command -v code &> /dev/null; then
        code "$PROJECT_DIR"
        log_ok "VS Code aperto su $PROJECT_DIR"
    else
        log_error "Comando 'code' non trovato. Apri VS Code manualmente."
    fi
}

cmd_help() {
    banner
    echo "  ${BOLD}Comandi disponibili:${RESET}"
    echo ""
    echo "  ${GREEN}./orchestra.sh${RESET}          Avvia TUTTO (Ollama + Backend + Frontend + VS Code + Browser)"
    echo "  ${GREEN}./orchestra.sh start${RESET}    Come sopra"
    echo "  ${GREEN}./orchestra.sh dev${RESET}      Avvia solo il frontend React (npm run dev)"
    echo "  ${GREEN}./orchestra.sh backend${RESET}  Avvia solo il backend Python FastAPI"
    echo "  ${GREEN}./orchestra.sh build${RESET}    Build di produzione (TypeScript check + Vite build)"
    echo "  ${GREEN}./orchestra.sh stop${RESET}     Ferma tutti i servizi"
    echo "  ${GREEN}./orchestra.sh status${RESET}   Mostra cosa è in esecuzione"
    echo "  ${GREEN}./orchestra.sh test${RESET}     Esegui tutti i test e verifiche"
    echo "  ${GREEN}./orchestra.sh open${RESET}     Apri solo VS Code sul progetto"
    echo "  ${GREEN}./orchestra.sh help${RESET}     Mostra questo aiuto"
    echo ""
    echo "  ${DIM}Scorciatoia rapida (dopo aver aggiunto l'alias):${RESET}"
    echo "  ${CYAN}vio${RESET}                    Avvia tutto con un comando!"
    echo "  ${CYAN}vio stop${RESET}               Ferma tutto"
    echo "  ${CYAN}vio status${RESET}             Controlla lo stato"
    echo ""
}

# ============================================================
# ROUTER COMANDI
# ============================================================

case "${1:-start}" in
    start)    cmd_start ;;
    dev)      cmd_dev ;;
    backend)  cmd_backend ;;
    build)    cmd_build ;;
    stop)     cmd_stop ;;
    status)   cmd_status ;;
    test)     cmd_test ;;
    open)     cmd_open ;;
    help|-h)  cmd_help ;;
    *)
        log_error "Comando sconosciuto: $1"
        cmd_help
        exit 1
        ;;
esac
