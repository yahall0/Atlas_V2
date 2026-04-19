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
  local name="$1" url="$2" expect_pattern="${3:-2..|3..}"
  code="$(curl -sL -o /dev/null -w '%{http_code}' --max-time 15 "${url}" || echo 000)"
  if [[ "${code}" =~ ^(${expect_pattern})$ ]]; then
    printf '  ✅ %-30s %s (%s)\n' "${name}" "${url}" "${code}"
    pass=$((pass+1))
  else
    printf '  ❌ %-30s %s  expected %s got %s\n' "${name}" "${url}" "${expect_pattern}" "${code}"
    fail=$((fail+1))
  fi
}

echo "Smoke-testing ${BASE}"
check "Frontend root (→login)" "${BASE}/"              "200|307"
check "Frontend /login"     "${BASE}/login"            "200"
check "Backend health"      "${BASE}/api/v1/health"    "200"
check "Prometheus metrics"  "${BASE}/metrics"          "200"
check "Grafana"             "${BASE}/grafana/"         "200"

echo
echo "Passed: ${pass}  Failed: ${fail}"
[[ ${fail} -eq 0 ]]
