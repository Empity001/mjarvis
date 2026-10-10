# Funciones comunes del flujo en Windows. Hacen lo que hacía rsync en linux/*.sh (que en Windows no existe):
# comparan cada archivo por su huella (SHA1) con lo que hay en la Latitude, y mandan solo lo que cambió, con tar por SSH.
# Nunca borran nada allá (como rsync sin --delete).
#
# Cada conexión SSH cuesta 1-3 s en Windows, así que se hacen pocas: una para ubicar a la Latitude, una para leer las huellas
# de todo, una para lo que haya que traer, y una por carpeta que tenga cambios.
$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $PSScriptRoot
$Latitude = 'mjarvis'   # el nombre de ~/.ssh/config
$script:Ip = $null
$script:HuellasDe = @{}   # carpeta base remota (mjarvis, mjarvis-prueba) -> (ruta relativa -> sha1), leída una sola vez
$script:NombreHost = (& ssh -G $Latitude | Where-Object { $_ -like 'hostname *' } | Select-Object -First 1) -replace '^hostname ', ''

function Test-Puerto22([string]$ip) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $r = $c.BeginConnect($ip, 22, $null, $null)
        $ok = $r.AsyncWaitHandle.WaitOne(1500) -and $c.Connected
        $c.Close(); return $ok
    } catch { return $false }
}

function Get-IpLatitude {
    # mDNS (el nombre .local) en Windows tarda y falla a ratos. Se prueba, en este orden: la última dirección que funcionó,
    # el nombre, los equipos vecinos de esta red y las direcciones fijas de las redes de M-Jarvis (Wi-Fi propia y cable).
    # Las que no son la guardada se comprueban entrando con la llave y la huella guardada del host (HostKeyAlias).
    if ($null -ne $script:Ip) { return $script:Ip }
    $script:Ip = ''
    $guardada = Join-Path $env:LOCALAPPDATA 'mjarvis\ip-latitude.txt'
    $anterior = if (Test-Path $guardada) { (Get-Content $guardada -Raw).Trim() } else { '' }
    if ($anterior -and (Test-Puerto22 $anterior)) { $script:Ip = $anterior; return $script:Ip }

    $candidatas = @()
    try { $candidatas += [Net.Dns]::GetHostAddresses($script:NombreHost) | Where-Object { $_.AddressFamily -eq 'InterNetwork' } | ForEach-Object { $_.IPAddressToString } } catch { }
    $candidatas += (& arp -a) | ForEach-Object { if ($_ -match '^\s+(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f]{2}-){5}[0-9a-f]{2}\s+dynamic') { $Matches[1] } }
    $candidatas += '10.42.0.1', '10.44.0.1', '10.43.0.218'
    foreach ($ip in ($candidatas | Where-Object { $_ } | Select-Object -Unique)) {
        if (-not (Test-Puerto22 $ip)) { continue }
        & ssh -o BatchMode=yes -o ConnectTimeout=5 -o "HostName=$ip" -o "HostKeyAlias=$script:NombreHost" $Latitude 'true' 2>$null
        if ($LASTEXITCODE -eq 0) {
            $script:Ip = $ip
            New-Item -ItemType Directory -Force -Path (Split-Path $guardada) | Out-Null
            Set-Content -Path $guardada -Value $ip
            break
        }
    }
    return $script:Ip
}

function Get-OpcionesSsh {
    $ip = Get-IpLatitude
    $o = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10')
    if ($ip) { $o += @('-o', "HostName=$ip", '-o', "HostKeyAlias=$script:NombreHost") }
    return $o
}

function Invoke-Latitude([string]$comando) {
    # Corre un comando en la Latitude y devuelve su salida (líneas). Falla si el comando falla.
    $salida = & ssh @(Get-OpcionesSsh) $Latitude $comando
    if ($LASTEXITCODE -ne 0) { throw "Falló en la Latitude: $comando" }
    return $salida
}

function Get-ArchivosLocales([string]$carpeta, [string[]]$excluir = @(), [string[]]$solo = @()) {
    # Los archivos de una carpeta, con su ruta relativa (con /). Una exclusión sin / vale para cualquier nivel (como en rsync).
    $base = (Resolve-Path $carpeta).Path.TrimEnd('\')
    $todos = Get-ChildItem -LiteralPath $base -Recurse -File -Force
    foreach ($f in $todos) {
        $rel = $f.FullName.Substring($base.Length + 1).Replace('\', '/')
        if ($solo.Count -and ($solo -notcontains $rel)) { continue }
        $omitir = $false
        foreach ($parte in $rel.Split('/')) { foreach ($e in (@('__pycache__', '*.pyc') + $excluir)) { if ($parte -like $e) { $omitir = $true } } }
        if (-not $omitir) { [pscustomobject]@{ Rel = $rel; Ruta = $f.FullName } }
    }
}

function Get-HuellasRemotas([string]$baseRemota) {
    # ruta relativa -> sha1 de todo lo que hay en ~/<baseRemota> (salvo lo pesado que nunca se sincroniza), en UNA conexión.
    if ($script:HuellasDe.ContainsKey($baseRemota)) { return $script:HuellasDe[$baseRemota] }
    $mapa = @{}
    $cmd = "cd ~/$baseRemota 2>/dev/null && find . \( -name venv -o -name modelos -o -name conocimiento -o -name documentos -o -name __pycache__ -o -name bench -o -name node_modules \) -prune -o -type f -print0 | xargs -0 -r sha1sum; true"
    foreach ($l in (Invoke-Latitude $cmd)) { if ($l -match '^([0-9a-f]{40})\s+\./(.+)$') { $mapa[$Matches[2]] = $Matches[1] } }
    $script:HuellasDe[$baseRemota] = $mapa
    return $mapa
}

function Send-Cambios {
    <#
      Compara ORIGEN (carpeta local) con ~/DESTINO en la Latitude y devuelve la lista de archivos que cambiaron.
      Con -Aplicar, además los envía. -Excluir: nombres o patrones que no se tocan. -Solo: únicamente esos archivos.
      DESTINO es  <base>/<subcarpeta>  (mjarvis/servidor)  o solo  <base>  (mjarvis) para archivos sueltos.
    #>
    param([string]$Origen, [string]$Destino, [string[]]$Excluir = @(), [string[]]$Solo = @(), [switch]$Aplicar)
    $base, $sub = $Destino -split '/', 2
    $remotas = Get-HuellasRemotas $base
    $prefijo = if ($sub) { "$sub/" } else { '' }
    $cambios = @()
    foreach ($f in @(Get-ArchivosLocales $Origen $Excluir $Solo)) {
        $huella = (Get-FileHash -LiteralPath $f.Ruta -Algorithm SHA1).Hash.ToLower()
        $clave = "$prefijo$($f.Rel)"
        if (-not $remotas.ContainsKey($clave)) { $cambios += [pscustomobject]@{ Rel = $f.Rel; Tipo = 'nuevo' } }
        elseif ($remotas[$clave] -ne $huella) { $cambios += [pscustomobject]@{ Rel = $f.Rel; Tipo = 'cambiado' } }
    }
    if ($Aplicar -and $cambios.Count) {
        $tmp = Join-Path $env:TEMP ('mjarvis-envio-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $tmp | Out-Null
        try {
            $lista = Join-Path $tmp 'lista.txt'
            [IO.File]::WriteAllText($lista, (($cambios.Rel -join "`n") + "`n"), (New-Object Text.UTF8Encoding($false)))
            $origenAbs = (Resolve-Path $Origen).Path.TrimEnd('\')
            # Un .cmd para que los bytes pasen de tar a ssh sin que PowerShell los toque.
            $cmd = Join-Path $tmp 'enviar.cmd'
            $opc = (Get-OpcionesSsh) -join ' '
            $linea = "tar --format gnutar -cf - -C `"$origenAbs`" -T `"$lista`" | ssh $opc $Latitude `"mkdir -p ~/$Destino && tar -xf - -C ~/$Destino`""
            [IO.File]::WriteAllText($cmd, "@echo off`r`n$linea`r`nexit /b %errorlevel%`r`n", [Text.Encoding]::ASCII)
            & cmd /c $cmd
            if ($LASTEXITCODE -ne 0) { throw "No se pudo enviar a ~/$Destino (código $LASTEXITCODE)." }
        } finally { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
    }
    return $cambios
}

function Receive-SiMasNuevo([string]$dirRemoto, [string[]]$archivos, [string]$carpetaLocal) {
    # Trae de la Latitude los archivos que allá son MÁS NUEVOS y distintos (lo que se aprueba en Control se edita allá).
    # Antes de pisar el local, se guarda una copia en _respaldos. Devuelve lo que se trajo. Una sola consulta para todos.
    $lista = ($archivos | ForEach-Object { "'$_'" }) -join ' '
    $info = Invoke-Latitude "cd ~/$dirRemoto && for f in $lista; do [ -f `"`$f`" ] && echo `"`$f `$(stat -c %Y `"`$f`") `$(sha1sum `"`$f`" | cut -c1-40)`"; done; true"
    $traidos = @()
    foreach ($linea in $info) {
        $m = [regex]::Match($linea, '^(\S+) (\d+) ([0-9a-f]{40})$'); if (-not $m.Success) { continue }
        $a = $m.Groups[1].Value; $remotoEpoch = [int64]$m.Groups[2].Value
        $ruta = Join-Path $carpetaLocal $a
        if (Test-Path -LiteralPath $ruta) {
            $huella = (Get-FileHash -LiteralPath $ruta -Algorithm SHA1).Hash.ToLower()
            $localEpoch = [int64]([DateTimeOffset](Get-Item -LiteralPath $ruta).LastWriteTimeUtc).ToUnixTimeSeconds()
            if ($huella -eq $m.Groups[3].Value -or $localEpoch -ge $remotoEpoch) { continue }
            $resp = Join-Path $carpetaLocal '_respaldos'; New-Item -ItemType Directory -Force -Path $resp | Out-Null
            Copy-Item -LiteralPath $ruta -Destination (Join-Path $resp ("$a." + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bak'))
        }
        & scp -q -p @(Get-OpcionesSsh) "${Latitude}:$dirRemoto/$a" $ruta
        if ($LASTEXITCODE -ne 0) { throw "No se pudo traer $a de la Latitude." }
        $traidos += $a
    }
    return $traidos
}
