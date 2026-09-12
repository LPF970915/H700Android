#requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$out = (Resolve-Path '.\out\rgsp-single-card-v2-20260911').Path
$log = Join-Path $out 'written-gpt-check.txt'
try {
    Set-Disk -Number 3 -IsOffline:$false
    Update-Disk -Number 3
    Start-Sleep -Seconds 3
    $d = Get-Disk -Number 3
    $lines = @(
        "DISK Number=$($d.Number) Size=$($d.Size) Serial=$($d.SerialNumber) Offline=$($d.IsOffline) Style=$($d.PartitionStyle) Status=$($d.OperationalStatus)"
    )
    foreach ($p in @(Get-Partition -DiskNumber 3 | Sort-Object PartitionNumber)) {
        $lines += "PART $($p.PartitionNumber) Offset=$($p.Offset) Size=$($p.Size) Type=$($p.Type) GptType=$($p.GptType) Guid=$($p.Guid)"
    }
    Set-Content -LiteralPath $log -Value $lines
} catch {
    Set-Content -LiteralPath $log -Value ("GPT_CHECK_FAILED " + $_.Exception.ToString())
    throw
}
