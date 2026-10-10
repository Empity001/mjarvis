# Prueba los cambios de esta carpeta en la Latitude SIN tocar el servicio en marcha: copia servidor/, comportamiento/ y grafo/
# a ~/mjarvis-prueba y corre los escenarios con un modelo simulado. (Es linux/probar.sh, para Windows.)
# Uso:  probar.cmd        -> resumen        probar.cmd -v  -> detalle de cada fallo
param([switch]$v)
. "$PSScriptRoot\sync.ps1"
Set-Location $Raiz

Invoke-Latitude 'mkdir -p ~/mjarvis-prueba/web/grafo ~/mjarvis-prueba/conocimiento && cp ~/mjarvis/web/grafo/graph.json ~/mjarvis/web/grafo/trato.json ~/mjarvis-prueba/web/grafo/ 2>/dev/null; cp ~/mjarvis/clave.txt ~/mjarvis-prueba/ 2>/dev/null; true' | Out-Null
$excluir = 'propuestas.json', 'recetas.json'
foreach ($carpeta in 'servidor', 'comportamiento', 'grafo') {
    Send-Cambios -Origen $carpeta -Destino "mjarvis-prueba/$carpeta" -Excluir $excluir -Aplicar | Out-Null
}
$arg = if ($v) { '-v' } else { '' }
& ssh @(Get-OpcionesSsh) $Latitude "cd ~/mjarvis-prueba/servidor && ~/mjarvis/venv/bin/python pruebas_rutas.py $arg"
exit $LASTEXITCODE
