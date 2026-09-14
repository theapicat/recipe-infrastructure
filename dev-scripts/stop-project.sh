#!/usr/bin/env bash
# Stopper mikrotjenester startet av start-project.sh, sporet via dev-scripts/.run/*.pid.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

usage() {
    cat <<EOF
Bruk: $(basename "$0") [tjeneste ...] [--with-infra]

Uten argumenter stoppes alle sporede mikrotjenester (Docker-infrastrukturen lar vi stå).
Du kan oppgi én eller flere tjenester for å stoppe et delsett:
  $(basename "$0") auth-api notification-service

Gyldige tjenester: ${SERVICE_ORDER[*]}

Flagg:
  --with-infra  Kjør også "docker compose down" etter at tjenestene er stoppet
  -h, --help    Vis denne hjelpeteksten
EOF
}

STOP_INFRA=false
SELECTED=()

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            usage
            exit 0
            ;;
        --with-infra)
            STOP_INFRA=true
            ;;
        *)
            if contains "$arg" "${SERVICE_ORDER[@]}"; then
                SELECTED+=("$arg")
            else
                log_error "Ukjent tjeneste: $arg"
                usage
                exit 1
            fi
            ;;
    esac
done
[ ${#SELECTED[@]} -eq 0 ] && SELECTED=("${SERVICE_ORDER[@]}")

log_info "===================================================="
log_info "   🛑 Stopper Recipe Applikasjoner"
log_info "===================================================="
echo

HAVE_WMCTRL=false
command -v wmctrl &>/dev/null && HAVE_WMCTRL=true

stopped_any=false
for svc in "${SELECTED[@]}"; do
    pidfile=$(pidfile_for "$svc")
    title="${SERVICE_TITLE[$svc]}"

    [ -f "$pidfile" ] || continue
    pid=$(cat "$pidfile")

    if kill -0 "$pid" 2>/dev/null; then
        # Send til hele prosessgruppen (negativ PID) - se merknad i lib.sh sin
        # write_runner_script() om "set -m". Fanger opp underprosesser
        # "dotnet watch" o.l. selv spawner.
        kill -TERM -- "-$pid" 2>/dev/null

        # .NET-tjenester med Quartz/MassTransit kan bruke noen sekunder på
        # graceful shutdown (observert i praksis) - gi dem rom før SIGKILL.
        for _ in {1..20}; do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.3
        done

        if kill -0 "$pid" 2>/dev/null; then
            kill -KILL -- "-$pid" 2>/dev/null
        fi

        echo -e "   ${GREEN}✔${NC} $title stoppet"
        stopped_any=true
    fi

    rm -f "$pidfile"
    [ "$HAVE_WMCTRL" = true ] && wmctrl -c "$title" 2>/dev/null
done

if [ "$stopped_any" = false ]; then
    log_warn "   Ingen sporede prosesser å stoppe (glemt å kjøre start-project.sh, eller allerede stoppet?)"
fi

# Sikkerhetsnett: frigjør HTTP-portene i tilfelle noe kjører utenfor PID-sporingen
# (f.eks. startet manuelt med "dotnet watch" i en egen terminal).
PORTS=(5000 5001 5002 3000)
for port in "${PORTS[@]}"; do
    pid=$(lsof -t -i :"$port" 2>/dev/null)
    if [ -n "$pid" ]; then
        kill -9 $pid 2>/dev/null
        log_warn "   Frigjorde port $port (usporet prosess, PID $pid)"
    fi
done

[ "$HAVE_WMCTRL" = false ] && log_warn "   (Installer 'wmctrl' for automatisk lukking av terminalvinduer.)"

if [ "$STOP_INFRA" = true ]; then
    echo -e "\n🐳 Stopper infrastruktur (docker compose down)..."
    (cd "$INFRA_DIR" && docker compose down)
fi

echo
log_info "===================================================="
log_ok "✨ Ryddet og klart!"
log_info "===================================================="
