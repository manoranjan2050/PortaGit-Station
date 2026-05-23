@echo off
echo Building PortaGit Station Dashboard Executable...
echo Installing PyInstaller...
pip install pyinstaller

echo Starting Build Process...
:: --onefile: Creates a single exe
:: --noconsole: Hides the black terminal window when running
:: --add-data: Includes your templates and data folders
pyinstaller --noconsole --onefile ^
    --add-data "templates;templates" ^
    --add-data "data;data" ^
    --name "PortaGit Station" ^
    app.py

echo.
echo ==================================================
echo Build Complete!
echo You can find your portable app in the 'dist' folder.
echo ==================================================
pause
