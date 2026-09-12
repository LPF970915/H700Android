#requires -Version 7.2
$ErrorActionPreference = 'Stop'
$sourcePath = Join-Path $PSScriptRoot 'check_rgsp_fix72_runtime.ps1'
$source = Get-Content -LiteralPath $sourcePath -Raw
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Runtime checker syntax error.' }
$boundary = @($ast.EndBlock.Statements | Where-Object {
    $_ -is [Management.Automation.Language.AssignmentStatementAst] -and
    $_.Left.Extent.Text -eq '$outputDirectory'
})
if ($boundary.Count -ne 1) { throw 'Cannot isolate the offline manifest stage.' }
$prefixText = $source.Substring(0, $boundary[0].Extent.StartOffset)
# A dynamically created script block has no script file directory.
$prefixText = $prefixText.Replace('$PSScriptRoot', ("'" + $PSScriptRoot.Replace("'", "''") + "'"))
$manifestStage = [scriptblock]::Create($prefixText)
$candidate = Get-Content -LiteralPath (Join-Path $PSScriptRoot '../out/rgsp-audio-candidate-20260910/CANDIDATE_MANIFEST.json') -Raw |
    ConvertFrom-Json
$profiles = @{}
foreach ($profileName in @('Frozen', 'Codec', 'Audio')) {
    . $manifestStage -Profile $profileName
    $profiles[$profileName] = @($lines)
    $expectedCount = @{ Frozen = 17; Codec = 20; Audio = 23 }[$profileName]
    if ($lines.Count -ne $expectedCount -or @($lines | Sort-Object -Unique).Count -ne $expectedCount) {
        throw "Wrong component count or duplicates: $profileName"
    }
    Write-Host "PASS: $profileName has $expectedCount unique component checks."
}
foreach ($line in $profiles.Frozen) {
    if ($line -cnotin $profiles.Codec -or $line -cnotin $profiles.Audio) {
        throw 'An existing frozen component check was lost.'
    }
}
foreach ($line in $profiles.Codec) {
    if ($line -cnotin $profiles.Audio) { throw 'An existing codec component check was lost.' }
}
foreach ($change in $candidate.changes) {
    $expected = "$($change.after.sha256)  /vendor/$($change.path)"
    if ($expected -cnotin $profiles.Audio) { throw "Audio candidate mismatch: $($change.path)" }
}
Write-Host 'PASS: all older checks retained and audio hashes match the qualified candidate.'
Write-Host 'RGSP_RUNTIME_PROFILE_TESTS_PASSED; no serial helpers or physical devices opened.'
