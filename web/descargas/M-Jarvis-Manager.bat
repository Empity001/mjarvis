@echo off
rem M-Jarvis Manager: abre la consola de M-Jarvis como una aplicacion y busca a la Latitude donde este.
rem No instala nada. Si no la encuentra, pide su direccion (se ve en la Latitude: M-Jarvis > Compartir).
setlocal EnableExtensions
title M-Jarvis Manager
set "CARPETA=%LOCALAPPDATA%\MJarvis"
if not exist "%CARPETA%" mkdir "%CARPETA%"
set "HOST="
if exist "%CARPETA%\direccion.txt" set /p HOST=<"%CARPETA%\direccion.txt"

:buscar
echo.
echo  Buscando a M-Jarvis...
for %%h in ("%HOST%" ferr-latitude-5590.local 10.42.0.1 10.44.0.1 192.168.137.2 192.168.137.3 192.168.137.4) do (
  if not "%%~h"=="" (
    curl -s -m 3 -o nul "http://%%~h:8080/api/estado" && (set "HOST=%%~h" & goto abrir)
  )
)
echo.
echo  No encuentro a M-Jarvis. Revise que este encendida y conectada (Wi-Fi o cable).
set "HOST="
set /p HOST= Escriba su direccion (o Enter para reintentar): 
goto buscar

:abrir
>"%CARPETA%\direccion.txt" echo %HOST%
set "URL=http://%HOST%:8080/#control"
set "NAV="
for %%p in ("%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe") do (
  if exist %%p if not defined NAV set "NAV=%%~p"
)
if defined NAV (start "" "%NAV%" --app=%URL%) else (start "" %URL%)
endlocal
