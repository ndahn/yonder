# Updating the Template

> Note: If you're not me you can probably skip the first two steps, the template will already be included.

1. Get [pybabel](https://babel.pocoo.org):
```bash
pip install Babel
```

2. Extract catalog:
```bash
# Two variants: µ(msgid) and µ(msgid, ctx)
pybabel.exe extract --keyword=µ:1,1t --keyword=µ:1,2c,2t --sort-by-file --add-location=file --input-dirs=../../yonder/gui --output-file=template.pot 
```

# Updating a Localization

3. Merge the updated template with your localization file
```bash
pybabel update --domain=yonder --input-file=template.pot --output-dir=.
```

4. Search and translate any lines with an empty `msgid` (i.e. "").
5. Compile your translated file as follows:
```bash
pybabel.exe compile --domain=yonder --locale=<lang> --directory=.
```

# Creating a new Localization

3. Run the following command to create your translation file (`<lang>` should be an ISO639 country code):
```bash
pybabel.exe init --domain=yonder --locale=<lang> --input-file=template.pot
```

5. Compile your translations:
```bash
pybabel.exe compile --domain=yonder --locale=<lang> --directory=.
```

6. Add an entry in the `_languages` dict in `yonder/gui/localization.py`.
7. TEST IT! Then make a pull request on github: https://github.com/ndahn/yonder/
