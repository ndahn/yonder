@echo off
CALL "%userprofile%\miniforge3\Scripts\activate.bat"
CALL conda activate yonder
pip install pyinstaller

REM "=== RUNNING PYINSTALLER ==="
IF EXIST dist RMDIR /S /Q dist
pyinstaller banks_of_yonder.py --onefile --icon=yonder.ico

REM "=== COPYING ADDITIONAL FILES ==="
COPY LICENSE dist\
COPY README.md dist\
REM COPY icon.ico dist\
ROBOCOPY resources dist\resources /E
REM ROBOCOPY docs dist\docs