& "$env:USERPROFILE\miniforge3\Scripts\activate.ps1"
conda activate yonder
pip install pyinstaller

# === RUNNING PYINSTALLER ===
if (Test-Path dist) { Remove-Item dist -Recurse -Force }
pyinstaller banks_of_yonder.py --onefile --icon=yonder.ico

# === COPYING ADDITIONAL FILES ===
Copy-Item LICENSE dist\
Copy-Item README.md dist\
# Copy-Item icon.ico dist\
robocopy resources dist\resources /E
# robocopy docs dist\docs