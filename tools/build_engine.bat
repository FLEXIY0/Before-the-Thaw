@echo off
rem Builds Xash3D FWGS (32-bit, the Windows default) into engine\ and the game
rem code (HLSDK-portable) into game\dlls + game\cl_dlls.
rem Needs: Git, Python 3, CMake, Visual Studio 2019/2022 and the SDL2 development
rem package for Visual Studio (https://libsdl.org). Set SDL2_DIR to it, e.g.
rem   set SDL2_DIR=C:\libs\SDL2-2.30.0
setlocal
call "%~dp0_common.bat" || exit /b 1
if "%SDL2_DIR%"=="" (echo Set SDL2_DIR to the SDL2 VC development package & exit /b 1)
call :fetch "%XASH_URL%" "%XASH_REF%" "%SRC%\xash3d-fwgs" || exit /b 1
pushd "%SRC%\xash3d-fwgs"
python waf configure -T release --sdl2="%SDL2_DIR%" --gamedir=game || (popd & exit /b 1)
python waf build || (popd & exit /b 1)
python waf install --destdir="%ROOT%\engine" || (popd & exit /b 1)
popd
copy /y "%SDL2_DIR%\lib\x86\SDL2.dll" "%ROOT%\engine\" >nul
call :fetch "%HLSDK_URL%" "%HLSDK_REF%" "%SRC%\hlsdk-portable" || exit /b 1
cmake -S "%SRC%\hlsdk-portable" -B "%SRC%\hlsdk-portable\build" -A Win32 -DGAMEDIR=game -DCMAKE_INSTALL_PREFIX="%ROOT%" || exit /b 1
cmake --build "%SRC%\hlsdk-portable\build" --config Release --target install || exit /b 1
echo engine in engine\, game libraries in game\dlls and game\cl_dlls
exit /b 0

:fetch
if not exist "%~3\.git" git clone "%~1" "%~3" || exit /b 1
git -C "%~3" fetch --tags origin || exit /b 1
git -C "%~3" checkout -q "%~2" || exit /b 1
git -C "%~3" submodule update --init --recursive
exit /b %errorlevel%
