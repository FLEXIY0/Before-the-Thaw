@echo off
rem Compiles development\maps_src\<map>.map into game\maps\<map>.bsp
rem usage: tools\compile.bat [mapname] [fast^|full]     (default: btt_house full)
setlocal
call "%~dp0_common.bat" || exit /b 1
set "MAP=%~1"
if "%MAP%"=="" set "MAP=btt_house"
set "MODE=%~2"
if "%MODE%"=="" set "MODE=full"
if "%SDHLT_DIR%"=="" set "SDHLT_DIR=%TOOLS%\sdhlt"
set "SUF="
if exist "%SDHLT_DIR%\sdHLCSG_x64.exe" set "SUF=_x64"
if not exist "%SDHLT_DIR%\sdHLCSG%SUF%.exe" (echo SDHLT not found in %SDHLT_DIR% - run tools\build_tools.bat & exit /b 1)
set "WORK=%ROOT%\development\build"
if not exist "%WORK%" mkdir "%WORK%"
if not exist "%ROOT%\game\maps" mkdir "%ROOT%\game\maps"
copy /y "%ROOT%\development\maps_src\%MAP%.map" "%WORK%\" >nul
copy /y "%ROOT%\game\textures\*.wad" "%WORK%\" >nul
copy /y "%SDHLT_DIR%\sdhlt.wad" "%WORK%\" >nul
pushd "%WORK%"
if /i "%MODE%"=="fast" (set "VIS=-fast" & set "RAD=-fast -bounce 2") else (set "VIS=-full" & set "RAD=-extra -bounce 8 -smooth 50")
"%SDHLT_DIR%\sdHLCSG%SUF%.exe" -wadinclude btt_house -wadautodetect "%MAP%" || goto :fail
"%SDHLT_DIR%\sdHLBSP%SUF%.exe" "%MAP%" || goto :fail
"%SDHLT_DIR%\sdHLVIS%SUF%.exe" %VIS% "%MAP%" || goto :fail
"%SDHLT_DIR%\sdHLRAD%SUF%.exe" %RAD% -chop 32 -texchop 16 "%MAP%" || goto :fail
copy /y "%MAP%.bsp" "%ROOT%\game\maps\" >nul
popd
echo OK: game\maps\%MAP%.bsp
exit /b 0
:fail
popd
echo Compile FAILED - see %WORK%\%MAP%.log
exit /b 1
