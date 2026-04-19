#!/usr/bin/env bash
# Atlas_V2 — smoke-test the deployed demo box. Reads public IP from .state.json.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_FILE="${SCRIPT_DIR}/.state.json"
[[ -f "${STATE_FILE}" ]] || { echo "Missing ${STATE_FILE}." >&2; exit 1; }

PY="$(command -v python || command -v python3)"
PUBLIC_IP="$("${PY}" -c "import json,sys; print(json.load(open(sys.argv[1]))['public_ip'])" "${STATE_FILE}")"
BASE="http://${PUBLIC_IP}"

pass=0; fail=0
check() {
  local name="$1" url="$2" expect="${3:-200}"
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "${url}" || echo 000)"
  if [[ "${code}" == "${expect}" ]]; then
    printf '  ✅ %-30s %s (%s)\n' "${name}" "${url}" "${code}"
    pass=$((pass+1))
  else
    printf '  ❌ %-30s %s  expected %s got %s\n' "${name}" "${url}" "${expect}" "${code}"
    fail=$((fail+1))
  fi
}

echo "Smoke-testing ${BASE}"
check "Frontend root"       "${BASE}/"
check "Backend health"      "${BASE}/api/v1/health"
check "OpenAPI docs"        "${BASE}/api/docs"
check "Prometheus metrics"  "${BASE}/metrics"
check "Grafana login"       "${BASE}/grafana/login"

echo
echo "Passed: ${pass}  Failed: ${fail}"
[[ ${fail} -eq 0 ]]
