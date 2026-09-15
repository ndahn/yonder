Write-Host "Extracting AC6"
& "$PSScriptRoot.\extract_gamesyncs.ps1" -SourcePath "..\resources\gamedata\ac6\gamesyncs.json" -OutputPath dist\gamesyncs_ac6.yaml

Write-Host "Extracting ER"
& "$PSScriptRoot.\extract_gamesyncs.ps1" -SourcePath "..\resources\gamedata\er\gamesyncs.json" -OutputPath dist\gamesyncs_er.yaml

Write-Host "Extracting NR"
& "$PSScriptRoot.\extract_gamesyncs.ps1" -SourcePath "..\resources\gamedata\nr\gamesyncs.json" -OutputPath dist\gamesyncs_nr.yaml
