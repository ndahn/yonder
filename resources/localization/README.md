# Updating the localization template

> Note: If you're not me you can probably skip the first two steps, the template will already be included.

1. Get [pybabel](https://babel.pocoo.org):
```bash
pip install Babel
```

2. Extract catalog:
```bash
# Two variants: µ(msgid) and µ(msgid, ctx)
pybabel.exe extract --keyword=µ:1,1t --keyword=µ:1,2c,2t --output-file=template.pot --sort-by-file --input-dirs=../../yonder/gui
```

3. Copy the `template.pot` file to `yonder.po` and translate it.

4. Compile your translations (`<lang>` should be an ISO639 country code):
```bash
pybabel.exe compile --domain=yonder --locale=<lang> --input-file=yonder.po
```

5. Verify the previous command created the file `<lang>/LC_MESSAGES/yonder.mo`.

6. Add an entry in the `_languages` dict in `yonder/gui/localization.py`. 

7. TEST IT! Then make a pull request on github: https://github.com/ndahn/yonder/
