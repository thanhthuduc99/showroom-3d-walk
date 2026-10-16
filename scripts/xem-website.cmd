@echo off
rem Open the site on this machine: local server + browser. Close this window to stop the server.
cd /d "%~dp0"
start "" http://127.0.0.1:8770/web/index.html
python tools\serve.py 8770
