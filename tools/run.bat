@echo off
rem Starts Before the Thaw. Extra arguments go to the engine (e.g. -windowed -width 1280 -height 720)
setlocal
call "%~dp0_common.bat" || exit /b 1
if not exist "%ROOT%\engine\xash3d.exe" (echo engine not found - run tools\build_engine.bat & exit /b 1)
set "XASH3D_BASEDIR=%ROOT%"
if exist "%ROOT%\engine\extras.pk3" set "XASH3D_EXTRAS_PAK1=%ROOT%\engine\extras.pk3"
cd /d "%ROOT%"
"%ROOT%\engine\xash3d.exe" -game game -console +map btt_house %*
