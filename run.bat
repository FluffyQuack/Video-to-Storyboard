@echo off
REM ===================================================================
REM  run.bat - Extract frames from a video, then build a storyboard.
REM
REM  Usage:
REM     run.bat "path\to\video.mp4" [keyframe|diff] [single|pairs] [audio|noaudio]
REM
REM  Arg 2 (mode)   defaults to "keyframe" - which frames to detect.
REM  Arg 3 (layout) defaults to "single"   - "pairs" puts the first and last
REM                frame of each cut side by side with an arrow between them.
REM  Arg 4 (audio)  defaults to "audio"    - "noaudio" skips audio extraction.
REM ===================================================================

setlocal

REM Make sure ffmpeg/ffprobe are reachable.
set "PATH=H:\apps\Video\ffmpeg\bin;%PATH%"

if "%~1"=="" (
    echo Usage: run.bat "path\to\video.mp4" [keyframe^|diff] [single^|pairs] [audio^|noaudio]
    pause
    exit /b 1
)

set "VIDEO=%~1"
set "MODE=%~2"
if "%MODE%"=="" set "MODE=keyframe"
set "LAYOUT=%~3"
if "%LAYOUT%"=="" set "LAYOUT=single"
set "PAIRSFLAG="
if /i "%LAYOUT%"=="pairs" set "PAIRSFLAG=--pairs"
set "AUDIO=%~4"
if "%AUDIO%"=="" set "AUDIO=audio"
set "AUDIOFLAG=--audio"
if /i "%AUDIO%"=="noaudio" set "AUDIOFLAG=--no-audio"

REM Folder created by ExtractKeyframes.py = <video dir>\<YYYY-MM-DD>-<name>.
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "TODAY=%%i"
set "OUTDIR=%~dp1%TODAY%-%~n1"

echo.
echo === Step 1: Extracting frames (%MODE% mode, %AUDIO%) ===
python "%~dp0ExtractKeyframes.py" "%VIDEO%" --mode %MODE% %AUDIOFLAG%
if errorlevel 1 (
    echo ExtractKeyframes.py failed.
    pause
    exit /b 1
)

echo.
echo === Step 2: Building storyboard (%LAYOUT% layout) ===
python "%~dp0CreateStoryboard.py" "%OUTDIR%" %PAIRSFLAG%
if errorlevel 1 (
    echo CreateStoryboard.py failed.
    pause
    exit /b 1
)

echo.
echo Done. See "%OUTDIR%\storyboard.png"
endlocal
pause