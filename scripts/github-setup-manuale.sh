#!/bin/zsh
# ============================================================
# 🎵 VIO 83 — Azioni GitHub da completare nel browser
# Esegui questo script: apre tutte le pagine necessarie
# ============================================================

GREEN='\033[0;32m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

echo ""
echo "${GREEN}╔══════════════════════════════════════════════════╗${RESET}"
echo "${GREEN}║${RESET}  ${MAGENTA}🎵${RESET}  ${BOLD}VIO 83 — GitHub Setup Guidato${RESET}               ${GREEN}║${RESET}"
echo "${GREEN}╚══════════════════════════════════════════════════╝${RESET}"
echo ""

# ============================================================
# STEP 1: Aggiorna profilo GitHub
# ============================================================
echo "${MAGENTA}━━━ STEP 1: Aggiorna il tuo profilo GitHub ━━━${RESET}"
echo ""
echo "  Apro la pagina delle impostazioni profilo..."
echo ""
echo "  ${BOLD}Quando si apre, aggiorna questi campi:${RESET}"
echo "  ${CYAN}• Name:${RESET}     Viorica | VIO 83 AI Creator"
echo "  ${CYAN}• Bio:${RESET}      🚀 Visionary AI Creator | Building VIO 83 AI Orchestra"
echo "  ${CYAN}• URL:${RESET}      https://github.com/vio83/vio83-ai-orchestra"
echo "  ${CYAN}• Location:${RESET} Sardinia, Italy 🇮🇹"
echo ""
echo "  Poi clicca ${GREEN}Update profile${RESET}"
echo ""
read "?  Premi INVIO per aprire la pagina → "
open "https://github.com/settings/profile"
echo ""

# ============================================================
# STEP 2: Pin i repository sul profilo
# ============================================================
echo "${MAGENTA}━━━ STEP 2: Pin i repository importanti ━━━${RESET}"
echo ""
echo "  Apro il tuo profilo GitHub..."
echo ""
echo "  ${BOLD}Quando si apre:${RESET}"
echo "  1. Scorri giù fino a ${CYAN}Pinned repositories${RESET}"
echo "  2. Clicca ${CYAN}Customize your pins${RESET}"
echo "  3. Seleziona questi repo:"
echo "     ${GREEN}✓ vio83-ai-orchestra${RESET}  (il progetto principale)"
echo "     ${GREEN}✓ ai-scripts-elite${RESET}     (il monitor Mac)"
echo "     ${GREEN}✓ vio83${RESET}                (il tuo profile README)"
echo "  4. Clicca ${GREEN}Save pins${RESET}"
echo ""
read "?  Premi INVIO per aprire la pagina → "
open "https://github.com/vio83"
echo ""

# ============================================================
# STEP 3: Attiva GitHub Sponsors
# ============================================================
echo "${MAGENTA}━━━ STEP 3: Attiva GitHub Sponsors ━━━${RESET}"
echo ""
echo "  Apro la pagina GitHub Sponsors..."
echo ""
echo "  ${BOLD}Quando si apre:${RESET}"
echo "  1. Clicca ${CYAN}Get started${RESET} o ${CYAN}Set up GitHub Sponsors${RESET}"
echo "  2. Segui la procedura guidata:"
echo "     • ${CYAN}Region:${RESET} Italy"
echo "     • ${CYAN}Bank:${RESET} Inserisci i tuoi dati bancari (IBAN)"
echo "     • ${CYAN}Tiers:${RESET} Crea queste fasce:"
echo "       ${GREEN}\$3/mese${RESET}  — Coffee Supporter"
echo "       ${GREEN}\$10/mese${RESET} — Orchestra Musician"
echo "       ${GREEN}\$25/mese${RESET} — Conductor"
echo "       ${GREEN}\$100/mese${RESET} — Patron"
echo "  3. Clicca ${GREEN}Submit for review${RESET}"
echo ""
echo "  ${DIM}Nota: GitHub impiega 1-7 giorni per approvare.${RESET}"
echo "  ${DIM}Il file FUNDING.yml è già nel tuo repo.${RESET}"
echo ""
read "?  Premi INVIO per aprire la pagina → "
open "https://github.com/sponsors/vio83/dashboard"
echo ""

# ============================================================
# STEP 4: Crea pagina Ko-fi
# ============================================================
echo "${MAGENTA}━━━ STEP 4: Crea/Aggiorna pagina Ko-fi ━━━${RESET}"
echo ""
echo "  Apro Ko-fi..."
echo ""
echo "  ${BOLD}Quando si apre:${RESET}"
echo "  1. Crea account con username ${CYAN}vio83${RESET} (se non esiste)"
echo "  2. Copia il contenuto da questo file:"
echo "     ${CYAN}/Users/padronavio/Projects/vio83-ai-orchestra/docs/KOFI_PAGE_CONTENT.md${RESET}"
echo "  3. Imposta i tier di donazione:"
echo "     ${GREEN}€3${RESET} — Coffee"
echo "     ${GREEN}€10${RESET} — Support the Orchestra"
echo "     ${GREEN}€25${RESET} — Conductor"
echo "     ${GREEN}€50${RESET} — Patron"
echo ""
read "?  Premi INVIO per aprire la pagina → "
open "https://ko-fi.com/manage"
echo ""

# ============================================================
# STEP 5: Aggiorna token GitHub con scope 'user'
# ============================================================
echo "${MAGENTA}━━━ STEP 5 (Opzionale): Aggiorna permessi token ━━━${RESET}"
echo ""
echo "  ${BOLD}Per permettere a Claude di aggiornare il tuo profilo in futuro:${RESET}"
echo "  1. Vai su GitHub → Settings → Developer settings → Personal access tokens"
echo "  2. Trova il token usato da ${CYAN}gh cli${RESET}"
echo "  3. Aggiungi lo scope ${CYAN}user${RESET}"
echo ""
read "?  Premi INVIO per aprire la pagina (o Ctrl+C per saltare) → "
open "https://github.com/settings/tokens"
echo ""

# ============================================================
# FINE
# ============================================================
echo "${GREEN}╔══════════════════════════════════════════════════╗${RESET}"
echo "${GREEN}║${RESET}  ${BOLD}✅ Setup completato!${RESET}                            ${GREEN}║${RESET}"
echo "${GREEN}║${RESET}                                                  ${GREEN}║${RESET}"
echo "${GREEN}║${RESET}  Il tuo profilo GitHub ora mostra:               ${GREEN}║${RESET}"
echo "${GREEN}║${RESET}  • Profile README personalizzato                 ${GREEN}║${RESET}"
echo "${GREEN}║${RESET}  • Repository pinnati                            ${GREEN}║${RESET}"
echo "${GREEN}║${RESET}  • Pulsante Sponsor (dopo approvazione)          ${GREEN}║${RESET}"
echo "${GREEN}║${RESET}  • 15 topics su vio83-ai-orchestra               ${GREEN}║${RESET}"
echo "${GREEN}║${RESET}  • Description professionale su tutti i repo     ${GREEN}║${RESET}"
echo "${GREEN}╚══════════════════════════════════════════════════╝${RESET}"
echo ""
