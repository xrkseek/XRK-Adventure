@echo off
setlocal
cd /d "%~dp0"

set "GODOT="
if exist "%USERPROFILE%\Tools\Godot\Godot_v4.7.1-stable_win64.exe" (
  set "GODOT=%USERPROFILE%\Tools\Godot\Godot_v4.7.1-stable_win64.exe"
)
if not defined GODOT if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\godot.exe" (
  set "GODOT=%LOCALAPPDATA%\Microsoft\WinGet\Links\godot.exe"
)
if not defined GODOT (
  for /f "delims=" %%i in ('where godot 2^>nul') do (
    set "GODOT=%%i"
    goto :found
  )
)

:found
if not defined GODOT (
  echo [ERROR] Godot not found.
  echo Install Godot 4.7+ or edit this bat with your Godot exe path.
  pause
  exit /b 1
)

echo Launching: "%GODOT%"
echo Project:   "%CD%"
start "" "%GODOT%" --path "%CD%"
exit /b 0
