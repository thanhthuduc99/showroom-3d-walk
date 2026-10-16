@echo off
rem Render (or resume) every walk frame of scene.blend into frames\. Safe to close and run again: finished frames are skipped.
rem Blender: set BLENDER=<path to blender.exe>, or have blender on PATH. Exposure: set EXPOSURE (Hollow Oak used 1.6).
cd /d "%~dp0"
if "%BLENDER%"=="" set BLENDER=blender
if "%EXPOSURE%"=="" set EXPOSURE=1.6
if not exist renders mkdir renders
for %%f in (frames\f*.png) do if %%~zf==0 del "%%f"
"%BLENDER%" -b scene.blend -P blender\render_setup.py -a -- --exposure %EXPOSURE% >> renders\render.log 2>&1
