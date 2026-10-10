# Envía los cambios de esta carpeta a la Latitude (~/mjarvis) y reinicia el servicio si hace falta. (Es linux/desplegar.sh, para Windows.)
# Uso:  desplegar.cmd        -> muestra qué cambiaría (simulación)
#       desplegar.cmd -y     -> aplica
# Reglas: nunca borra nada allá y no toca lo que sube el usuario (conocimiento/, documentos/, web/medios/,
# aprendido.json, desactivadas.json, grafos generados).
param([switch]$y)
. "$PSScriptRoot\sync.ps1"
Set-Location $Raiz

# Lo que se aprueba en Control (palabras del filtro, variantes de frases) se edita en la Latitude: antes de enviar,
# se trae lo que allá sea más nuevo para no pisarlo.
$traidos = Receive-SiMasNuevo 'mjarvis/comportamiento' @('reacciones.json', 'personalidad.json') (Join-Path $Raiz 'comportamiento')
foreach ($t in $traidos) { Write-Host "(traído de la Latitude) comportamiento/$t" }

$cambios = @()
$cambios += Send-Cambios -Origen 'servidor'       -Destino 'mjarvis/servidor'       -Aplicar:$y | ForEach-Object { [pscustomobject]@{ Rel = "servidor/$($_.Rel)"; Tipo = $_.Tipo } }
$cambios += Send-Cambios -Origen 'web'            -Destino 'mjarvis/web'            -Excluir 'medios', 'graph.json', 'trato.json' -Aplicar:$y | ForEach-Object { [pscustomobject]@{ Rel = "web/$($_.Rel)"; Tipo = $_.Tipo } }
$cambios += Send-Cambios -Origen 'comportamiento' -Destino 'mjarvis/comportamiento' -Excluir 'aprendido.json', 'recetas.json', 'propuestas.json', '_respaldos' -Aplicar:$y | ForEach-Object { [pscustomobject]@{ Rel = "comportamiento/$($_.Rel)"; Tipo = $_.Tipo } }
$cambios += Send-Cambios -Origen 'grafo'          -Destino 'mjarvis/grafo'          -Excluir 'graph.json' -Aplicar:$y | ForEach-Object { [pscustomobject]@{ Rel = "grafo/$($_.Rel)"; Tipo = $_.Tipo } }
$cambios += Send-Cambios -Origen 'latitude'       -Destino 'mjarvis'                -Solo 'm-jarvis.sh', 'wifi-propia.sh' -Aplicar:$y | ForEach-Object { [pscustomobject]@{ Rel = $_.Rel; Tipo = $_.Tipo } }

if (-not $cambios.Count) { Write-Host 'Nada que enviar: la Latitude ya está al día.'; exit 0 }
$cambios | ForEach-Object { Write-Host ("{0,-9} {1}" -f $_.Tipo, $_.Rel) }
if (-not $y) { Write-Host "`n(simulación) usa  desplegar.cmd -y  para aplicar."; exit 0 }

# Los .sh de la Latitude tienen que seguir siendo ejecutables (el lanzador del escritorio los llama directo).
if ($cambios | Where-Object { $_.Rel -like '*.sh' }) { Invoke-Latitude 'chmod +x ~/mjarvis/*.sh' | Out-Null }

# Reiniciar solo si cambió el servidor o su configuración; corta la pregunta en curso.
if ($cambios | Where-Object { $_.Rel -like 'servidor/*' -or $_.Rel -like 'comportamiento/*' }) {
    Invoke-Latitude 'systemctl --user restart mjarvis-web' | Out-Null
    Write-Host 'Servicio mjarvis-web reiniciado.'
} else { Write-Host 'Solo cambiaron archivos web: recarga la página, no hizo falta reiniciar.' }
