#!/usr/bin/env bash
# =============================================================================
# _verify-common.sh — helpers compartidos por los scripts verify-*.sh
# -----------------------------------------------------------------------------
# Centraliza log/step/info/pass/faild/fatal, record_pass/record_fail, json_extract,
# json_has_key, http_request, http_multipart y register_or_login para evitar
# duplicacion (Issue 42 — Duplic%).
#
# Uso desde cada script:
#   VERIFY_NAME="verify-auth"   # nombre del script (para logs)
#   source "$(dirname "$0")/_verify-common.sh"
# =============================================================================

# Colores (deshabilitados si no hay TTY o NO_COLOR esta seteado)
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    C_RESET="\033[0m"; C_BOLD="\033[1m"
    C_RED="\033[31m";  C_GREEN="\033[32m"
    C_YELLOW="\033[33m"; C_BLUE="\033[34m"; C_CYAN="\033[36m"; C_GRAY="\033[90m"
else
    C_RESET=""; C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_CYAN=""; C_GRAY=""
fi

VERIFY_NAME="${VERIFY_NAME:-verify}"

log()   { echo -e "${C_CYAN}[${VERIFY_NAME}]${C_RESET} $*"; }
step()  { echo -e "\n${C_BOLD}${C_BLUE}==>${C_RESET} ${C_BOLD}$*${C_RESET}"; }
info()  { echo -e "  ${C_GRAY}$*${C_RESET}"; }
pass()  { echo -e "  ${C_GREEN}${C_BOLD}[PASS]${C_RESET} $*"; }
faild() { echo -e "  ${C_RED}${C_BOLD}[FAIL]${C_RESET} $*"; }
fatal() { echo -e "${C_RED}${C_BOLD}[FATAL]${C_RESET} $*" >&2; exit 1; }

record_pass() { TESTS_TOTAL=$(( TESTS_TOTAL + 1 )); TESTS_PASSED=$(( TESTS_PASSED + 1 )); pass "$1"; }
record_fail() { TESTS_TOTAL=$(( TESTS_TOTAL + 1 )); FAILED_TESTS+=("$1"); faild "$1"; }

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
            --json)
                args+=(-H "Content-Type: application/json" -d "$2")
                shift 2
                ;;
            --header)
                args+=(-H "$2")
                shift 2
                ;;
            *)
                fatal "http_request: arg desconocido '$1'"
                ;;
        esac
    done

    HTTP_CODE=$(curl "${args[@]}") || fatal "curl fallo contra ${url}."
    HTTP_BODY=$(cat "$BODY_FILE")
}

http_multipart() {
    local method="$1" url="$2" file="$3" field="$4"; shift 4
    local -a args=(-sS -o "$BODY_FILE" -w "%{http_code}" -X "$method" "$url" -F "${field}=@${file}")

    while (( $# > 0 )); do
        case "$1" in
            --header)
                args+=(-H "$2")
                shift 2
                ;;
            *)
                fatal "http_multipart: arg desconocido '$1'"
                ;;
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
EOF
echo "written ($(wc -l < scripts/_verify-common.sh) lines)"