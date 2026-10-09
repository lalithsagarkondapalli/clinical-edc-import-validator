<#
.SYNOPSIS
    Scheduled-job wrapper for one clinical data import run.

.DESCRIPTION
    Runs the Python import, verifies the audit trail, runs the SQL reconciliation,
    and writes a one-line status to a job log. Intended for Windows Task Scheduler
    (or any scheduler) so an unattended transfer either completes with evidence or
    fails loudly with a non-zero exit code.

.EXAMPLE
    ./scripts/Invoke-StudyImport.ps1 -Spec specs/CARD301_transfer_spec.yaml -OutDir out

.NOTES
    Exit codes: 0 success | 2 reconciliation/XSD/audit failure | 3 error discrepancies with -FailOnError
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [ValidateScript({ Test-Path $_ -PathType Leaf })] [string] $Spec,
    [string] $OutDir = "out",
    [string] $Python = "python",
    [string] $RunDate,
    [switch] $FailOnError
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repo   = Split-Path -Parent $PSScriptRoot
$Spec   = (Resolve-Path $Spec).Path                       # absolute, so Push-Location can't break paths
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
$runId  = "{0}_{1}" -f ([IO.Path]::GetFileNameWithoutExtension($Spec)), (Get-Date -AsUTC -Format "yyyyMMddTHHmmssZ")
$jobLog = Join-Path $OutDir "job_history.log"

function Write-JobLog([string] $Status, [string] $Detail) {
    $line = "{0}`t{1}`t{2}`t{3}`t{4}" -f (Get-Date -AsUTC -Format o), ([Environment]::UserName), $runId, $Status, $Detail
    Add-Content -Path $jobLog -Value $line
    Write-Host $line
}

Push-Location $repo
try {
    $runArgs = @("-m", "edcimport", "run", "--spec", $Spec, "--out", $OutDir, "--run-id", $runId)
    if ($RunDate)     { $runArgs += @("--run-date", $RunDate) }
    if ($FailOnError) { $runArgs += "--fail-on-error" }

    & $Python @runArgs
    $importExit = $LASTEXITCODE
    $runDir = Join-Path $OutDir $runId

    if (-not (Test-Path (Join-Path $runDir "run_manifest.json"))) {
        Write-JobLog "FAIL" "no run manifest produced (exit $importExit)"; exit 2
    }

    & $Python -m edcimport verify-audit (Join-Path $runDir "audit_trail.jsonl")
    if ($LASTEXITCODE -ne 0) { Write-JobLog "FAIL" "audit trail verification failed"; exit 2 }

    & $Python -m edcimport load-staging $runDir
    if ($LASTEXITCODE -ne 0) { Write-JobLog "FAIL" "SQL reconciliation failed"; exit 2 }

    $recon = Import-Csv (Join-Path $runDir "reconciliation.csv")
    $summary = ($recon | ForEach-Object { "$($_.dataset)=$($_.accepted)/$($_.source_records)" }) -join " "
    $errors = @(Import-Csv (Join-Path $runDir "discrepancies.csv") | Where-Object severity -eq "error").Count

    if ($importExit -ne 0) { Write-JobLog "FAIL" "import exit $importExit; $summary; errors=$errors"; exit $importExit }
    Write-JobLog "PASS" "$summary; errors=$errors (see discrepancies.csv)"
    exit 0
}
catch {
    Write-JobLog "FAIL" $_.Exception.Message
    exit 2
}
finally {
    Pop-Location
}
