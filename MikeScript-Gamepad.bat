@echo off
REM Launch the MikeScript Gamepad app (double-click me).
setlocal
call :find_pyw
if not defined PY ( echo Could not find Python. Install from https://python.org & pause & exit /b 1 )
start "" "%PY%" "%~dp0app\gui.py"
exit /b

:find_pyw
REM Prefer pythonw.exe (no console window) but fall back to python.exe.
set "PY="
if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" & goto :eof
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"  set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"  & goto :eof
where pythonw >nul 2>nul && ( set "PY=pythonw" & goto :eof )
where python  >nul 2>nul && ( set "PY=python"  & goto :eof )
goto :eof
