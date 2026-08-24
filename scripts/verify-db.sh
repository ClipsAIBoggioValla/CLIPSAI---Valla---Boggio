#!/usr/bin/env bash
# =============================================================================
# clipsai — Script de verificacion de la Issue 1 (DB dockerizada + esquema)
# -----------------------------------------------------------------------------
# Recorre el ciclo de vida completo para generar las evidencias del PR:
#   1) Levantar la DB desde cero (down -v + up -d).
#   2) Esperar el healthcheck de Postgres.
#   3) Listar tablas (\dt) y estructura detallada (\d) de las 4 tablas.
#   4) Insertar datos ficticios en `usuarios` y `videos`.
#   5) `docker compose down` (SIN -v) + `up -d` para probar persistencia.
#   6) SELECT que demuestra que los datos sobrevivieron.
#
# Uso:
#   chmod +x scripts/verify-db.sh
#   ./scripts/verify-db.sh
#
# Requisitos previos:
#   - Docker Desktop / Docker Engine corriendo.
#   - Archivo `.env` en la raiz (copiar de `.env.example` y ajustar).
#
# Compatibilidad:
#   - Detecta `docker compose` (v2) y cae a `docker-compose` (v1) si hace falta.
# =============================================================================

set -Eeuo pipefail

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="db"
CONTAINER_NAME="clipsai-db"
HEALTHCHECK_TIMEOUT_SEC=60

cd "${PROJECT_ROOT}"

# -----------------------------------------------------------------------------
# Colores (deshabilitados si no hay TTY)
# -----------------------------------------------------------------------------
if [[ -t 1 ]]; then
    C_RESET="\033[0m"; C_BOLD="\033[1m"
    C_RED="\033[31m";  C_GREEN="\033[32m"
    C_YELLOW="\033[33m"; C_BLUE="\033[34m"; C_CYAN="\033[36m"
else
    C_RESET=""; C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_CYAN=""
fi

log()       { echo -e "${C_CYAN}[verify-db]${C_RESET} $*"; }
step()      { echo -e "\n${C_BOLD}${C_BLUE}==>${C_RESET} ${C_BOLD}$*${C_RESET}"; }
ok()        { echo -e "${C_GREEN}[OK]${C_RESET}   $*"; }
warn()      { echo -e "${C_YELLOW}[WARN]${C_RESET} $*"; }
fail()      { echo -e "${C_RED}[FAIL]${C_RESET} $*" >&2; }
fatal()     { fail "$*"; exit 1; }

# -----------------------------------------------------------------------------
# Deteccion del binario de compose
# -----------------------------------------------------------------------------
if docker compose version >/dev/null 2>&1; then
    DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    DC=(docker-compose)
else
    fatal "No se encontro 'docker compose' ni 'docker-compose'. Instala Docker."
fi
log "Usando compose: ${DC[*]}"

# -----------------------------------------------------------------------------
# Chequeos previos
# -----------------------------------------------------------------------------
[[ -f "${PROJECT_ROOT}/docker-compose.yml" ]] \
    || fatal "No se encontro docker-compose.yml en ${PROJECT_ROOT}"

if [[ ! -f "${PROJECT_ROOT}/.env" ]]; then
    warn "No existe .env en ${PROJECT_ROOT}. Copiando desde .env.example..."
    [[ -f "${PROJECT_ROOT}/.env.example" ]] \
        || fatal "Tampoco existe .env.example. Aborto."
    cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
    warn "Se creo .env desde .env.example. Revisa las credenciales antes de un entorno real."
fi

# Cargar variables de POSTGRES_* desde el .env sin volcar todo al entorno
# (solo lo que necesitamos para los psql).
POSTGRES_USER="$(grep -E '^POSTGRES_USER=' "${PROJECT_ROOT}/.env" | tail -n1 | cut -d= -f2- | tr -d '"'"'"'')"
POSTGRES_DB="$(grep -E '^POSTGRES_DB='   "${PROJECT_ROOT}/.env" | tail -n1 | cut -d= -f2- | tr -d '"'"'"'')"
: "${POSTGRES_USER:=clipsai}"
: "${POSTGRES_DB:=clipsai}"
log "POSTGRES_USER=${POSTGRES_USER}  POSTGRES_DB=${POSTGRES_DB}"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
psql_exec() {
    # Ejecuta una sentencia SQL (-c "...")
    docker exec -i "${CONTAINER_NAME}" \
        psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 -c "$*"
}

psql_meta() {
    # Ejecuta un meta-comando de psql (-c "\dt", "\d tabla", etc.)
    docker exec -i "${CONTAINER_NAME}" \
        psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "$*"
}

wait_for_healthy() {
    step "Esperando healthcheck de Postgres (timeout ${HEALTHCHECK_TIMEOUT_SEC}s)"
    local elapsed=0
    while (( elapsed < HEALTHCHECK_TIMEOUT_SEC )); do
        local status
        status=$(docker inspect --format='{{.State.Health.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "starting")
        case "${status}" in
            healthy)
                ok "Postgres healthy tras ${elapsed}s"
                return 0
                ;;
            unhealthy)
                fatal "El contenedor ${CONTAINER_NAME} quedo unhealthy. Revisa: ${DC[*]} logs ${SERVICE_NAME}"
                ;;
            *)
                printf "."
                sleep 2
                elapsed=$(( elapsed + 2 ))
                ;;
        esac
    done
    fatal "Timeout esperando healthcheck. Revisa: ${DC[*]} logs ${SERVICE_NAME}"
}

banner() {
    echo -e "\n${C_BOLD}${C_CYAN}------------------------------------------------------------${C_RESET}"
    echo -e "${C_BOLD}${C_CYAN} $* ${C_RESET}"
    echo -e "${C_BOLD}${C_CYAN}------------------------------------------------------------${C_RESET}"
}

# =============================================================================
# 1) Reset total: down -v + up -d
# =============================================================================
banner "FASE 1 — Levantando la DB desde cero"

step "Bajando stack y borrando volumenes (docker compose down -v)"
"${DC[@]}" down -v --remove-orphans || true
ok "Stack limpio."

step "Levantando servicio '${SERVICE_NAME}' (docker compose up -d)"
"${DC[@]}" up -d "${SERVICE_NAME}"
ok "Servicio levantado."

wait_for_healthy

# =============================================================================
# 2) Estructura del esquema
# =============================================================================
banner "FASE 2 — Verificando estructura del esquema"

step "Listado de tablas (\\dt)"
psql_meta '\dt'

for tabla in usuarios videos jobs clips; do
    step "Estructura detallada de '${tabla}' (\\d ${tabla})"
    psql_meta "\\d ${tabla}"
done

step "Verificando que las 4 tablas existen"
count=$(docker exec -i "${CONTAINER_NAME}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
    -tAc "SELECT COUNT(*) FROM information_schema.tables
          WHERE table_schema='public' AND table_name IN ('usuarios','videos','jobs','clips');")
[[ "${count}" == "4" ]] || fatal "Se esperaban 4 tablas, se encontraron: ${count}"
ok "Las 4 tablas (usuarios, videos, jobs, clips) estan presentes."

step "Verificando indices en FKs"
psql_meta "SELECT indexname FROM pg_indexes
           WHERE schemaname='public'
             AND indexname IN ('idx_videos_usuario_id','idx_jobs_video_id','idx_clips_job_id')
           ORDER BY indexname;"

# =============================================================================
# 3) Datos ficticios (evidencia de INSERT)
# =============================================================================
banner "FASE 3 — Insertando datos ficticios"

step "INSERT en usuarios"
psql_exec "
    INSERT INTO usuarios (email, hashed_password, full_name)
    VALUES ('demo@clipsai.dev', '\$2b\$12\$DummyBcryptHashForEvidenceOnly....', 'Demo User')
    ON CONFLICT (email) DO UPDATE SET full_name = EXCLUDED.full_name
    RETURNING id, email, full_name, created_at;
"

step "INSERT en videos (usa el usuario recien creado)"
psql_exec "
    INSERT INTO videos (usuario_id, original_filename, file_path, duration_seconds, transcript)
    SELECT u.id,
           'demo-video.mp4',
           '/data/videos/demo-video.mp4',
           123.456,
           'Transcripcion de prueba para la Issue 1.'
    FROM usuarios u
    WHERE u.email = 'demo@clipsai.dev'
    RETURNING id, usuario_id, original_filename, duration_seconds, created_at;
"

step "Snapshot ANTES del reinicio"
psql_exec "SELECT email, full_name FROM usuarios WHERE email='demo@clipsai.dev';"
psql_exec "SELECT original_filename, duration_seconds FROM videos WHERE original_filename='demo-video.mp4';"

# =============================================================================
# 4) Reinicio SIN borrar volumenes (persistencia)
# =============================================================================
banner "FASE 4 — Probando persistencia (down + up sin -v)"

step "docker compose down (conservando el volumen postgres_data)"
"${DC[@]}" down
ok "Stack bajado. El volumen NO fue eliminado."

step "docker compose up -d nuevamente"
"${DC[@]}" up -d "${SERVICE_NAME}"
wait_for_healthy

# =============================================================================
# 5) Verificar que los datos sobrevivieron
# =============================================================================
banner "FASE 5 — Verificando que los datos sobrevivieron"

step "SELECT sobre usuarios"
psql_meta "SELECT id, email, full_name, created_at FROM usuarios;"

step "SELECT sobre videos"
psql_meta "SELECT id, usuario_id, original_filename, duration_seconds, created_at FROM videos;"

step "Chequeo final: deben existir 1 usuario y 1 video"
u_count=$(docker exec -i "${CONTAINER_NAME}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
    -tAc "SELECT COUNT(*) FROM usuarios WHERE email='demo@clipsai.dev';")
v_count=$(docker exec -i "${CONTAINER_NAME}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
    -tAc "SELECT COUNT(*) FROM videos WHERE original_filename='demo-video.mp4';")

[[ "${u_count}" == "1" ]] || fatal "Se esperaba 1 usuario tras el reinicio, se encontraron: ${u_count}"
[[ "${v_count}" == "1" ]] || fatal "Se esperaba 1 video tras el reinicio,   se encontraron: ${v_count}"
ok "Persistencia confirmada: 1 usuario + 1 video sobrevivieron el ciclo down/up."

# =============================================================================
# Instrucciones para el desarrollador (capturas del PR)
# =============================================================================
banner "SIGUIENTES PASOS — Evidencias para adjuntar al Pull Request"

cat <<EOF

${C_BOLD}Este script cumple los criterios de aceptacion de la Issue 1.${C_RESET}
Ahora capturaras las evidencias visuales para el PR.

${C_BOLD}Capturas de pantalla recomendadas:${C_RESET}

  ${C_YELLOW}1)${C_RESET} Terminal completa mostrando la salida de ${C_BOLD}FASE 2${C_RESET}:
     - El listado \\dt (4 tablas: usuarios, videos, jobs, clips).
     - La estructura \\d de cada tabla (columnas, tipos, FKs, indices).
     - La query final que confirma los 3 indices idx_*_id.

  ${C_YELLOW}2)${C_RESET} Terminal mostrando ${C_BOLD}FASE 3${C_RESET}:
     - Los dos INSERT ... RETURNING con las filas devueltas.

  ${C_YELLOW}3)${C_RESET} Terminal mostrando ${C_BOLD}FASE 4 + FASE 5${C_RESET} en una sola imagen:
     - El "docker compose down" seguido del "up -d" y el healthcheck.
     - Los dos SELECT posteriores que muestran los mismos datos vivos.

  ${C_YELLOW}4)${C_RESET} Ultima linea del script confirmando "Persistencia confirmada".

${C_BOLD}Comandos utiles para inspeccionar manualmente despues:${C_RESET}
  ${DC[*]} ps
  ${DC[*]} logs ${SERVICE_NAME}
  docker exec -it ${CONTAINER_NAME} psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}

${C_BOLD}Para volver a ejecutar la verificacion desde cero:${C_RESET}
  ./scripts/verify-db.sh

${C_GREEN}${C_BOLD}Verificacion completada con exito.${C_RESET}
EOF
