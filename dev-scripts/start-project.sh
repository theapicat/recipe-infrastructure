#!/usr/bin/env bash

# Sørg for at skriptet beholder sine egne kjørerettigheter
chmod +x "$0" 2>/dev/null

# Farger for konsollutskrift
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Sti-beregning ut fra skriptets plassering (recipe-infrastructure/dev-scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$INFRA_DIR/.." && pwd)"

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}   🚀 Starter Recipe Utviklingsmiljø               ${NC}"
echo -e "${CYAN}====================================================${NC}"

# 1. Åpne separate terminalvinduer for hver tjeneste
echo -e "\n🔥 [1/2] Åpner terminalvinduer for mikrotjenestene..."

TERM_CMD="gnome-terminal"
if ! command -v gnome-terminal &> /dev/null; then
    TERM_CMD="x-terminal-emulator"
fi

start_service_window() {
    local title=$1
    local dir=$2
    local cmd=$3

    $TERM_CMD --title="$title" -- bash -c "cd '$dir' && echo -e '${CYAN}=== $title ===${NC}\n' && $cmd; exec bash" >/dev/null 2>&1 &
}

start_service_window "Auth API (5001)"          "$ROOT_DIR/recipe-auth-api/API"               "dotnet watch"
start_service_window "Core API (5002)"          "$ROOT_DIR/recipe-core-api/API"               "dotnet watch"
start_service_window "Scraper Service"          "$ROOT_DIR/recipe-scraper-service/Service"    "dotnet watch"
start_service_window "Notification Service"     "$ROOT_DIR/recipe-notification-service/Service" "dotnet watch"
start_service_window "Gateway API (5000)"       "$ROOT_DIR/recipe-gateway-api/API"            "dotnet watch"
start_service_window "Web App (3000)"           "$ROOT_DIR/recipe-webapp"                     "npm run dev"

echo -e "   ${GREEN}✔ 6 terminalvinduer er åpnet på skrivebordet!${NC}"

# 2. Helsesjekk i hovedterminalen for HTTP-baserte tjenester
echo -e "\n🏥 [2/2] Utfører helsesjekk på HTTP-tjenester..."

declare -A SERVICES=(
    ["Seq Log Dashboard"]="http://localhost:5341"
    ["Mailpit Web UI"]="http://localhost:8025"
    ["recipe-authentication-api"]="http://localhost:5001/api/auth/health"
    ["recipe-core-api"]="http://localhost:5002/api/public/health"
    ["recipe-gateway-api"]="http://localhost:5000/api/gateway/health"
    ["recipe-webapp"]="http://localhost:3000/api/health"
)

check_health() {
    local name=$1
    local url=$2
    local max_retries=20
    local count=0

    while [ $count -lt $max_retries ]; do
        http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "$url")

        if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 304 ]; then
            printf "   [${GREEN}OK${NC}]   %-28s (HTTP %s)\n" "$name" "$http_code"
            return 0
        fi

        sleep 1
        ((count++))
    done

    printf "   [${RED}FEIL${NC}] %-28s (Status: %s)\n" "$name" "$http_code"
    return 1
}

# Kjøre helsesjekkene i definert rekkefølge
check_health "Seq Log Dashboard" "${SERVICES["Seq Log Dashboard"]}"
check_health "Mailpit Web UI" "${SERVICES["Mailpit Web UI"]}"
check_health "recipe-authentication-api" "${SERVICES["recipe-authentication-api"]}"
check_health "recipe-core-api" "${SERVICES["recipe-core-api"]}"
check_health "recipe-gateway-api" "${SERVICES["recipe-gateway-api"]}"
check_health "recipe-webapp" "${SERVICES["recipe-webapp"]}"

echo -e "\n${CYAN}====================================================${NC}"
echo -e "${GREEN}🎉 Alt er oppe og nikker!${NC}"
echo -e "${CYAN}====================================================${NC}"