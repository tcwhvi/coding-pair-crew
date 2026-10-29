@echo off
rem Launch Trae with a CDP debug port so send_trae.py can attach.
rem Usage: launch_trae_cdp.cmd [port] [project-path]
rem   port          default 9226
rem   project-path  optional folder to open
rem Trae must be closed first: an already running instance ignores the flag.
setlocal
set "PORT=%~1"
if "%PORT%"=="" set "PORT=9226"
set "PROJECT=%~2"

rem Trae CN.exe runs as Node when this is set, and exits without opening a window.
set "ELECTRON_RUN_AS_NODE="

set "TRAE=%TRAE_CLI%"
if "%TRAE%"=="" set "TRAE=E:\Programs\Trae CN\Trae CN.exe"
if not exist "%TRAE%" set "TRAE=%ProgramFiles%\Trae CN\Trae CN.exe"
if not exist "%TRAE%" set "TRAE=%LOCALAPPDATA%\Programs\Trae CN\Trae CN.exe"
if not exist "%TRAE%" (
  echo launch_trae_cdp: Trae CN.exe not found. Set TRAE_CLI to the full path.
  exit /b 1
)

echo launch_trae_cdp: port=%PORT% project=%PROJECT%
start "" "%TRAE%" --remote-debugging-port=%PORT% %PROJECT%
exit /b 0
