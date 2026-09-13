<#
.SYNOPSIS
    Converts a source yaml (states/switches as dicts of groups) into a flat
    yaml (states/switches as lists) matching the tracker's expected format.

.PARAMETER SourcePath
    Path to the source yaml file.

.PARAMETER OutputPath
    Path to write the converted yaml file.

.EXAMPLE
    .\extract_gamesyncs.ps1 -SourcePath source.yaml -OutputPath tracker.yaml
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

# requires the powershell-yaml module for parsing/emitting yaml
if (-not (Get-Module -ListAvailable -Name powershell-yaml)) {
    Install-Module -Name powershell-yaml -Scope CurrentUser -Force
}
Import-Module powershell-yaml

$source = ConvertFrom-Yaml (Get-Content -Path $SourcePath -Raw)

# rtpcs are already a flat list, keep as-is
$rtpcs = @($source.rtpcs)

# states/switches are dicts of group -> list of names, flatten into one list
function Flatten-GroupDict {
    param($dict)
    $result = @()
    if ($null -eq $dict) { return $result }
    foreach ($key in $dict.Keys) {
        $result += @($dict[$key])
    }
    return $result
}

$states = Flatten-GroupDict $source.states
$switches = Flatten-GroupDict $source.switches

$output = [ordered]@{
    rtpcs    = $rtpcs
    states   = $states
    switches = $switches
}

ConvertTo-Yaml $output -Options UseSequenceFlowStyle | Set-Content -Path $OutputPath -Encoding utf8

Write-Host "Converted '$SourcePath' -> '$OutputPath'"