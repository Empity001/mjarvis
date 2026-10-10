@echo off
rem ============================================================================
rem  M-Jarvis - lanzador para Windows (protocolo compartido).
rem  Busca la Latitude en la red (o por cable directo) y abre sus herramientas
rem  en el navegador predeterminado de quien lo use.
rem  No instala nada: todo lo sirve la Latitude. Este archivo se puede copiar a
rem  cualquier PC, o descargarlo desde el panel de M-Jarvis.
rem ============================================================================
setlocal EnableExtensions
title M-Jarvis
set "CARPETA=%LOCALAPPDATA%\MJarvis"
if not exist "%CARPETA%" mkdir "%CARPETA%"

rem El navegador predeterminado de este usuario: se le pregunta a Windows que programa
rem abre los enlaces http (funcion AssocQueryString; el registro a veces guarda uno viejo).
rem La orden va codificada para no pelear con las comillas; dice esto:
rem   $t = Add-Type -MemberDefinition '[DllImport("Shlwapi.dll", CharSet=CharSet.Unicode)] public static extern
rem     uint AssocQueryString(uint f, uint s, string a, string e, System.Text.StringBuilder o, ref uint n);'
rem     -Name A -Namespace W -PassThru; $b = New-Object System.Text.StringBuilder 1024; $n = [uint32]1024;
rem   if ($t::AssocQueryString(0, 2, 'http', 'open', $b, [ref]$n) -eq 0) { $b.ToString() }
rem Segun cual sea, se abre como ventana de aplicacion (familia de Chrome), como ventana
rem nueva (familia de Firefox) o simplemente como un enlace.
set "NAV="
set "TIPO=otro"
for /f "usebackq delims=" %%p in (`powershell -NoProfile -EncodedCommand JAB0ACAAPQAgAEEAZABkAC0AVAB5AHAAZQAgAC0ATQBlAG0AYgBlAHIARABlAGYAaQBuAGkAdABpAG8AbgAgACcAWwBEAGwAbABJAG0AcABvAHIAdAAoACIAUwBoAGwAdwBhAHAAaQAuAGQAbABsACIALAAgAEMAaABhAHIAUwBlAHQAPQBDAGgAYQByAFMAZQB0AC4AVQBuAGkAYwBvAGQAZQApAF0AIABwAHUAYgBsAGkAYwAgAHMAdABhAHQAaQBjACAAZQB4AHQAZQByAG4AIAB1AGkAbgB0ACAAQQBzAHMAbwBjAFEAdQBlAHIAeQBTAHQAcgBpAG4AZwAoAHUAaQBuAHQAIABmACwAIAB1AGkAbgB0ACAAcwAsACAAcwB0AHIAaQBuAGcAIABhACwAIABzAHQAcgBpAG4AZwAgAGUALAAgAFMAeQBzAHQAZQBtAC4AVABlAHgAdAAuAFMAdAByAGkAbgBnAEIAdQBpAGwAZABlAHIAIABvACwAIAByAGUAZgAgAHUAaQBuAHQAIABuACkAOwAnACAALQBOAGEAbQBlACAAQQAgAC0ATgBhAG0AZQBzAHAAYQBjAGUAIABXACAALQBQAGEAcwBzAFQAaAByAHUAOwAgACQAYgAgAD0AIABOAGUAdwAtAE8AYgBqAGUAYwB0ACAAUwB5AHMAdABlAG0ALgBUAGUAeAB0AC4AUwB0AHIAaQBuAGcAQgB1AGkAbABkAGUAcgAgADEAMAAyADQAOwAgACQAbgAgAD0AIABbAHUAaQBuAHQAMwAyAF0AMQAwADIANAA7ACAAaQBmACAAKAAkAHQAOgA6AEEAcwBzAG8AYwBRAHUAZQByAHkAUwB0AHIAaQBuAGcAKAAwACwAIAAyACwAIAAnAGgAdAB0AHAAJwAsACAAJwBvAHAAZQBuACcALAAgACQAYgAsACAAWwByAGUAZgBdACQAbgApACAALQBlAHEAIAAwACkAIAB7ACAAJABiAC4AVABvAFMAdAByAGkAbgBnACgAKQAgAH0A 2^>nul`) do set "NAV=%%p"
if defined NAV if not exist "%NAV%" set "NAV="
if defined NAV for %%n in ("%NAV%") do (
  for %%c in (chrome msedge brave vivaldi opera thorium chromium) do if /i "%%~nn"=="%%c" set "TIPO=chromium"
  for %%f in (firefox zen librewolf waterfox floorp) do if /i "%%~nn"=="%%f" set "TIPO=firefox"
)

set "HOST="
if exist "%CARPETA%\direccion.txt" set /p HOST=<"%CARPETA%\direccion.txt"

:buscar
echo.
echo  Buscando a M-Jarvis...
call :probar "%HOST%"
if errorlevel 1 call :probar "ferr-latitude-5590.local"
if errorlevel 1 call :probar "10.42.0.1"
if errorlevel 1 goto preguntar
>"%CARPETA%\direccion.txt" echo %HOST%
rem La Latitude entrega su version mas reciente del lanzador; queda guardada aqui.
curl -s -m 8 -o "%CARPETA%\M-Jarvis.bat" "http://%HOST%:8080/descargas/M-Jarvis.bat" >nul 2>&1
goto menu

:preguntar
echo.
echo  No encuentro a M-Jarvis.
echo  Compruebe que la Latitude esta encendida y en la misma red que este equipo,
echo  o conectada a el con un cable de red (tarda cerca de un minuto en enlazar).
echo.
set "HOST="
set /p HOST= Escriba la direccion que muestra la Latitude (ej. 192.168.1.50) o Enter para reintentar:
goto buscar

:menu
cls
echo.
echo   M-JARVIS  -  protocolo compartido  -  conectado a %HOST%
echo   ----------------------------------------------------------------
echo.
echo     1. Panel de control   (archivos, estado, red neuronal en vivo)
echo     2. Chat con Jarvis
echo     3. Red neuronal a pantalla completa
echo     4. Chat y red neuronal juntos
echo     5. Red neuronal en el segundo monitor
echo     6. Escritorio de la Latitude (control remoto)
echo     7. Buscar a M-Jarvis otra vez
echo     S. Salir
echo.
choice /c 1234567S /n /m "  Elija una opcion: "
if errorlevel 8 exit /b
if errorlevel 7 goto rebuscar
if errorlevel 6 goto escritorio
if errorlevel 5 goto segundo
if errorlevel 4 call :abrir "/" & goto menu
if errorlevel 3 call :abrir "/grafo/" --start-fullscreen & goto menu
if errorlevel 2 call :abrir "/?vista=chat" & goto menu
call :abrir "/#control/archivos" & goto menu

:rebuscar
set "HOST="
goto buscar

:segundo
set "POS="
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; $s = [System.Windows.Forms.Screen]::AllScreens | Where-Object { -not $_.Primary } | Select-Object -First 1; if ($s) { '{0},{1}' -f $s.Bounds.X, $s.Bounds.Y }"`) do set "POS=%%p"
if not defined POS (
  echo.
  echo  No veo un segundo monitor conectado a este equipo.
  pause
  goto menu
)
rem Solo los navegadores de la familia de Chrome dejan elegir en que pantalla se abre la ventana.
if "%TIPO%"=="chromium" (
  start "" "%NAV%" --user-data-dir="%CARPETA%\mapa" --no-first-run --app="http://%HOST%:8080/grafo/" --window-position=%POS% --start-fullscreen
  goto menu
)
call :abrir "/grafo/"
echo.
echo  Su navegador no permite colocar la ventana solo: arrastrela al segundo
echo  monitor y pulse F11 para verla a pantalla completa.
pause
goto menu

:escritorio
if not exist "%USERPROFILE%\.ssh\mjarvis_ed25519" (
  echo.
  echo  Este equipo no tiene la llave de acceso remoto a la Latitude.
  echo  El control remoto solo funciona desde el equipo donde se configuro.
  pause
  goto menu
)
start "Tunel M-Jarvis - no cerrar" cmd /c ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o StrictHostKeyChecking=accept-new -i "%USERPROFILE%\.ssh\mjarvis_ed25519" -L 6080:127.0.0.1:6080 ferr@%HOST%
timeout /t 3 /nobreak >nul
call :abrir_url "http://localhost:6080/vnc.html?autoconnect=1&resize=scale&reconnect=1"
goto menu

:probar
if "%~1"=="" exit /b 1
curl -s -m 4 -o nul "http://%~1:8080/api/estado"
if errorlevel 1 exit /b 1
set "HOST=%~1"
exit /b 0

rem Abre una vista de M-Jarvis en el navegador predeterminado.
rem %1 = ruta dentro de M-Jarvis; %2 = opcion extra para los de la familia de Chrome.
:abrir
if "%TIPO%"=="chromium" (
  start "" "%NAV%" --app="http://%HOST%:8080%~1" %~2
  exit /b 0
)
call :abrir_url "http://%HOST%:8080%~1"
exit /b 0

rem Abre una direccion cualquiera: en ventana nueva si es Firefox; si no, como un enlace normal.
:abrir_url
if "%TIPO%"=="firefox" (
  start "" "%NAV%" -new-window "%~1"
) else (
  start "" "%~1"
)
exit /b 0
