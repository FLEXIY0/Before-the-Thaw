@echo off
rem shared settings for the *.bat scripts
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "TOOLS=%ROOT%\tools"
set "SRC=%TOOLS%\src"
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%TOOLS%\versions.txt") do set "%%A=%%B"
exit /b 0
