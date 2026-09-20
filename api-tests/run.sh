#!/usr/bin/env bash
# Inngangspunkt for API-testene (pytest). Kjør denne fra hvor som helst.
#
#   ./run.sh                 # alle tester via gatewayen (:5000)
#   ./run.sh --direct        # gå rett mot Auth (:5001) og Core (:5002), uten om gatewayen
#   ./run.sh --read-only     # kun lesetester: ingen data opprettes, ingen e-post sendes
#   ./run.sh -k admin -x     # alt annet sendes videre til pytest (-k filter, -x stopp ved første feil)
#
# Krever at hele stacken kjører (docker compose up -d og ./dev-scripts/start-project.sh).
# Første kjøring lager et virtuelt Python-miljø i .venv og installerer avhengighetene.
# Se README.md (oppsett) og TESTS.md (hva hver test gjør).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"

if [ ! -x "$VENV/bin/python" ]; then
  echo "Lager virtuelt Python-miljø i $VENV ..."
  python3 -m venv "$VENV"
fi
if [ ! -f "$VENV/.installed" ] || [ "$ROOT/requirements.txt" -nt "$VENV/.installed" ]; then
  echo "Installerer avhengigheter ..."
  "$VENV/bin/pip" install -q -r "$ROOT/requirements.txt"
  touch "$VENV/.installed"
fi

args=()
for arg in "$@"; do
  case "$arg" in
    --direct)
      export API_TEST_AUTH_URL="${API_TEST_AUTH_URL:-http://localhost:5001}"
      export API_TEST_CORE_URL="${API_TEST_CORE_URL:-http://localhost:5002}"
      ;;
    --read-only)
      export API_TEST_ENV=readonly
      ;;
    *)
      args+=("$arg")
      ;;
  esac
done

cd "$ROOT"
exec "$VENV/bin/python" -m pytest ${args[@]+"${args[@]}"}
