@echo off
title MikeScript Gamepad - Setup
echo(
echo ===========================================================
echo    MikeScript Gamepad - one-time setup
echo    This installs Python, the ViGEmBus driver, and the
echo    needed packages. Click "Yes" on any security prompts.
echo ===========================================================
echo(

REM --- 1) Python -------------------------------------------------------------
call :find_python
if not defined PY (
  echo Installing Python 3.12 ...
  winget install --id Python.Python.3.12 -e --scope user --accept-source-agreements --accept-package-agreements
  call :find_python
)
if not defined PY (
  echo(
  echo  Could not find or install Python automatically.
  echo  Please install it from https://python.org  ^(tick "Add Python to PATH"^)
  echo  and run this Install again.
  echo(
  pause & exit /b 1
)
echo Using Python: %PY%
echo(

REM --- 2) Python packages ----------------------------------------------------
echo Installing packages ^(pygame, vgamepad^) ...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r "%~dp0app\requirements.txt"
echo(

REM --- 3) ViGEmBus driver (the virtual Xbox controller) ----------------------
echo Installing the ViGEmBus driver ^(a Windows prompt may pop up - click Yes^) ...
winget install --id ViGEm.ViGEmBus -e --accept-source-agreements --accept-package-agreements
echo(

echo ===========================================================
echo    All set!  Double-click  MikeScript-Gamepad.bat  to start.
echo ===========================================================
pause
exit /b

:find_python
set "PY="
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe" & goto :eof
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe" & goto :eof
where py >nul 2>nul && ( set "PY=py" & goto :eof )
where python >nul 2>nul && ( set "PY=python" & goto :eof )
goto :eof
