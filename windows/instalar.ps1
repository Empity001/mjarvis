# Deja listo este Windows para el flujo de M-Jarvis: revisa el acceso a la Latitude y las herramientas, e instala Playwright
# (solo la librería, ~10 MB, en C:\Users\<tú>\mjarvis-tools: fuera de OneDrive) para la prueba de humo con Edge.
$ErrorActionPreference = 'Stop'
$ok = $true
function Revisar($nombre, [bool]$bien, $detalle = '') { if ($bien) { Write-Host ("  [ok] {0} {1}" -f $nombre, $detalle) } else { Write-Host ("  [FALTA] {0} {1}" -f $nombre, $detalle); $script:ok = $false } }

Write-Host 'Acceso a la Latitude'
Revisar 'ssh' ([bool](Get-Command ssh -ErrorAction SilentlyContinue))
Revisar 'tar' ([bool](Get-Command tar -ErrorAction SilentlyContinue))
Revisar 'scp' ([bool](Get-Command scp -ErrorAction SilentlyContinue))
Revisar 'llave ~/.ssh/mjarvis_ed25519' (Test-Path "$env:USERPROFILE\.ssh\mjarvis_ed25519")
$hola = & ssh -o BatchMode=yes -o ConnectTimeout=10 mjarvis 'hostname' 2>$null
Revisar 'ssh mjarvis (entra sin contraseña)' ($LASTEXITCODE -eq 0) "-> $hola"

Write-Host 'Herramientas'
Revisar 'node' ([bool](Get-Command node -ErrorAction SilentlyContinue)) ((& node --version) 2>$null)
Revisar 'npm' ([bool](Get-Command npm -ErrorAction SilentlyContinue))
$edge = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
Revisar 'Microsoft Edge' (Test-Path $edge)

$tools = Join-Path $env:USERPROFILE 'mjarvis-tools'
New-Item -ItemType Directory -Force -Path $tools | Out-Null
if (-not (Test-Path (Join-Path $tools 'node_modules\playwright'))) {
    Write-Host "Instalando Playwright en $tools ..."
    Push-Location $tools
    try { if (-not (Test-Path 'package.json')) { & npm init -y | Out-Null }; & npm install playwright --no-audit --no-fund --loglevel=error } finally { Pop-Location }
}
Revisar 'playwright (npm)' (Test-Path (Join-Path $tools 'node_modules\playwright'))

if ($ok) { Write-Host "`nTodo listo. Flujo:  windows\probar.cmd  ->  windows\desplegar.cmd -y  ->  windows\humo.cmd" } else { Write-Host "`nHay cosas por arreglar (arriba)."; exit 1 }
