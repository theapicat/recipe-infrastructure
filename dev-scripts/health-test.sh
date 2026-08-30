#!/usr/bin/env bash

# Sørg for at skriptet har kjørerettigheter
chmod +x "$0" 2>/dev/null

# Farger for konsollutskrift
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}   🏥 Utfører Helsesjekk på Kjøkkenhylla         ${NC}"
echo -e "${CYAN}====================================================${NC}\n"

declare -A SERVICES=(
    ["Seq Log Dashboard"]="http://localhost:5341"
    ["recipe-authentication-api"]="http://localhost:5001/api/auth/health"
    ["recipe-core-api"]="http://localhost:5002/api/public/health"
    ["recipe-scraper-api"]="http://localhost:5003/api/scraper/health"
    ["recipe-gateway-api"]="http://localhost:5000/api/gateway/health"
    ["recipe-webapp"]="http://localhost:3000/api/health"
)

all_healthy=true

check_health() {
    local name=$1
    local url=$2
    local max_retries=2
    local count=0

    while [ $count -lt $max_retries ]; do
        http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "$url")

        if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 304 ]; then
            printf "   [${GREEN}OK${NC}]   %-28s (HTTP %s)\n" "$name" "$http_code"
            return 0
        fi

        sleep 0.5
        ((count++))
    done

    printf "   [${RED}FEIL${NC}] %-28s (Status: %s)\n" "$name" "$http_code"
    all_healthy=false
    return 1
}

# Kjøre helsesjekkene i definert rekkefølge
check_health "Seq Log Dashboard" "${SERVICES["Seq Log Dashboard"]}"
check_health "recipe-authentication-api" "${SERVICES["recipe-authentication-api"]}"
check_health "recipe-core-api" "${SERVICES["recipe-core-api"]}"
check_health "recipe-scraper-api" "${SERVICES["recipe-scraper-api"]}"
check_health "recipe-gateway-api" "${SERVICES["recipe-gateway-api"]}"
check_health "recipe-webapp" "${SERVICES["recipe-webapp"]}"

echo -e "\n${CYAN}====================================================${NC}"
if [ "$all_healthy" = true ]; then
    echo -e "${GREEN}🎉 Alle tjenester er oppe og nikker!${NC}"
else
    echo -e "${RED}⚠️ En eller flere tjenester svarte ikke korrekt.${NC}"
fi
echo -e "${CYAN}====================================================${NC}"