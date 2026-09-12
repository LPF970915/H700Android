$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'rgsp_single_card_io.ps1')
$passed = 0
function Assert-True($Value, $Name) { if (!$Value) { throw "FAIL $Name" } }
function Reject([scriptblock]$Action, $Name) {
    $thrown = $false
    try { & $Action } catch { $thrown = $true }
    Assert-True $thrown $Name
}
$source = [IO.MemoryStream]::new([Text.Encoding]::ASCII.GetBytes('NEW!'))
$dest = [IO.MemoryStream]::new([Text.Encoding]::ASCII.GetBytes('PREFIXOLD!SUFFIX'))
try {
    $hash = Invoke-RgspSingleCardRange $source $dest 6 4 {} -Copy
    Assert-True ([Text.Encoding]::ASCII.GetString($dest.ToArray()) -ceq 'PREFIXNEW!SUFFIX') 'bounded write'
    $passed++
    Assert-True ((Invoke-RgspSingleCardRange $dest $null 6 4 {}) -eq $hash) 'readback hash'
    $passed++
    Reject { Invoke-RgspSingleCardRange $source $null 0 8 {} } 'truncated source'
    $passed++
    $message = ''
    try { Invoke-RgspSingleCardRange $source $null 0 8589934592L {} }
    catch { $message = $_.Exception.Message }
    Assert-True ($message -eq 'Unexpected EOF.') '8GiB length uses 64-bit arithmetic'
    $passed++
    Reject { Invoke-RgspSingleCardRange $source $dest -1 4 {} -Copy } 'negative offset'
    $passed++
    Reject { Invoke-RgspSingleCardRange $source $null 0 4 {} -Copy } 'missing destination'
    $passed++
} finally { $source.Dispose(); $dest.Dispose() }
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$manifest = Get-Content (Join-Path $root 'out/rgsp-single-card-v2-20260911/manifest.json') -Raw | ConvertFrom-Json
Assert-RgspSingleCardRecipe $manifest $root
$passed++
$manifest.ranges[1].offset++
Reject { Assert-RgspSingleCardRecipe $manifest $root } 'offset corruption'
$passed++
$manifest.ranges[1].offset--
$manifest.ranges[1].path = 'C:\Windows\system.raw.img'
Reject { Assert-RgspSingleCardRecipe $manifest $root } 'outside path'
$passed++
$disk = [pscustomobject]@{
    BusType='USB'; SerialNumber='000000001539'; Size=62239277056L
    IsBoot=$false; IsSystem=$false; IsReadOnly=$false; IsOffline=$true
}
$parts = @($manifest.partitions | ForEach-Object {
    [pscustomobject]@{PartitionNumber=$_.number; Offset=$_.start; Size=($_.end_exclusive - $_.start)}
})
Assert-RgspSingleCardTarget $disk $parts
$passed++
$disk.IsOffline = $false
Assert-RgspSingleCardTarget $disk $parts
$passed++
$disk.IsOffline = $true
$disk.Size = 0
Reject { Assert-RgspSingleCardTarget $disk $parts } 'empty reader slot'
$passed++
$disk.Size = 62239277056L
$disk.SerialNumber = 'wrong'
Reject { Assert-RgspSingleCardTarget $disk $parts } 'wrong serial'
$passed++
$disk.SerialNumber = '000000001539'
$disk.IsSystem = $true
Reject { Assert-RgspSingleCardTarget $disk $parts } 'system disk'
$passed++
"PASS $passed single-card IO tests; no physical device opened."
