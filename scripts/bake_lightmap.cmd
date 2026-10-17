@echo off
rem Bake a big room (lightmap + tiling albedo, light per vertex on goods) for web3d-lightmap. HEM shop 14 x 10 m: 20 minutes on an RTX 4050 laptop.
rem Blender: set BLENDER=<path to blender.exe>, or have blender on PATH.
cd /d "%~dp0"
if "%BLENDER%"=="" set BLENDER=blender
if not exist renders mkdir renders
"%BLENDER%" -b scene.blend -P blender\bake_lightmap.py -- --samples 256 > renders\bake.log 2>&1
