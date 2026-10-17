@echo off
rem Bake the lighting of scene.blend for the real-time site (web3d\assets). Hollow Oak: 15 minutes on an RTX 4050 laptop.
rem Blender: set BLENDER=<path to blender.exe>, or have blender on PATH.
cd /d "%~dp0"
if "%BLENDER%"=="" set BLENDER=blender
if not exist renders mkdir renders
"%BLENDER%" -b scene.blend -P blender\bake.py -- --samples 256 > renders\bake.log 2>&1
