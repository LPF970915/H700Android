#requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$template = Join-Path $root 'out/rgsp-single-card-20260911/single-card-gpt-template.img'
$expectedSerial = '000000001539'
$expectedSize = 62239277056L

$matches = @(Get-Disk | Where-Object {
    $_.FriendlyName -eq 'Generic MassStorageClass' -and
    $_.SerialNumber -eq $expectedSerial -and
    $_.Size -eq $expectedSize -and
    $_.BusType -eq 'USB'
})
if ($matches.Count -ne 1) {
    throw "Expected exactly one matching target card, found $($matches.Count)."
}

if (Get-Volume -DriveLetter F -ErrorAction SilentlyContinue) {
    & mountvol F: /p
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to remove F: mount point.'
    }
}

if (Test-Path -LiteralPath $template -PathType Leaf) {
    $resolvedTemplate = (Resolve-Path -LiteralPath $template).Path
    if (-not $resolvedTemplate.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Unexpected cleanup target: $resolvedTemplate"
    }
    Remove-Item -LiteralPath $resolvedTemplate -Force
}

[pscustomobject]@{
    TargetDisk = $matches[0].Number
    TargetSerial = $matches[0].SerialNumber
    MountFRemoved = ($null -eq (Get-Volume -DriveLetter F -ErrorAction SilentlyContinue))
    TemplateExists = (Test-Path -LiteralPath $template)
    FreeGiB = [math]::Round((Get-PSDrive D).Free / 1GB, 1)
} | Format-List
