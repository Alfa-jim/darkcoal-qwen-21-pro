@echo off
cd /d "%~dp0"
echo Starting the playground at http://127.0.0.1:8766/playground.html
echo Keep this terminal open while using it. Ctrl+C stops the server.
start "" "http://127.0.0.1:8766/playground.html"
python -m http.server 8766 --bind 127.0.0.1
