@echo off
rem Builds the SDHLT map compilers into tools\sdhlt\
rem Needs: Git, CMake 3.20+, Visual Studio 2019/2022 (Desktop C++).
setlocal
call "%~dp0_common.bat" || exit /b 1
call :fetch "%SDHLT_URL%" "%SDHLT_REF%" "%SRC%\SDHLT" || exit /b 1
cmake -S "%SRC%\SDHLT" -B "%SRC%\SDHLT\build" -A x64 || exit /b 1
cmake --build "%SRC%\SDHLT\build" --config Release || exit /b 1
if not exist "%TOOLS%\sdhlt" mkdir "%TOOLS%\sdhlt"
copy /y "%SRC%\SDHLT\tools\*.exe" "%TOOLS%\sdhlt\" >nul
copy /y "%SRC%\SDHLT\tools\sdhlt.wad" "%TOOLS%\sdhlt\" >nul
copy /y "%SRC%\SDHLT\tools\sdhlt.fgd" "%TOOLS%\sdhlt\" >nul
echo SDHLT ready in tools\sdhlt
exit /b 0

:fetch
if not exist "%~3\.git" git clone "%~1" "%~3" || exit /b 1
git -C "%~3" fetch --tags origin || exit /b 1
git -C "%~3" checkout -q "%~2" || exit /b 1
git -C "%~3" submodule update --init --recursive
exit /b %errorlevel%
