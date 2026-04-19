@echo off
CALL "%userprofile%\miniforge3\Scripts\activate.bat"
CALL conda deactivate
pip install Babel

pybabel.exe extract --keyword=µ:1,1t --keyword=µ:1,2c,2t --output-file=template.pot --sort-by-file --input-dirs=../../yonder/gui
