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
echo -e "${CYAN}   🛑 Stopper Kjøkkenhylla Applikasjoner           ${NC}"
echo -e "${CYAN}====================================================${NC}\n"

echo -e "🧹 Stopper applikasjoner og lukker terminaler..."

# 1. Stopper dotnet watch og node/next-prosesser
pkill -f "dotnet watch" 2>/dev/null
pkill -f "next-dev" 2>/dev/null
pkill -f "recipe-webapp" 2>/dev/null

# 2. Tvinger frigjøring av porter dersom en prosess henger (5000, 5001, 5002, 5003, 3000)
PORTS=(5000 5001 5002 5003 3000)
for port in "${PORTS[@]}"; do
    pid=$(lsof -t -i :"$port" 2>/dev/null)
    if [ -n "$pid" ]; then
        kill -9 $pid 2>/dev/null
    fi
done

# 3. Lukker de åpne terminalvinduene basert på tittelen
pkill -f "Auth API \(5001\)" 2>/dev/null
pkill -f "Core API \(5002\)" 2>/dev/null
pkill -f "Scraper API \(5003\)" 2>/dev/null
pkill -f "Gateway API \(5000\)" 2>/dev/null
pkill -f "Web App \(3000\)" 2>/dev/null

echo -e "   ${GREEN}✔ Alle 5 mikrotjenester er stoppet og terminalene er lukket!${NC}"

echo -e "\n${CYAN}====================================================${NC}"
echo -e "${GREEN}✨ Ryddet og klart!${NC}"
echo -e "${CYAN}====================================================${NC}"