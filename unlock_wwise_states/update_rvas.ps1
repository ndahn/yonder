# run-mapper.ps1
# Usage: .\run-mapper.ps1 -Profile <toml> -Exe <exe> -Output <yaml>

param(
    [Parameter(Mandatory)] [string] $Profile,
    [Parameter(Mandatory)] [string] $Exe,
    [Parameter(Mandatory)] [string] $Output
)

$raw = & ".\binary-mapper.exe" map --profile $Profile --exe $Exe --output rust 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Error "binary-mapper failed (exit $LASTEXITCODE):`n$raw"
    exit $LASTEXITCODE
}

# match all NAME: 0xVALUE, occurrences anywhere in the string
$yaml = [regex]::Matches($raw, '([A-Z0-9_]+):\s+(0x[0-9a-fA-F]+),') `
    | ForEach-Object { "$($_.Groups[1].Value): $($_.Groups[2].Value)" }

if (-not $yaml) {
    Write-Error "No RVA entries found. Raw output:`n$raw"
    exit 1
}

$yaml | Set-Content -Encoding UTF8 -Path $Output
Write-Host "Written $($yaml.Count) entr$(if ($yaml.Count -eq 1){'y'}else{'ies'}) to $Output"