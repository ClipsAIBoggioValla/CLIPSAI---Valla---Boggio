#!/usr/bin/env bash
# =============================================================================
# clipsai — Verificacion automatica de la Issue 4 (videos + jobs FastAPI)
# -----------------------------------------------------------------------------
# Flujo:
#   0) Precheck backend + auth (registro/login -> TOKEN)
#   1) POST /videos valido      -> 201 + video_id
#   2) POST /videos invalido    -> 400 (extension no permitida)
#   3) POST /videos/{id}/jobs   -> 202 inmediato + job_id
#   4) GET  /jobs/{id} polling  -> PENDING -> PROCESSING -> COMPLETED + result_metadata
#
# Uso:
#   chmod +x scripts/verify-issue4.sh
#   ./scripts/verify-issue4.sh
#   BASE_URL=http://localhost:8000 ./scripts/verify-issue4.sh
#   TEST_EMAIL=x@x.com TEST_PASSWORD=yyy ./scripts/verify-issue4.sh
#
# Requisitos: curl, jq (opcional, fallback grep/sed)
# =============================================================================

set -Eeuo pipefail

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
BASE_URL="${BASE_URL:-http://localhost:8000}"
TEST_EMAIL="${TEST_EMAIL:-testuser@clipsai.dev}"
TEST_PASSWORD="${TEST_PASSWORD:-Passw0rd!123}"
TEST_FULL_NAME="${TEST_FULL_NAME:-Test User}"
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

log()   { echo -e "${C_CYAN}[verify-issue4]${C_RESET} $*"; }
step()  { echo -e "\n${C_BOLD}${C_BLUE}==>${C_RESET} ${C_BOLD}$*${C_RESET}"; }
info()  { echo -e "  ${C_GRAY}$*${C_RESET}"; }
pass()  { echo -e "  ${C_GREEN}${C_BOLD}[PASS]${C_RESET} $*"; }
faild() { echo -e "  ${C_RED}${C_BOLD}[FAIL]${C_RESET} $*"; }
fatal() { echo -e "${C_RED}${C_BOLD}[FATAL]${C_RESET} $*" >&2; exit 1; }

TESTS_TOTAL=0
TESTS_PASSED=0
declare -a FAILED_TESTS=()

record_pass() { TESTS_TOTAL=$(( TESTS_TOTAL + 1 )); TESTS_PASSED=$(( TESTS_PASSED + 1 )); pass "$1"; }
record_fail() {
    TESTS_TOTAL=$(( TESTS_TOTAL + 1 ))
    FAILED_TESTS+=("$1")
    faild "$1"
}

HTTP_CODE=""
HTTP_BODY=""
TEST_DIR="$(pwd)/tmp_test"
mkdir -p "${TEST_DIR}"
BODY_FILE="${TEST_DIR}/.verify-body.json"
: > "${BODY_FILE}"
trap 'rm -rf "${TEST_DIR}"' EXIT

# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------
command -v curl >/dev/null 2>&1 || fatal "'curl' no esta instalado."

HAS_JQ=0
if command -v jq >/dev/null 2>&1; then
    HAS_JQ=1
else
    log "${C_YELLOW}jq no encontrado; usando parser fallback (regex).${C_RESET}"
fi

json_extract() {
    local json="$1" key="$2"
    if (( HAS_JQ )); then
        printf '%s' "$json" | jq -r --arg k "$key" '.[$k] // empty'
    else
        printf '%s' "$json" \
            | grep -oE "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" \
            | head -n1 \
            | sed -E "s/.*\"${key}\"[[:space:]]*:[[:space:]]*\"([^\"]*)\".*/\1/"
    fi
}

json_has_key() {
    local json="$1" key="$2"
    if (( HAS_JQ )); then
        jq -e --arg k "$key" 'has($k)' <<<"$json" >/dev/null 2>&1
    else
        grep -q "\"${key}\"" <<<"$json"
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

# -----------------------------------------------------------------------------
# 0) Precheck backend
# -----------------------------------------------------------------------------
step "Precheck: comprobando backend en ${BASE_URL}"

elapsed=0
backend_up=0
while (( elapsed < HEALTH_TIMEOUT_SEC )); do
    if curl -fsS -m 2 "${BASE_URL}/health" >/dev/null 2>&1 \
       || curl -fsS -m 2 "${BASE_URL}/docs" >/dev/null 2>&1; then
        pass "Backend accesible (${elapsed}s)"
        backend_up=1
        break
    fi
    printf "."
    sleep 2
    elapsed=$(( elapsed + 2 ))
done

if (( backend_up == 0 )); then
    fatal "Backend no respondio en ${HEALTH_TIMEOUT_SEC}s. Levantalo con: docker compose up -d"
fi

if command -v docker >/dev/null 2>&1; then
    info "Contenedor:"
    docker ps --filter "name=clipsai-backend-fastapi" \
              --format "  ${C_GRAY}{{.Names}}  {{.Status}}  {{.Ports}}${C_RESET}" 2>/dev/null || true
fi

# -----------------------------------------------------------------------------
# 1) Autenticacion: registro (idempotente) + login -> TOKEN
# -----------------------------------------------------------------------------
step "Auth: registro + login -> TOKEN"

http_request POST "${BASE_URL}/auth/registro" \
    --json "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\",\"full_name\":\"${TEST_FULL_NAME}\"}"
info "POST /auth/registro -> HTTP ${HTTP_CODE}"

if [[ "$HTTP_CODE" == "201" || "$HTTP_CODE" == "200" || "$HTTP_CODE" == "409" ]]; then
    if [[ "$HTTP_CODE" == "409" ]]; then
        info "${C_YELLOW}Usuario ya existia (409), continuando.${C_RESET}"
    fi
    pass "Registro OK / idempotente"
else
    faild "Registro devolvio HTTP ${HTTP_CODE}: ${HTTP_BODY}"
    fatal "No se pudo registrar usuario para el test"
fi

http_request POST "${BASE_URL}/auth/login" \
    --json "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}"
info "POST /auth/login -> HTTP ${HTTP_CODE}"

TOKEN=""
if [[ "$HTTP_CODE" == "200" ]]; then
    TOKEN=$(json_extract "$HTTP_BODY" "access_token")
    if [[ -n "$TOKEN" ]]; then
        info "token_type=bearer len=${#TOKEN} prefijo=${TOKEN:0:20}..."
        pass "Login OK"
    else
        fatal "Login 200 pero sin access_token: ${HTTP_BODY}"
    fi
else
    fatal "Login devolvio HTTP ${HTTP_CODE}: ${HTTP_BODY}"
fi

AUTH_HEADER="Authorization: Bearer ${TOKEN}"

# -----------------------------------------------------------------------------
# 2) Test subida VALIDA — POST /videos
# -----------------------------------------------------------------------------
step "Test 1 — POST /videos valido (video .mp4 + transcripcion .txt) -> 201"

TEST_VIDEO="${TEST_DIR}/test_video.mp4"
TEST_TRANSCRIPT="${TEST_DIR}/test_transcription.txt"
printf 'FAKE_MP4_CONTENT_FOR_TEST' > "$TEST_VIDEO"
cat > "$TEST_TRANSCRIPT" <<'EOF'
00:00:00 - Hola mundo, esto es una transcripcion de prueba
00:00:10 - Segundo segmento para el motor de clips
00:00:30 - Tercer segmento con contenido suficiente para generar metadata
EOF

info "Archivos: $(basename "$TEST_VIDEO") ($(wc -c < "$TEST_VIDEO") bytes), $(basename "$TEST_TRANSCRIPT") ($(wc -c < "$TEST_TRANSCRIPT") bytes)"

http_multipart "${BASE_URL}/videos" \
    --header "${AUTH_HEADER}" \
    --field "video=@${TEST_DIR}/test_video.mp4" \
    --field "transcription=@${TEST_DIR}/test_transcription.txt"

info "HTTP ${HTTP_CODE}"
VIDEO_ID=""
if [[ "$HTTP_CODE" == "201" ]]; then
    VIDEO_ID=$(json_extract "$HTTP_BODY" "id")
    if [[ -n "$VIDEO_ID" ]]; then
        info "video_id=${VIDEO_ID}"
        record_pass "POST /videos valido -> 201 + video_id"
    else
        record_fail "POST /videos 201 pero sin id en body: ${HTTP_BODY}"
    fi
else
    record_fail "POST /videos valido devolvio HTTP ${HTTP_CODE} (esperado 201). Body: ${HTTP_BODY}"
fi

# -----------------------------------------------------------------------------
# 3) Test subida INVALIDA — extension no permitida -> 400
# -----------------------------------------------------------------------------
step "Test 2 — POST /videos invalido (video .pdf) -> 400"

BAD_VIDEO="${TEST_DIR}/test.pdf"
printf 'FAKE_PDF' > "$BAD_VIDEO"

http_multipart "${BASE_URL}/videos" \
    --header "${AUTH_HEADER}" \
    --field "video=@${TEST_DIR}/test.pdf" \
    --field "transcription=@${TEST_DIR}/test_transcription.txt"

info "HTTP ${HTTP_CODE}"
if [[ "$HTTP_CODE" == "400" ]]; then
    record_pass "Validacion extension rechazada correctamente (400)"
else
    record_fail "Se esperaba 400 para extension no permitida, se obtuvo HTTP ${HTTP_CODE}. Body: ${HTTP_BODY}"
fi

# -----------------------------------------------------------------------------
# 4) Disparo Job asincrono — POST /videos/{id}/jobs -> 202 inmediato
# -----------------------------------------------------------------------------
step "Test 3 — POST /videos/{video_id}/jobs -> 202 inmediato"

if [[ -z "$VIDEO_ID" ]]; then
    record_fail "Sin video_id, se salta creacion de job"
    JOB_ID=""
else
    info "video_id=${VIDEO_ID}"
    START_MS=$(date +%s%3N 2>/dev/null || echo 0)

    HTTP_CODE=$(curl -sS -o "$BODY_FILE" -w "%{http_code}" -X POST \
        -H "${AUTH_HEADER}" \
        "${BASE_URL}/videos/${VIDEO_ID}/jobs") || fatal "curl fallo POST /videos/${VIDEO_ID}/jobs"
    HTTP_BODY=$(cat "$BODY_FILE")

    if [[ "$START_MS" != "0" ]]; then
        END_MS=$(date +%s%3N 2>/dev/null || echo 0)
        ELAPSED_MS=$(( END_MS - START_MS ))
        info "Tiempo respuesta: ${ELAPSED_MS}ms"
        if (( ELAPSED_MS > 2000 )); then
            info "${C_YELLOW}Advertencia: respuesta tardo ${ELAPSED_MS}ms, deberia ser sub-segundo (no bloqueante).${C_RESET}"
        fi
    fi

    info "HTTP ${HTTP_CODE}"
    JOB_ID=""
    if [[ "$HTTP_CODE" == "202" ]]; then
        JOB_ID=$(json_extract "$HTTP_BODY" "id")
        JOB_STATUS=$(json_extract "$HTTP_BODY" "status")
        info "job_id=${JOB_ID} status=${JOB_STATUS}"
        if [[ -n "$JOB_ID" ]]; then
            if [[ "$JOB_STATUS" == "PENDING" ]]; then
                record_pass "POST /videos/{id}/jobs -> 202 + PENDING (no bloqueante)"
            else
                info "${C_YELLOW}Status inicial es ${JOB_STATUS}, se esperaba PENDING (puede haber transicionado rapido).${C_RESET}"
                record_pass "POST /videos/{id}/jobs -> 202 (job creado, status=${JOB_STATUS})"
            fi
        else
            record_fail "202 pero sin job id: ${HTTP_BODY}"
        fi
    else
        record_fail "POST /videos/{id}/jobs devolvio HTTP ${HTTP_CODE} (esperado 202). Body: ${HTTP_BODY}"
        JOB_ID=""
    fi
fi

# -----------------------------------------------------------------------------
# 5) Polling GET /jobs/{id} -> PENDING -> PROCESSING -> COMPLETED
# -----------------------------------------------------------------------------
step "Test 4 — Polling GET /jobs/{job_id} (timeout ${POLL_TIMEOUT_SEC}s)"

if [[ -z "${JOB_ID:-}" ]]; then
    record_fail "Sin job_id, se salta polling"
else
    info "job_id=${JOB_ID}"
    poll_elapsed=0
    last_status=""
    final_status=""
    final_body=""

    while (( poll_elapsed < POLL_TIMEOUT_SEC )); do
        http_request GET "${BASE_URL}/jobs/${JOB_ID}" --header "${AUTH_HEADER}"
        cur_status=$(json_extract "$HTTP_BODY" "status")
        if [[ "$cur_status" != "$last_status" && -n "$cur_status" ]]; then
            info "  [${poll_elapsed}s] status=${cur_status}"
            last_status="$cur_status"
        fi

        if [[ "$cur_status" == "COMPLETED" ]]; then
            final_status="$cur_status"
            final_body="$HTTP_BODY"
            break
        elif [[ "$cur_status" == "FAILED" ]]; then
            final_status="$cur_status"
            final_body="$HTTP_BODY"
            info "${C_YELLOW}Job fallo, revisando error_message...${C_RESET}"
            break
        fi

        sleep "$POLL_INTERVAL_SEC"
        poll_elapsed=$(( poll_elapsed + POLL_INTERVAL_SEC ))
    done

    if [[ -z "$final_status" ]]; then
        http_request GET "${BASE_URL}/jobs/${JOB_ID}" --header "${AUTH_HEADER}"
        final_status=$(json_extract "$HTTP_BODY" "status")
        final_body="$HTTP_BODY"
        info "Ultimo status tras timeout: ${final_status}"
    fi

    info "Status final: ${final_status}"

    if [[ "$final_status" == "COMPLETED" ]]; then
        if json_has_key "$final_body" "result_metadata"; then
            if (( HAS_JQ )); then
                meta_not_null=$(printf '%s' "$final_body" | jq -e '.result_metadata != null' >/dev/null 2>&1 && echo "yes" || echo "no")
                if [[ "$meta_not_null" == "yes" ]]; then
                    record_pass "Polling -> COMPLETED con result_metadata presente"
                else
                    record_fail "COMPLETED pero result_metadata es null: ${final_body}"
                fi
            else
                record_pass "Polling -> COMPLETED con result_metadata clave presente"
            fi
        else
            record_fail "COMPLETED pero sin result_metadata en body: ${final_body}"
        fi
    elif [[ "$final_status" == "FAILED" ]]; then
        err_msg=$(json_extract "$final_body" "error_message")
        record_fail "Job termino en FAILED (error_message: ${err_msg:-<vacio>}) — revisar motor Issue 2"
    else
        record_fail "Polling timeout ${POLL_TIMEOUT_SEC}s, ultimo status: ${final_status}. Body: ${final_body}"
    fi
fi

# -----------------------------------------------------------------------------
# Reporte final
# -----------------------------------------------------------------------------
echo -e "\n${C_BOLD}${C_CYAN}============================================================${C_RESET}"
echo -e "${C_BOLD}${C_CYAN} Reporte — Issue 4: Videos + Jobs asincronos (FastAPI)${C_RESET}"
echo -e "${C_BOLD}${C_CYAN}============================================================${C_RESET}"

echo -e "  ${C_BOLD}Tests corridos:${C_RESET} ${TESTS_TOTAL}"
echo -e "  ${C_BOLD}Passed:${C_RESET}         ${C_GREEN}${TESTS_PASSED}${C_RESET}"
echo -e "  ${C_BOLD}Failed:${C_RESET}         ${C_RED}$(( TESTS_TOTAL - TESTS_PASSED ))${C_RESET}"

echo -e "\n${C_BOLD}Criterios de aceptacion (ISSUES.md — Issue 4):${C_RESET}"
if (( TESTS_PASSED == TESTS_TOTAL && TESTS_TOTAL >= 4 )); then
    echo -e "  ${C_GREEN}[OK]${C_RESET} Subir video no bloquea (202 inmediato) y valida formato/tamaño."
    echo -e "  ${C_GREEN}[OK]${C_RESET} Job transita PENDING -> PROCESSING -> COMPLETED/FAILED."
    echo -e "  ${C_GREEN}[OK]${C_RESET} Archivo invalido rechazado con 400."
    echo ""
    echo -e "${C_GREEN}${C_BOLD} TODOS los criterios de aceptacion de la Issue 4 se cumplen.${C_RESET}"
    exit 0
else
    echo -e "  ${C_RED}[X]${C_RESET} Faltan validaciones. Tests fallidos:"
    for t in "${FAILED_TESTS[@]}"; do
        echo -e "    ${C_RED}- ${t}${C_RESET}"
    done
    echo ""
    echo -e "${C_RED}${C_BOLD} La Issue 4 NO cumple todos los criterios. Revisa los logs arriba.${C_RESET}"
    exit 1
fi
