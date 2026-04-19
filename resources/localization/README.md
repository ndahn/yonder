# Updating the localization template
1. Get `xgettext`; on windows, get it from [](https://github.com/vslavik/gettext-tools-windows)
2. Extract translation strings from `yonder/gui`

```powershell
# Windows
Get-ChildItem -Path ../../yonder/gui -Filter *.py -Recurse | ForEach-Object { Resolve-Path -relative $_.FullName } | Out-File -FilePath files.tmp -Encoding utf8
```

```bash
# Linux
find ../../yonder/gui -iname *.py > files.tmp
```

3. Create the language template
```bash
xgettext --keyword="µ:1,2c" -a -L python -o .yonder.pot --files-from=files.tmp
```
