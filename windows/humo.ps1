# La prueba de humo con navegador (bench/humo.js): recorre todas las pantallas y hace una pregunta. Correrla SIEMPRE después de
# tocar index.html, shell.js o control.js: probar.cmd no ejecuta el JavaScript de las pantallas.
# Usa Microsoft Edge, que ya viene con Windows (no descarga ningún navegador).
$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $PSScriptRoot
$tools = Join-Path $env:USERPROFILE 'mjarvis-tools'
if (-not (Test-Path (Join-Path $tools 'node_modules\playwright'))) { throw "Falta Playwright: corre  windows\instalar.cmd  primero." }
& "$PSScriptRoot\tunel.ps1"
try {
    $env:NODE_PATH = Join-Path $tools 'node_modules'
    $env:MJARVIS_CANAL = 'msedge'
    & node (Join-Path $Raiz 'bench\humo.js') 'http://localhost:8081'
    exit $LASTEXITCODE
} finally { & "$PSScriptRoot\tunel.ps1" -Cerrar | Out-Null }
