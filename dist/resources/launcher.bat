@echo off
rem @NAME@ - Teil der LogisticsLab-Distribution (Windows)
rem @WHAT@

setlocal

rem Logs und Matrix-Cache im Benutzerverzeichnis, nicht im (evtl. schreibgeschuetzten) Programmverzeichnis
if "%LOGLAB_LOG_DIR%"=="" set "LOGLAB_LOG_DIR=%LOCALAPPDATA%\LogisticsLab\logs"

rem Konfiguration in confs\ neben diesem Skript (die Programme liegen in bin\)
if "%LOGLAB_CONF_DIR%"=="" set "LOGLAB_CONF_DIR=%~dp0confs"

rem -I bzw. -E -s: keine PYTHON*-Variablen, kein User-site-packages - nur das, was in der Distribution liegt
@PYTHON@ @PYARGS@ %*
exit /b %ERRORLEVEL%
