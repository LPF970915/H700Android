#requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$log = Join-Path $root 'out/rgsp-single-card-20260911/write-single-card-raw.log'
Set-Content -LiteralPath $log -Value ("started " + (Get-Date).ToString('o'))
try {
    & (Join-Path $PSScriptRoot 'write_rgsp_single_card_raw.ps1') -ConfirmWrite *>&1 |
        Tee-Object -FilePath $log -Append
}
catch {
    $_ | Out-String | Add-Content -LiteralPath $log
    exit 1
}
