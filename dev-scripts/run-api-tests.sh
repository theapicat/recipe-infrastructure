#!/usr/bin/env bash
# Snarvei til API-testene. Selve inngangspunktet ligger i api-tests/run.sh (samme flagg: --direct, --read-only, pytest-argumenter).
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/../api-tests" && pwd)/run.sh" "$@"
