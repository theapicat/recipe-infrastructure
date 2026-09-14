#!/usr/bin/env bash
# Starter Recipe-utviklingsmiljøet: Docker-infrastruktur + valgte mikrotjenester.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

usage() {
    cat <<EOF
Bruk: $(basename "$0") [tjeneste ...] [--no-infra]

Uten argumenter startes hele stacken (Docker-infrastruktur + alle mikrotjenester).
Du kan oppgi én eller flere tjenester for å starte et delsett, f.eks:
  $(basename "$0") auth-api notification-service

Gyldige tjenester: ${SERVICE_ORDER[*]}

Flagg:
  --no-infra   Ikke kjør "docker compose up -d" (anta at infrastrukturen allerede kjører)
  -h, --help   Vis denne hjelpeteksten
EOF
}

RUN_INFRA=true
SELECTED=()

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            usage
            exit 0
            ;;
        --no-infra)
            RUN_INFRA=false
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
log_info "   🚀 Starter Recipe Utviklingsmiljø"
log_info "===================================================="

# ---------------------------------------------------------------------------
# 1. Docker-infrastruktur
# ---------------------------------------------------------------------------
if [ "$RUN_INFRA" = true ]; then
    echo -e "\n🐳 [1/3] Starter infrastruktur (Docker Compose)..."
    if ! (cd "$INFRA_DIR" && docker compose up -d); then
        log_error "Klarte ikke starte docker compose i $INFRA_DIR"
        exit 1
    fi

    for c in recipe-auth-db recipe-core-db; do
        printf "   Venter på %s..." "$c"
        if wait_for_container_health "$c" 45; then
            echo -e " ${GREEN}klar${NC}"
        else
            echo -e " ${YELLOW}tidsavbrudd, fortsetter likevel${NC}"
        fi
    done

    printf "   Venter på recipe-message-broker (port %s)..." "${RABBITMQ_PORT:-5672}"
    if wait_for_port localhost "${RABBITMQ_PORT:-5672}" 20; then
        echo -e " ${GREEN}klar${NC}"
    else
        echo -e " ${YELLOW}tidsavbrudd${NC}"
    fi

    printf "   Venter på recipe-mongo-db (port %s)..." "${MONGO_PORT:-27017}"
    if wait_for_port localhost "${MONGO_PORT:-27017}" 20; then
        echo -e " ${GREEN}klar${NC}"
    else
        echo -e " ${YELLOW}tidsavbrudd${NC}"
    fi
else
    echo -e "\n🐳 [1/3] Hopper over infrastruktur (--no-infra)"
fi

# ---------------------------------------------------------------------------
# 2. Mikrotjenester
# ---------------------------------------------------------------------------
echo -e "\n🔥 [2/3] Starter ${#SELECTED[@]} tjeneste(r)..."

TERM_EMU="$(detect_terminal)"
if [ -z "$TERM_EMU" ]; then
    log_warn "   Fant ingen støttet terminalemulator - starter i bakgrunnen med logger under dev-scripts/.run/logs/"
fi
mkdir -p "$RUN_DIR/logs"

for svc in "${SELECTED[@]}"; do
    dir="${SERVICE_DIR[$svc]}"
    cmd="${SERVICE_CMD[$svc]}"
    title="${SERVICE_TITLE[$svc]}"
    pidfile=$(pidfile_for "$svc")

    if service_is_running "$svc"; then
        log_warn "   ⏭  $title kjører allerede (PID $(cat "$pidfile")), hopper over"
        continue
    fi
    if [ ! -d "$dir" ]; then
        log_warn "   ⏭  $title: mappa finnes ikke ennå ($dir), hopper over"
        continue
    fi

    if [ -n "$TERM_EMU" ]; then
        inner=$(build_service_inner "$svc")
        launch_in_terminal "$TERM_EMU" "$title" "$dir" "$inner"
        echo -e "   ${GREEN}✔${NC} $title"
    else
        logfile="$RUN_DIR/logs/$svc.log"
        # setsid gir prosessen sin egen sesjon/gruppe, uavhengig av dette
        # skriptets egen gruppe - trygt å gruppe-drepe senere uten å risikere
        # å treffe start-project.sh selv eller andre bakgrunnslagte tjenester.
        (
            cd "$dir" || exit 1
            export PATH="$PATH"
            if command -v setsid &>/dev/null; then
                setsid $cmd >"$logfile" 2>&1 &
            else
                $cmd >"$logfile" 2>&1 &
            fi
            echo $! > "$pidfile"
        )
        echo -e "   ${GREEN}✔${NC} $title (bakgrunn, logg: $logfile)"
    fi
done

# ---------------------------------------------------------------------------
# 3. Helsesjekk
# ---------------------------------------------------------------------------
echo -e "\n🏥 [3/3] Utfører helsesjekk på HTTP-tjenester..."

CHECK_KEYS=()
[ "$RUN_INFRA" = true ] && CHECK_KEYS+=(seq mailpit)
for svc in "${SELECTED[@]}"; do
    [ -n "${HEALTH_URL[$svc]:-}" ] && CHECK_KEYS+=("$svc")
done

for key in "${HEALTH_ORDER[@]}"; do
    if [ ${#CHECK_KEYS[@]} -gt 0 ] && contains "$key" "${CHECK_KEYS[@]}"; then
        check_health "${HEALTH_LABEL[$key]}" "${HEALTH_URL[$key]}" 20 1
    fi
done

echo -e "\n===================================================="
log_ok "🎉 Alt er oppe og nikker!"
echo -e "===================================================="
