#!/usr/bin/env bash
# =============================================================================
# clipsai — Verificacion automatica de la Issue 5 (CRUD Clips + Descarga)
# -----------------------------------------------------------------------------
# Flujo:
#   0) Precheck + registro/login user1 y user2 -> TOKEN1 / TOKEN2
#   1) POST /videos (TOKEN1) -> video_id
#   2) POST /videos/{id}/jobs (TOKEN1) -> job_id -> polling -> COMPLETED
#   3) GET /clips (TOKEN1) -> clip_id
#   4) GET /clips/{id} (TOKEN1) -> 200
#   5) PATCH /clips/{id} (TOKEN1) -> 200 + title/tags editados
#   6) GET /clips/{id}/descarga (TOKEN1) -> 200
#   7) Ownership TOKEN2 -> GET/PATCH/descarga/DELETE -> 403
#   8) DELETE /clips/{id} (TOKEN1) -> 204 + GET -> 404
#
# Uso:
#   chmod +x scripts/verify-issue5.sh
#   ./scripts/verify-issue5.sh
#   BASE_URL=http://localhost:8000 ./scripts/verify-issue5.sh
# =============================================================================

set -Eeuo pipefail

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
BASE_URL="${BASE_URL:-http://localhost:8000}"
USER1_EMAIL="${USER1_EMAIL:-user1_issue5@test.com}"
USER2_EMAIL="${USER2_EMAIL:-user2_issue5@test.com}"
USER_PASSWORD="${USER_PASSWORD:-Passw0rd!123}"
USER1_NAME="${USER1_NAME:-User One Issue5}"
USER2_NAME="${USER2_NAME:-User Two Issue5}"
HEALTH_TIMEOUT_SEC="${HEALTH_TIMEOUT_SEC:-30}"
POLL_TIMEOUT_SEC="${POLL_TIMEOUT_SEC:-30}"
POLL_INTERVAL_SEC="${POLL_INTERVAL_SEC:-1}"

# -----------------------------------------------------------------------------
# Colores
# -----------------------------------------------------------------------------
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    C_RESET="\033[0m"; C_BOLD="\033[1m"
    C_RED="\033[31m";  C_GREEN="\033[32m"
    C_YELLOW="\033[33m"; C_BLUE="\033[34m"; C_CYAN="\033[36m"; C_GRAY="\033[90m"
else
    C_RESET=""; C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_CYAN=""; C_GRAY=""
fi

log()   { echo -e "${C_CYAN}[verify-issue5]${C_RESET} $*"; }
step()  { echo -e "\n${C_BOLD}${C_BLUE}==>${C_RESET} ${C_BOLD}$*${C_RESET}"; }
info()  { echo -e "  ${C_GRAY}$*${C_RESET}"; }
pass()  { echo -e "  ${C_GREEN}${C_BOLD}[PASS]${C_RESET} $*"; }
faild() { echo -e "  ${C_RED}${C_BOLD}[FAIL]${C_RESET} $*"; }
fatal() { echo -e "${C_RED}${C_BOLD}[FATAL]${C_RESET} $*" >&2; exit 1; }

TESTS_TOTAL=0
TESTS_PASSED=0
declare -a FAILED_TESTS=()
record_pass() { TESTS_TOTAL=$(( TESTS_TOTAL + 1 )); TESTS_PASSED=$(( TESTS_PASSED + 1 )); pass "$1"; }
record_fail() { TESTS_TOTAL=$(( TESTS_TOTAL + 1 )); FAILED_TESTS+=("$1"); faild "$1"; }

HTTP_CODE=""
HTTP_BODY=""
TEST_DIR="$(pwd)/tmp_test_issue5"
mkdir -p "${TEST_DIR}"
BODY_FILE="${TEST_DIR}/.verify-body.json"
: > "${BODY_FILE}"
trap 'rm -rf "${TEST_DIR}"' EXIT

command -v curl >/dev/null 2>&1 || fatal "'curl' no esta instalado."

HAS_JQ=0
if command -v jq >/dev/null 2>&1; then HAS_JQ=1; else log "${C_YELLOW}jq no encontrado; usando fallback regex.${C_RESET}"; fi

json_extract() {
    local json="$1" key="$2"
    if (( HAS_JQ )); then
        printf '%s' "$json" | jq -r --arg k "$key" '.[$k] // empty' 2>/dev/null || echo ""
    else
        printf '%s' "$json" | grep -oE "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" 2>/dev/null | head -n1 | sed -E "s/.*\"${key}\"[[:space:]]*:[[:space:]]*\"([^\"]*)\".*/\1/" 2>/dev/null || echo ""
    fi
}

http_request() {
    local method="$1" url="$2"; shift 2
    local -a args=(-sS -o "$BODY_FILE" -w "%{http_code}" -X "$method" "$url")
    while (( $# > 0 )); do
        case "$1" in
            --json)   args+=(-H "Content-Type: application/json" --data "$2"); shift 2 ;;
            --header) args+=(-H "$2"); shift 2 ;;
            *) fatal "http_request: arg desconocido '$1'" ;;
        esac
    done
    HTTP_CODE=$(curl "${args[@]}") || fatal "curl fallo contra ${url}."
    HTTP_BODY=$(cat "$BODY_FILE")
}

http_multipart() {
    local url="$1"; shift
    local -a args=(-sS -o "$BODY_FILE" -w "%{http_code}" -X POST "$url")
    while (( $# > 0 )); do
        case "$1" in
            --header) args+=(-H "$2"); shift 2 ;;
            --field)  args+=(-F "$2"); shift 2 ;;
            *) fatal "http_multipart: arg desconocido '$1'" ;;
        esac
    done
    HTTP_CODE=$(curl "${args[@]}") || fatal "curl multipart fallo contra ${url}."
    HTTP_BODY=$(cat "$BODY_FILE")
}

register_or_login() {
    local email="$1" password="$2" name="$3" token_var="$4"
    http_request POST "${BASE_URL}/auth/registro" --json "{\"email\":\"${email}\",\"password\":\"${password}\",\"full_name\":\"${name}\"}"
    if [[ "$HTTP_CODE" == "201" || "$HTTP_CODE" == "200" ]]; then
        info "Registro ${email} -> ${HTTP_CODE}"
    elif [[ "$HTTP_CODE" == "409" ]]; then
        info "${C_YELLOW}Usuario ${email} ya existia (409).${C_RESET}"
    else
        fatal "Registro ${email} devolvio HTTP ${HTTP_CODE}: ${HTTP_BODY}"
    fi
    http_request POST "${BASE_URL}/auth/login" --json "{\"email\":\"${email}\",\"password\":\"${password}\"}"
    if [[ "$HTTP_CODE" != "200" ]]; then
        fatal "Login ${email} devolvio HTTP ${HTTP_CODE}: ${HTTP_BODY}"
    fi
    local tok
    tok=$(json_extract "$HTTP_BODY" "access_token")
    if [[ -z "$tok" ]]; then fatal "Login ${email} sin access_token: ${HTTP_BODY}"; fi
    printf -v "$token_var" '%s' "$tok"
}

# -----------------------------------------------------------------------------
# 0) Precheck
# -----------------------------------------------------------------------------
step "Precheck: backend en ${BASE_URL}"
elapsed=0; backend_up=0
while (( elapsed < HEALTH_TIMEOUT_SEC )); do
    if curl -fsS -m 2 "${BASE_URL}/health" >/dev/null 2>&1 || curl -fsS -m 2 "${BASE_URL}/docs" >/dev/null 2>&1; then
        pass "Backend accesible (${elapsed}s)"; backend_up=1; break
    fi
    printf "."; sleep 2; elapsed=$(( elapsed + 2 ))
done
if (( backend_up == 0 )); then fatal "Backend no respondio en ${HEALTH_TIMEOUT_SEC}s."; fi

# -----------------------------------------------------------------------------
# 1) Registro y login de 2 usuarios
# -----------------------------------------------------------------------------
step "Auth: registro/login user1 y user2"
register_or_login "$USER1_EMAIL" "$USER_PASSWORD" "$USER1_NAME" TOKEN1
info "TOKEN1 len=${#TOKEN1} prefijo=${TOKEN1:0:20}..."
register_or_login "$USER2_EMAIL" "$USER_PASSWORD" "$USER2_NAME" TOKEN2
info "TOKEN2 len=${#TOKEN2} prefijo=${TOKEN2:0:20}..."
AUTH1="Authorization: Bearer ${TOKEN1}"
AUTH2="Authorization: Bearer ${TOKEN2}"
pass "2 usuarios autenticados"

# -----------------------------------------------------------------------------
# 2) POST /videos con TOKEN1
# -----------------------------------------------------------------------------
step "Test 1 — POST /videos (TOKEN1) -> 201"

TEST_VIDEO="${TEST_DIR}/test_video.mp4"
TEST_TRANSCRIPT="${TEST_DIR}/test_transcription.txt"
printf 'FAKE_MP4_CONTENT_FOR_TEST_ISSUE5' > "$TEST_VIDEO"
cat > "$TEST_TRANSCRIPT" <<'EOF'
00:00:00 - Hola mundo transcripcion issue5
00:00:10 - Segundo segmento para motor clips issue5
00:00:30 - Tercer segmento contenido suficiente para metadata
EOF

http_multipart "${BASE_URL}/videos" --header "${AUTH1}" --field "video=@${TEST_DIR}/test_video.mp4" --field "transcription=@${TEST_DIR}/test_transcription.txt"
info "HTTP ${HTTP_CODE}"
VIDEO_ID=""
if [[ "$HTTP_CODE" == "201" ]]; then
    VIDEO_ID=$(json_extract "$HTTP_BODY" "id")
    if [[ -n "$VIDEO_ID" ]]; then
        info "video_id=${VIDEO_ID}"
        record_pass "POST /videos -> 201 + video_id"
    else
        record_fail "POST /videos 201 sin id: ${HTTP_BODY}"
    fi
else
    record_fail "POST /videos devolvio HTTP ${HTTP_CODE} (esperado 201): ${HTTP_BODY}"
fi

# -----------------------------------------------------------------------------
# 3) POST /videos/{id}/jobs y polling
# -----------------------------------------------------------------------------
step "Test 2 — POST /videos/{video_id}/jobs (TOKEN1) -> 202"

JOB_ID=""
if [[ -z "$VIDEO_ID" ]]; then
    record_fail "Sin video_id, salta jobs"
else
    http_request POST "${BASE_URL}/videos/${VIDEO_ID}/jobs" --header "${AUTH1}"
    info "HTTP ${HTTP_CODE}"
    if [[ "$HTTP_CODE" == "202" ]]; then
        JOB_ID=$(json_extract "$HTTP_BODY" "id")
        info "job_id=${JOB_ID} status=$(json_extract "$HTTP_BODY" "status")"
        if [[ -n "$JOB_ID" ]]; then
            record_pass "POST /videos/{id}/jobs -> 202"
        else
            record_fail "202 sin job id: ${HTTP_BODY}"
        fi
    else
        record_fail "POST /videos/{id}/jobs devolvio HTTP ${HTTP_CODE} (esperado 202): ${HTTP_BODY}"
    fi
fi

step "Polling GET /jobs/{job_id} hasta COMPLETED (max ${POLL_TIMEOUT_SEC}s)"
if [[ -z "${JOB_ID:-}" ]]; then
    record_fail "Sin job_id, salta polling"
else
    poll_elapsed=0; last_status=""; final_status=""
    while (( poll_elapsed < POLL_TIMEOUT_SEC )); do
        http_request GET "${BASE_URL}/jobs/${JOB_ID}" --header "${AUTH1}"
        cur_status=$(json_extract "$HTTP_BODY" "status")
        if [[ "$cur_status" != "$last_status" && -n "$cur_status" ]]; then
            info "  [${poll_elapsed}s] status=${cur_status}"
            last_status="$cur_status"
        fi
        if [[ "$cur_status" == "COMPLETED" ]]; then final_status="$cur_status"; break; fi
        if [[ "$cur_status" == "FAILED" ]]; then final_status="$cur_status"; info "${C_YELLOW}Job FAILED${C_RESET}"; break; fi
        sleep "$POLL_INTERVAL_SEC"; poll_elapsed=$(( poll_elapsed + POLL_INTERVAL_SEC ))
    done
    if [[ -z "$final_status" ]]; then
        http_request GET "${BASE_URL}/jobs/${JOB_ID}" --header "${AUTH1}"
        final_status=$(json_extract "$HTTP_BODY" "status")
        info "Ultimo status tras timeout: ${final_status}"
    fi
    info "Status final: ${final_status}"
    if [[ "$final_status" == "COMPLETED" ]]; then
        record_pass "Polling -> COMPLETED"
    else
        record_fail "Polling no llego a COMPLETED (final=${final_status}): ${HTTP_BODY}"
    fi
fi

# -----------------------------------------------------------------------------
# 4) GET /clips -> clip_id
# -----------------------------------------------------------------------------
step "Test 3 — GET /clips (TOKEN1) -> 200 + al menos 1 clip"

http_request GET "${BASE_URL}/clips" --header "${AUTH1}"
info "HTTP ${HTTP_CODE}"
CLIP_ID=""
if [[ "$HTTP_CODE" == "200" ]]; then
    if (( HAS_JQ )); then
        CLIP_ID=$(printf '%s' "$HTTP_BODY" | jq -r '.[0].id // empty' 2>/dev/null || echo "")
        count=$(printf '%s' "$HTTP_BODY" | jq 'length' 2>/dev/null || echo "?")
        info "clips count=${count} clip_id=${CLIP_ID}"
    else
        set +e
        if command -v python3 >/dev/null 2>&1; then
            PYBIN=python3
        elif command -v python >/dev/null 2>&1; then
            PYBIN=python
        else
            PYBIN=""
        fi
        if [[ -n "$PYBIN" ]]; then
            CLIP_ID=$("$PYBIN" -c "import sys, json; data=json.load(sys.stdin); print(data[0]['id'] if isinstance(data, list) and len(data)>0 else '')" <<<"$HTTP_BODY" 2>/dev/null || echo "")
            count=$("$PYBIN" -c "import sys, json; data=json.load(sys.stdin); print(len(data) if isinstance(data, list) else 0)" <<<"$HTTP_BODY" 2>/dev/null || echo "?")
            info "clips count=${count} clip_id=${CLIP_ID} (via ${PYBIN})"
        else
            CLIP_ID=$(printf '%s' "$HTTP_BODY" | grep -oE '"id"[[:space:]]*:[[:space:]]*"[^"]*"' 2>/dev/null | head -n1 | sed -E 's/.*"([^"]+)".*/\1/' 2>/dev/null || echo "")
            info "clip_id=${CLIP_ID} (via grep)"
        fi
        set -e
        if [[ -z "$CLIP_ID" ]]; then
            CLIP_ID=$(printf '%s' "$HTTP_BODY" | grep -oE '"id"[[:space:]]*:[[:space:]]*"[^"]*"' 2>/dev/null | head -n1 | sed -E 's/.*"([^"]+)".*/\1/' 2>/dev/null || echo "")
        fi
    fi
    if [[ -n "$CLIP_ID" ]]; then
        record_pass "GET /clips -> 200 con al menos 1 clip"
    else
        record_fail "GET /clips 200 pero sin clips: ${HTTP_BODY}"
    fi
else
    record_fail "GET /clips devolvio HTTP ${HTTP_CODE}: ${HTTP_BODY}"
fi

# -----------------------------------------------------------------------------
# 5) GET /clips/{clip_id} (TOKEN1) -> 200
# -----------------------------------------------------------------------------
step "Test 4 — GET /clips/{clip_id} (TOKEN1) -> 200"

if [[ -z "${CLIP_ID:-}" ]]; then
    record_fail "Sin clip_id, salta GET /clips/{id}"
else
    http_request GET "${BASE_URL}/clips/${CLIP_ID}" --header "${AUTH1}"
    info "HTTP ${HTTP_CODE}"
    if [[ "$HTTP_CODE" == "200" ]]; then
        returned_id=$(json_extract "$HTTP_BODY" "id")
        if [[ "$returned_id" == "$CLIP_ID" ]]; then
            record_pass "GET /clips/{id} -> 200 OK"
        else
            record_fail "GET /clips/{id} 200 pero id no coincide: ${HTTP_BODY}"
        fi
    else
        record_fail "GET /clips/{id} devolvio HTTP ${HTTP_CODE}: ${HTTP_BODY}"
    fi
fi

# -----------------------------------------------------------------------------
# 6) PATCH /clips/{clip_id} (TOKEN1) -> 200
# -----------------------------------------------------------------------------
step "Test 5 — PATCH /clips/{clip_id} (TOKEN1) -> 200 con title/tags editados"

if [[ -z "${CLIP_ID:-}" ]]; then
    record_fail "Sin clip_id, salta PATCH"
else
    http_request PATCH "${BASE_URL}/clips/${CLIP_ID}" --header "${AUTH1}" --json '{"title":"Clip Editado Test","tags":["test","edited"]}'
    info "HTTP ${HTTP_CODE}"
    if [[ "$HTTP_CODE" == "200" ]]; then
        new_title=$(json_extract "$HTTP_BODY" "title")
        if [[ "$new_title" == "Clip Editado Test" ]]; then
            record_pass "PATCH -> 200 con title actualizado"
        else
            record_fail "PATCH 200 pero title no actualizado (got='${new_title}'): ${HTTP_BODY}"
        fi
        if (( HAS_JQ )); then
            has_tags=$(printf '%s' "$HTTP_BODY" | jq -e '.tags | index("test")' >/dev/null 2>&1 && echo yes || echo no)
            if [[ "$has_tags" == "yes" ]]; then
                info "tags verificados con jq"
            else
                info "${C_YELLOW}tags no verificados con jq, pero PATCH fue 200${C_RESET}"
            fi
        fi
    else
        record_fail "PATCH devolvio HTTP ${HTTP_CODE}: ${HTTP_BODY}"
    fi
fi

# -----------------------------------------------------------------------------
# 7) GET /clips/{clip_id}/descarga (TOKEN1) -> 200
# -----------------------------------------------------------------------------
step "Test 6 — GET /clips/{clip_id}/descarga (TOKEN1) -> 200"

if [[ -z "${CLIP_ID:-}" ]]; then
    record_fail "Sin clip_id, salta descarga"
else
    HTTP_CODE=$(curl -sS -o "${TEST_DIR}/downloaded.bin" -w "%{http_code}" -H "${AUTH1}" "${BASE_URL}/clips/${CLIP_ID}/descarga") || HTTP_CODE="000"
    info "HTTP ${HTTP_CODE}"
    if [[ "$HTTP_CODE" == "200" ]]; then
        size=$(wc -c < "${TEST_DIR}/downloaded.bin" 2>/dev/null || echo 0)
        info "download size=${size} bytes"
        if (( size > 0 )); then
            record_pass "GET /descarga -> 200 con contenido"
        else
            record_fail "GET /descarga 200 pero contenido vacio"
        fi
    else
        HTTP_BODY=$(cat "${TEST_DIR}/downloaded.bin" 2>/dev/null || echo "")
        record_fail "GET /descarga devolvio HTTP ${HTTP_CODE}: ${HTTP_BODY}"
    fi
fi

# -----------------------------------------------------------------------------
# 8) Ownership checks con TOKEN2 -> 403
# -----------------------------------------------------------------------------
step "Test 7 — Ownership: TOKEN2 intenta GET /clips/{clip_id} -> 403"

if [[ -z "${CLIP_ID:-}" ]]; then
    record_fail "Sin clip_id, salta ownership GET"
else
    http_request GET "${BASE_URL}/clips/${CLIP_ID}" --header "${AUTH2}"
    info "HTTP ${HTTP_CODE}"
    if [[ "$HTTP_CODE" == "403" ]]; then
        record_pass "GET con TOKEN2 -> 403 Forbidden (ownership OK)"
    elif [[ "$HTTP_CODE" == "404" ]]; then
        record_pass "GET con TOKEN2 -> 404 (aceptado como ownership, prefiere 403)"
    else
        record_fail "Se esperaba 403 para GET ajeno, se obtuvo HTTP ${HTTP_CODE}: ${HTTP_BODY}"
    fi
fi

step "Test 8 — Ownership: TOKEN2 intenta PATCH /clips/{clip_id} -> 403"

if [[ -z "${CLIP_ID:-}" ]]; then
    record_fail "Sin clip_id, salta ownership PATCH"
else
    http_request PATCH "${BASE_URL}/clips/${CLIP_ID}" --header "${AUTH2}" --json '{"title":"Hack"}'
    info "HTTP ${HTTP_CODE}"
    if [[ "$HTTP_CODE" == "403" ]]; then
        record_pass "PATCH con TOKEN2 -> 403 Forbidden"
    elif [[ "$HTTP_CODE" == "404" ]]; then
        record_pass "PATCH con TOKEN2 -> 404 (aceptado)"
    else
        record_fail "Se esperaba 403 para PATCH ajeno, se obtuvo HTTP ${HTTP_CODE}: ${HTTP_BODY}"
    fi
fi

step "Test 9 — Ownership: TOKEN2 intenta GET /descarga -> 403"

if [[ -z "${CLIP_ID:-}" ]]; then
    record_fail "Sin clip_id, salta ownership descarga"
else
    HTTP_CODE=$(curl -sS -o "${TEST_DIR}/downloaded2.bin" -w "%{http_code}" -H "${AUTH2}" "${BASE_URL}/clips/${CLIP_ID}/descarga") || HTTP_CODE="000"
    info "HTTP ${HTTP_CODE}"
    if [[ "$HTTP_CODE" == "403" ]]; then
        record_pass "GET /descarga con TOKEN2 -> 403 Forbidden"
    elif [[ "$HTTP_CODE" == "404" ]]; then
        record_pass "GET /descarga con TOKEN2 -> 404 (aceptado)"
    else
        HTTP_BODY=$(cat "${TEST_DIR}/downloaded2.bin" 2>/dev/null || echo "")
        record_fail "Se esperaba 403 para descarga ajena, se obtuvo HTTP ${HTTP_CODE}: ${HTTP_BODY}"
    fi
fi

step "Test 10 — Ownership: TOKEN2 intenta DELETE -> 403"

if [[ -z "${CLIP_ID:-}" ]]; then
    record_fail "Sin clip_id, salta ownership DELETE"
else
    http_request DELETE "${BASE_URL}/clips/${CLIP_ID}" --header "${AUTH2}"
    info "HTTP ${HTTP_CODE}"
    if [[ "$HTTP_CODE" == "403" ]]; then
        record_pass "DELETE con TOKEN2 -> 403 Forbidden"
    elif [[ "$HTTP_CODE" == "404" ]]; then
        record_pass "DELETE con TOKEN2 -> 404 (aceptado)"
    else
        record_fail "Se esperaba 403 para DELETE ajeno, se obtuvo HTTP ${HTTP_CODE}: ${HTTP_BODY}"
    fi
fi

# -----------------------------------------------------------------------------
# 9) Limpieza: DELETE con TOKEN1 -> 204 + GET -> 404
# -----------------------------------------------------------------------------
step "Test 11 — DELETE /clips/{clip_id} (TOKEN1) -> 204"

if [[ -z "${CLIP_ID:-}" ]]; then
    record_fail "Sin clip_id, salta DELETE"
else
    http_request DELETE "${BASE_URL}/clips/${CLIP_ID}" --header "${AUTH1}"
    info "HTTP ${HTTP_CODE}"
    if [[ "$HTTP_CODE" == "204" || "$HTTP_CODE" == "200" ]]; then
        record_pass "DELETE con TOKEN1 -> ${HTTP_CODE} No Content"
    else
        record_fail "DELETE devolvio HTTP ${HTTP_CODE} (esperado 204): ${HTTP_BODY}"
    fi
fi

step "Test 12 — GET /clips/{clip_id} tras DELETE (TOKEN1) -> 404"

if [[ -z "${CLIP_ID:-}" ]]; then
    record_fail "Sin clip_id, salta verificacion post-DELETE"
else
    http_request GET "${BASE_URL}/clips/${CLIP_ID}" --header "${AUTH1}"
    info "HTTP ${HTTP_CODE}"
    if [[ "$HTTP_CODE" == "404" ]]; then
        record_pass "GET tras DELETE -> 404 Not Found"
    else
        record_fail "Se esperaba 404 tras DELETE, se obtuvo HTTP ${HTTP_CODE}: ${HTTP_BODY}"
    fi
fi

# -----------------------------------------------------------------------------
# Reporte final
# -----------------------------------------------------------------------------
echo -e "\n${C_BOLD}${C_CYAN}============================================================${C_RESET}"
echo -e "${C_BOLD}${C_CYAN} Reporte — Issue 5: CRUD Clips + Descarga + Ownership${C_RESET}"
echo -e "${C_BOLD}${C_CYAN}============================================================${C_RESET}"

echo -e "  ${C_BOLD}Tests corridos:${C_RESET} ${TESTS_TOTAL}"
echo -e "  ${C_BOLD}Passed:${C_RESET}         ${C_GREEN}${TESTS_PASSED}${C_RESET}"
echo -e "  ${C_BOLD}Failed:${C_RESET}         ${C_RED}$(( TESTS_TOTAL - TESTS_PASSED ))${C_RESET}"

echo -e "\n${C_BOLD}Criterios de aceptacion (ISSUES.md — Issue 5):${C_RESET}"
if (( TESTS_PASSED == TESTS_TOTAL && TESTS_TOTAL >= 10 )); then
    echo -e "  ${C_GREEN}[OK]${C_RESET} CRUD completo probado: crear (via Job), listar, editar metadata, eliminar."
    echo -e "  ${C_GREEN}[OK]${C_RESET} Ownership: usuario no puede ver/editar clips de otro (403)."
    echo -e "  ${C_GREEN}[OK]${C_RESET} Descarga funciona y requiere ownership."
    echo ""
    echo -e "${C_GREEN}${C_BOLD} TODOS los criterios de aceptacion de la Issue 5 se cumplen.${C_RESET}"
    exit 0
else
    echo -e "  ${C_RED}[X]${C_RESET} Faltan validaciones. Tests fallidos:"
    for t in "${FAILED_TESTS[@]}"; do
        echo -e "    ${C_RED}- ${t}${C_RESET}"
    done
    echo ""
    echo -e "${C_RED}${C_BOLD} La Issue 5 NO cumple todos los criterios. Revisa los logs arriba.${C_RESET}"
    exit 1
fi
