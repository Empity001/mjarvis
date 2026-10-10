# Abre (o cierra) el túnel a la Latitude: así http://localhost:8081 es la Latitude, y las pruebas con navegador ven
# la interfaz como si fuera la propia pantalla (sin pedir la clave). Es lo que hacía  ssh -M -S ... -L 8081:localhost:8080.
# Uso:  tunel.cmd           -> abre      tunel.cmd -Cerrar  -> cierra el que abrió este mismo script
param([switch]$Cerrar, [int]$Puerto = 8081)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\sync.ps1"   # para reutilizar la dirección ya resuelta de la Latitude
$archivo = Join-Path $env:TEMP 'mjarvis-tunel.pid'

function Cerrar-Tunel {
    if (-not (Test-Path $archivo)) { return }
    $id = [int](Get-Content $archivo -Raw)
    # Se cierra solo ese proceso exacto, y solo si de verdad es un ssh: nunca por proceso padre ni por nombre.
    $p = Get-Process -Id $id -ErrorAction SilentlyContinue
    if ($p -and $p.ProcessName -eq 'ssh') { Stop-Process -Id $id -Force }
    Remove-Item $archivo -Force -ErrorAction SilentlyContinue
}
if ($Cerrar) { Cerrar-Tunel; Write-Host 'Túnel cerrado.'; exit 0 }

Cerrar-Tunel
$p = Start-Process -FilePath ssh -ArgumentList (@('-N', '-o', 'ExitOnForwardFailure=yes', '-L', "${Puerto}:localhost:8080") + (Get-OpcionesSsh) + @($Latitude)) -WindowStyle Hidden -PassThru
Set-Content -Path $archivo -Value $p.Id
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 300
    if ($p.HasExited) { Remove-Item $archivo -Force -ErrorAction SilentlyContinue; throw 'El túnel se cerró al abrirse: ¿hay otro usando el puerto $Puerto, o la Latitude no responde?' }
    try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', $Puerto); $c.Close(); Write-Host "Túnel abierto: http://localhost:$Puerto (pid $($p.Id))"; exit 0 } catch { }
}
Cerrar-Tunel; throw "El túnel no llegó a abrirse en $Puerto."
