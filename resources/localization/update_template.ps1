& "$env:USERPROFILE\miniforge3\Scripts\activate.ps1"
conda activate base
pip install Babel
pybabel extract --keyword=µ:1,1t --keyword=µ:1,2c,2t --output-file=template.pot --sort-by-file --input-dirs=../../yonder/gui