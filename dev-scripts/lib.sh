#!/usr/bin/env bash
# Delt bibliotek for dev-scripts (start-project.sh, stop-project.sh, health-test.sh).
# Ikke ment for direkte kjøring - kildes inn av de tre andre skriptene.

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "lib.sh er et bibliotek ment for 'source'-bruk, ikke direkte kjøring." >&2
    echo "Bruk start-project.sh, stop-project.sh eller health-test.sh i stedet." >&2
    exit 1
fi

set -uo pipefail

# ---------------------------------------------------------------------------
# Farger og loggehjelpere
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}$*${NC}"; }
log_ok()    { echo -e "${GREEN}$*${NC}"; }
log_warn()  { echo -e "${YELLOW}$*${NC}"; }
log_error() { echo -e "${RED}$*${NC}" >&2; }

# ---------------------------------------------------------------------------
# Stier
# ---------------------------------------------------------------------------
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$LIB_DIR/.." && pwd)"
ROOT_DIR="$(cd "$INFRA_DIR/.." && pwd)"
RUN_DIR="$LIB_DIR/.run"
mkdir -p "$RUN_DIR"

# Gjør DB/broker/Seq/Mailpit-porter tilgjengelige (SEQ_PORT, RABBITMQ_PORT, m.fl.)
if [ -f "$INFRA_DIR/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$INFRA_DIR/.env"
    set +a
fi

# ---------------------------------------------------------------------------
# Tjenestedefinisjoner
# Bash associative arrays har ingen garantert rekkefølge - SERVICE_ORDER er
# derfor fasiten for iterasjonsrekkefølge i alle skript.
# ---------------------------------------------------------------------------
SERVICE_ORDER=(gateway-api auth-api core-api notification-service scraper-service webapp)

declare -A SERVICE_DIR=(
    [gateway-api]="$ROOT_DIR/recipe-gateway-api/API"
    [auth-api]="$ROOT_DIR/recipe-auth-api/API"
    [core-api]="$ROOT_DIR/recipe-core-api/API"
    [notification-service]="$ROOT_DIR/recipe-notification-service/Service"
    [scraper-service]="$ROOT_DIR/recipe-scraper-service/Service"
    [webapp]="$ROOT_DIR/recipe-webapp"
)

declare -A SERVICE_CMD=(
    [gateway-api]="dotnet watch"
    [auth-api]="dotnet watch"
    [core-api]="dotnet watch"
    [notification-service]="dotnet watch"
    [scraper-service]="dotnet watch"
    [webapp]="npm run dev"
)

declare -A SERVICE_TITLE=(
    [gateway-api]="Gateway API (5000)"
    [auth-api]="Auth API (5001)"
    [core-api]="Core API (5002)"
    [notification-service]="Notification Service"
    [scraper-service]="Scraper Service"
    [webapp]="Web App (3000)"
)

# Kun tjenester med et faktisk HTTP-endepunkt kan helsesjekkes.
# notification-service og scraper-service eksponerer ingen HTTP - de lytter
# kun på RabbitMQ, se deres respektive README/CLAUDE.md.
HEALTH_ORDER=(seq mailpit gateway-api auth-api core-api webapp)

declare -A HEALTH_URL=(
    [seq]="http://localhost:${SEQ_PORT:-5341}"
    [mailpit]="http://localhost:${MAILPIT_UI_PORT:-8025}"
    [gateway-api]="http://localhost:5000/api/gateway/health"
    [auth-api]="http://localhost:5001/api/auth/health"
    [core-api]="http://localhost:5002/api/public/health"
    [webapp]="http://localhost:3000/api/health"
)

declare -A HEALTH_LABEL=(
    [seq]="Seq Log Dashboard"
    [mailpit]="Mailpit Web UI"
    [gateway-api]="recipe-gateway-api"
    [auth-api]="recipe-auth-api"
    [core-api]="recipe-core-api"
    [webapp]="recipe-webapp"
)

# ---------------------------------------------------------------------------
# Småhjelpere
# ---------------------------------------------------------------------------

# contains <needle> <hay...> - sjekk om needle finnes blant de øvrige argumentene
contains() {
    local needle=$1
    shift
    local x
    for x in "$@"; do
        [ "$x" = "$needle" ] && return 0
    done
    return 1
}

# ---------------------------------------------------------------------------
# PID-sporing (dev-scripts/.run/<tjeneste>.pid)
# ---------------------------------------------------------------------------
pidfile_for() { echo "$RUN_DIR/$1.pid"; }

service_is_running() {
    local pidfile
    pidfile=$(pidfile_for "$1")
    [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Terminalemulator-deteksjon og -oppstart
# ---------------------------------------------------------------------------

# Bevisst UTEN "x-terminal-emulator": det er et system-alias som kan peke på
# hva som helst (xterm, gnome-terminal, ...) med ukjent CLI-syntaks - trygghet
# fremfor gjetning.
detect_terminal() {
    local term
    for term in gnome-terminal tilix konsole xfce4-terminal kitty alacritty xterm; do
        if command -v "$term" &>/dev/null; then
            echo "$term"
            return 0
        fi
    done
    return 1
}

# build_service_inner <tjeneste>
# Bygger kommandostrengen som kjøres inni terminalvinduet. Bevisst i samme
# stil som det opprinnelige (Gemini-skrevne) skriptet, som fungerte pålitelig:
# ren "cd && ... && $cmd; exec bash" - INGEN bakgrunnslegging, INGEN
# jobbkontroll. Det eneste nye er:
#   - "export PATH=..." fremst, slik at en fersk terminal-shell (som ikke
#     leser ~/.bashrc) uansett finner dotnet/npm.
#   - "echo $$ > pidfile" rett før $cmd. Siden det ikke brukes jobbkontroll,
#     havner $cmd i SAMME prosessgruppe som denne shell-en (bash sin vanlige
#     oppførsel for en forgrunnskommando) - så gruppens PID (som er lik denne
#     shell-ens PID) er nok til at stop-project.sh kan stoppe $cmd rent.
# "; exec bash" på slutten er uendret fra originalen: vinduet blir alltid
# stående som en vanlig, brukbar shell når $cmd avslutter - krasj eller ikke.
build_service_inner() {
    local svc=$1
    local dir="${SERVICE_DIR[$svc]}" cmd="${SERVICE_CMD[$svc]}" title="${SERVICE_TITLE[$svc]}"
    local pidfile
    pidfile=$(pidfile_for "$svc")
    echo "export PATH='$PATH'; cd '$dir' && echo \$\$ > '$pidfile' && echo -e '${CYAN}=== $title ===${NC}\n' && $cmd; exec bash"
}

# launch_in_terminal <emulator> <title> <workdir> <inner_kommando>
launch_in_terminal() {
    local term=$1 title=$2 workdir=$3 inner=$4
    case "$term" in
        gnome-terminal|tilix)
            "$term" --title="$title" -- bash -c "$inner" &>/dev/null &
            ;;
        konsole)
            konsole -p tabtitle="$title" --workdir "$workdir" -e bash -c "$inner" &>/dev/null &
            ;;
        xfce4-terminal)
            xfce4-terminal --title="$title" --working-directory="$workdir" -x bash -c "$inner" &>/dev/null &
            ;;
        kitty)
            kitty --title "$title" --directory "$workdir" bash -c "$inner" &>/dev/null &
            ;;
        alacritty)
            alacritty --title "$title" --working-directory "$workdir" -e bash -c "$inner" &>/dev/null &
            ;;
        xterm)
            xterm -title "$title" -e bash -c "$inner" &>/dev/null &
            ;;
        *)
            return 1
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Ventehjelpere for infrastruktur
# ---------------------------------------------------------------------------

# wait_for_port <host> <port> <timeout_sekunder>
wait_for_port() {
    local host=$1 port=$2 timeout=$3 waited=0
    while true; do
        if (exec 3<>"/dev/tcp/$host/$port") 2>/dev/null; then
            return 0
        fi
        waited=$((waited + 1))
        [ "$waited" -ge "$timeout" ] && return 1
        sleep 1
    done
}

# wait_for_container_health <container_navn> <timeout_sekunder>
# For containere uten definert HEALTHCHECK i docker-compose.yaml (mongo,
# rabbitmq) - bruk wait_for_port i stedet.
wait_for_container_health() {
    local container=$1 timeout=$2 waited=0 status
    while [ "$waited" -lt "$timeout" ]; do
        status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "unknown")
        [ "$status" = "healthy" ] && return 0
        sleep 1
        waited=$((waited + 1))
    done
    return 1
}

# ---------------------------------------------------------------------------
# HTTP-helsesjekk
# check_health <label> <url> <maks_forsøk> <delay_sekunder>
# ---------------------------------------------------------------------------
check_health() {
    local label=$1 url=$2 max_retries=$3 delay=$4
    local count=0 http_code="000"

    while [ "$count" -lt "$max_retries" ]; do
        http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "$url" 2>/dev/null)
        if [ "$http_code" = "200" ] || [ "$http_code" = "304" ]; then
            printf "   [${GREEN}OK${NC}]   %-28s (HTTP %s)\n" "$label" "$http_code"
            return 0
        fi
        sleep "$delay"
        count=$((count + 1))
    done

    printf "   [${RED}FEIL${NC}] %-28s (Status: %s)\n" "$label" "$http_code"
    return 1
}
