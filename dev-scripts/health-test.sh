#!/usr/bin/env bash
# Rask helsesjekk av alle HTTP-baserte tjenester og dashboards. Antar at
# infrastruktur/tjenester allerede kjører - se start-project.sh for oppstart.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

log_info "===================================================="
log_info "   🏥 Utfører Helsesjekk på Recipe Applikasjonen"
log_info "===================================================="
echo

all_healthy=true
for key in "${HEALTH_ORDER[@]}"; do
    check_health "${HEALTH_LABEL[$key]}" "${HEALTH_URL[$key]}" 2 0.5 || all_healthy=false
done

echo
log_info "===================================================="
if [ "$all_healthy" = true ]; then
    log_ok "🎉 Alle HTTP-tjenester og dashboards er oppe og nikker!"
else
    log_warn "⚠️  En eller flere tjenester svarte ikke korrekt."
fi
log_info "===================================================="
