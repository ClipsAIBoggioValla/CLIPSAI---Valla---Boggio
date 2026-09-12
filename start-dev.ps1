#Requires -Version 5.1
<#
.SYNOPSIS
  Orquestación unificada ClipsAI — levanta los 5 servicios con un solo comando
.DESCRIPTION
  Opción A: Docker Compose completo (recomendado)
    docker compose up -d --build  -> db, backend_fastapi:8000, backend_express:3001, frontend_react:3000, frontend_vue:5173, ngrok->8000
  Opción B: Híbrido (este script)
    1) docker compose up -d db backend_fastapi backend_express (infra)
    2) npm run dev en frontend_react (3000) y frontend_vue (5173) en paralelo
    3) ngrok http 8000 --domain decorator-excretory-satin.ngrok-free.dev
  Uso:  .\start-dev.ps1          (híbrido)
        .\start-dev.ps1 -Docker  (full docker)
        .\start-dev.ps1 -Down    (baja todo)
#>
param(
  [switch]$Docker,
  [switch]$Down,
  [switch]$Logs
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Test-Cmd($cmd) { $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue) }

if ($Down) {
  Write-Host ">> docker compose down" -ForegroundColor Cyan
  docker compose down
  exit $LASTEXITCODE
}
if ($Logs) {
  docker compose logs -f
  exit $LASTEXITCODE
}

if (-not (Test-Path ".env")) {
  Write-Warning ".env no existe — copiando desde .env.example"
  Copy-Item ".env.example" ".env"
}

if ($Docker) {
  Write-Host ">> Opción A: docker compose up -d --build (6 servicios)" -ForegroundColor Cyan
  docker compose up -d --build
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  Write-Host "`n>> docker compose ps" -ForegroundColor Green
  docker compose ps
  Write-Host "`n>> Servicios:" -ForegroundColor Green
  Write-Host "  - db:               http://localhost:5432"
  Write-Host "  - backend_fastapi:  http://localhost:8000  (health /health, docs /docs)"
  Write-Host "  - backend_express:  http://localhost:3001  (health /health)"
  Write-Host "  - frontend_react:   http://localhost:3000"
  Write-Host "  - frontend_vue:     http://localhost:5173"
  Write-Host "  - ngrok:            https://decorator-excretory-satin.ngrok-free.dev -> backend_fastapi:8000  (inspect http://localhost:4040)"
  Write-Host "`n>> Logs: docker compose logs -f" -ForegroundColor Yellow
  exit 0
}

# --- Opción B híbrida ---
Write-Host ">> Opción B híbrida: infra Docker + frontends locales + ngrok" -ForegroundColor Cyan

if (-not (Test-Cmd docker)) { Write-Error "docker no encontrado"; exit 1 }
if (-not (Test-Cmd npm)) { Write-Error "npm no encontrado"; exit 1 }

Write-Host ">> 1/3 docker compose up -d db backend_fastapi backend_express" -ForegroundColor Cyan
docker compose up -d db backend_fastapi backend_express
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ">> 2/3 Verificando concurrently..." -ForegroundColor Cyan
if (-not (Test-Path "node_modules/.bin/concurrently")) {
  Write-Host "   Instalando concurrently en raíz..." -ForegroundColor Yellow
  npm install --save-dev concurrently@^8.2.2
}
if (-not (Test-Path "frontend_react/node_modules")) { Write-Host "   npm install frontend_react..." -ForegroundColor Yellow; npm --prefix frontend_react install }
if (-not (Test-Path "frontend_vue/node_modules")) { Write-Host "   npm install frontend_vue..." -ForegroundColor Yellow; npm --prefix frontend_vue install }

if (-not (Test-Cmd ngrok)) {
  Write-Warning "ngrok no encontrado — frontends se levantarán sin túnel. Instala con: npm i -g ngrok o choco install ngrok"
  Write-Host ">> Iniciando solo frontends..." -ForegroundColor Yellow
  npx concurrently --kill-others --names "REACT,VUE" "npm:dev:react" "npm:dev:vue"
  exit $LASTEXITCODE
}

Write-Host ">> 3/3 Levantando React(3000) + Vue(5173) + ngrok(8000->ngrok) — Ctrl+C para salir" -ForegroundColor Green
Write-Host "   React:  http://localhost:3000" -ForegroundColor White
Write-Host "   Vue:    http://localhost:5173" -ForegroundColor White
Write-Host "   FastAPI:http://localhost:8000/docs" -ForegroundColor White
Write-Host "   Ngrok:  https://decorator-excretory-satin.ngrok-free.dev" -ForegroundColor White

npx concurrently --kill-others --names "REACT,VUE,NGROK" "npm:dev:react" "npm:dev:vue" "npm:dev:ngrok"
