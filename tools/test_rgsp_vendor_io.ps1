$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'rgsp_vendor_io.ps1')
$script:passed = 0
function Assert-True([bool]$Condition, [string]$Name) {
    if (!$Condition) { throw "FAIL: $Name" }
}
function Test-Case([string]$Name, [scriptblock]$Body) {
    & $Body
    $script:passed++
    Write-Host "PASS: $Name"
}
function Assert-Throws([scriptblock]$Body, [string]$Pattern) {
    $caught = $false
    try { & $Body } catch {
        $caught = $true
        if ($_.Exception.Message -notmatch $Pattern) { throw "Unexpected failure: $_" }
    }
    if (!$caught) { throw 'Expected rejection did not occur.' }
}
function New-Memory([string]$Text) {
    return ,([IO.MemoryStream]::new([Text.Encoding]::ASCII.GetBytes($Text)))
}
function Text-Of([IO.MemoryStream]$Stream) { return [Text.Encoding]::ASCII.GetString($Stream.ToArray()) }
Add-Type -TypeDefinition @'
using System;
using System.IO;
public class RgspFaultStream : MemoryStream {
    public int Writes = 0;
    public string Fault;
    public RgspFaultStream(byte[] initial, string fault) : base(initial) { Fault = fault; }
    public override void Write(byte[] buffer, int offset, int count) {
        Writes++;
        if (Fault == "always" || (Fault == "once" && Writes == 1)) {
            base.Write(buffer, offset, Math.Min(2, count));
            throw new IOException("injected partial write");
        }
        base.Write(buffer, offset, count);
        if (Fault == "corrupt" && Writes == 1) {
            Position--;
            base.WriteByte(255);
        }
    }
}
'@
$old = New-Memory 'OLD!'
$new = New-Memory 'NEW!'
try {
    $oldSha = Get-RgspRangeHash $old 0 4
    $newSha = Get-RgspRangeHash $new 0 4
    Test-Case 'fresh preimage accepted without writes' {
        $disk = [RgspFaultStream]::new([Text.Encoding]::ASCII.GetBytes('PREFIXOLD!SUFFIX'), '')
        try {
            Assert-RgspRangePreimage $disk 6 4 $oldSha
            Assert-True ($disk.Writes -eq 0) 'read-only preimage check'
        } finally { $disk.Dispose() }
    }
    Test-Case 'changed preimage rejected before transaction writes' {
        $disk = [RgspFaultStream]::new([Text.Encoding]::ASCII.GetBytes('PREFIXNEW!SUFFIX'), '')
        try {
            Assert-Throws {
                Assert-RgspRangePreimage $disk 6 4 $oldSha
                Invoke-RgspVendorTransaction $disk $new $old 6 4 $newSha $oldSha
            } 'preimage differs'
            Assert-True ($disk.Writes -eq 0) 'zero writes for changed live bytes'
        } finally { $disk.Dispose() }
    }
    Test-Case 'verified write preserves both adjacent regions' {
        $disk = New-Memory 'PREFIXOLD!SUFFIX'
        try {
            Invoke-RgspVendorTransaction $disk $new $old 6 4 $newSha $oldSha
            Assert-True ((Text-Of $disk) -ceq 'PREFIXNEW!SUFFIX') 'bounded write'
        } finally { $disk.Dispose() }
    }
    foreach ($fault in @('once', 'corrupt')) {
        Test-Case "$fault failure restores the original region" {
            $disk = [RgspFaultStream]::new([Text.Encoding]::ASCII.GetBytes('PREFIXOLD!SUFFIX'), $fault)
            try {
                Assert-Throws { Invoke-RgspVendorTransaction $disk $new $old 6 4 $newSha $oldSha } 'VENDOR_ROLLBACK_VERIFIED'
                Assert-True ((Text-Of $disk) -ceq 'PREFIXOLD!SUFFIX') 'rollback and neighboring data'
                Assert-True ($disk.Writes -eq 2) 'exactly one rollback'
            } finally { $disk.Dispose() }
        }
    }
    Test-Case 'failed rollback is explicit' {
        $disk = [RgspFaultStream]::new([Text.Encoding]::ASCII.GetBytes('PREFIXOLD!SUFFIX'), 'always')
        try {
            Assert-Throws { Invoke-RgspVendorTransaction $disk $new $old 6 4 $newSha $oldSha } 'VENDOR_ROLLBACK_FAILED'
            Assert-True ($disk.Writes -eq 2) 'bounded retry'
            Assert-True ((Text-Of $disk).StartsWith('PREFIX') -and (Text-Of $disk).EndsWith('SUFFIX')) 'neighbors intact'
        } finally { $disk.Dispose() }
    }
    Test-Case 'bad input checksum makes zero writes' {
        $disk = [RgspFaultStream]::new([Text.Encoding]::ASCII.GetBytes('PREFIXOLD!SUFFIX'), '')
        try {
            Assert-Throws { Invoke-RgspVendorTransaction $disk $new $old 6 4 ('0' * 64) $oldSha } 'no writes'
            Assert-True ($disk.Writes -eq 0) 'zero disk writes'
        } finally { $disk.Dispose() }
    }
    Test-Case 'bad recovery checksum makes zero writes' {
        $disk = [RgspFaultStream]::new([Text.Encoding]::ASCII.GetBytes('PREFIXOLD!SUFFIX'), '')
        try {
            Assert-Throws { Invoke-RgspVendorTransaction $disk $new $old 6 4 $newSha ('0' * 64) } 'no writes'
            Assert-True ($disk.Writes -eq 0) 'zero disk writes'
        } finally { $disk.Dispose() }
    }
    Test-Case 'truncated image makes zero writes' {
        $short = New-Memory 'bad'
        $disk = [RgspFaultStream]::new([Text.Encoding]::ASCII.GetBytes('PREFIXOLD!SUFFIX'), '')
        try {
            Assert-Throws { Invoke-RgspVendorTransaction $disk $short $old 6 4 $newSha $oldSha } 'no writes'
            Assert-True ($disk.Writes -eq 0) 'zero disk writes'
        } finally { $disk.Dispose(); $short.Dispose() }
    }
    Test-Case 'hash and copy bounds reject invalid offsets and EOF' {
        Assert-Throws { Get-RgspRangeHash $old 0 5 } 'EOF'
        Assert-Throws { Get-RgspRangeHash $old -1 4 } 'Invalid'
        Assert-Throws { Copy-RgspRange $new $old 0 -1 4 } 'Invalid'
    }
} finally { $old.Dispose(); $new.Dispose() }

$diskInfo = [pscustomobject]@{
    BusType = 'USB'; Size = 125069950976L; PartitionStyle = 'GPT'
    IsBoot = $false; IsSystem = $false; IsOffline = $false; IsReadOnly = $false
}
$specs = @(
    @(1048576L, 268435456L, '0720745f-bbfb-4940-bef7-8595c6f34f4b'),
    @(269484032L, 8589934592L, '096d7fa1-62e8-c242-9876-cfdd5a92b8eb'),
    @(8859418624L, 2147483648L, '6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8'),
    @(11006902272L, 17179869184L, '734716ed-e7d9-e74f-9b3e-4f1cb8d448ed'),
    @(28186771456L, 96883162624L, '324a1514-de37-6344-8d09-ed5dd8b90da2')
)
$parts = @(for ($i = 0; $i -lt 5; $i++) {
    [pscustomobject]@{ PartitionNumber = $i + 1; Offset = $specs[$i][0]; Size = $specs[$i][1]; Guid = $specs[$i][2] }
})
Test-Case 'exact TF2 geometry accepted' { Assert-RgspVendorDisk $diskInfo $parts }
foreach ($field in @('IsBoot', 'IsSystem', 'IsOffline', 'IsReadOnly')) {
    Test-Case "$field disk rejected" {
        $diskInfo.$field = $true
        try { Assert-Throws { Assert-RgspVendorDisk $diskInfo $parts } 'identity mismatch' }
        finally { $diskInfo.$field = $false }
    }
}
Test-Case 'internal drive rejected' {
    $diskInfo.BusType = 'NVMe'
    try { Assert-Throws { Assert-RgspVendorDisk $diskInfo $parts } 'identity mismatch' }
    finally { $diskInfo.BusType = 'USB' }
}
Test-Case 'wrong GUID rejected' {
    $original = $parts[2].Guid
    $parts[2].Guid = [guid]::Empty
    try { Assert-Throws { Assert-RgspVendorDisk $diskInfo $parts } 'partition 3 mismatch' }
    finally { $parts[2].Guid = $original }
}
Test-Case 'wrong vendor offset rejected' {
    $parts[2].Offset++
    try { Assert-Throws { Assert-RgspVendorDisk $diskInfo $parts } 'partition 3 mismatch' }
    finally { $parts[2].Offset-- }
}
Test-Case 'missing partition rejected' {
    Assert-Throws { Assert-RgspVendorDisk $diskInfo $parts[0..3] } 'five partitions'
}
Test-Case 'receipts cannot overwrite earlier evidence' {
    $temp = Join-Path (Join-Path $PSScriptRoot '../out') ("vendor-io-test-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temp | Out-Null
    $path = Join-Path $temp 'receipt.json'
    try {
        Write-RgspNewJson $path @{ verified = $true }
        $hash = (Get-FileHash -LiteralPath $path).Hash
        Assert-Throws { Write-RgspNewJson $path @{ overwritten = $true } } 'exist'
        Assert-True ((Get-FileHash -LiteralPath $path).Hash -eq $hash) 'original receipt preserved'
    } finally {
        Remove-Item -LiteralPath $path
        Remove-Item -LiteralPath $temp
    }
}
Test-Case 'existing boot drive letter accepted' {
    $p = [pscustomobject]@{ DriveLetter = 'R'; AccessPaths = @() }
    Assert-True ((Get-RgspBootRoot $p) -ceq 'R:\') 'letter root'
}
Test-Case 'unlettered boot volume GUID accepted' {
    $path = '\\?\Volume{f8a45f85-a78d-11f1-aadb-00e04c239987}\'
    $p = [pscustomobject]@{ DriveLetter = [char]0; AccessPaths = @($path) }
    Assert-True ((Get-RgspBootRoot $p) -ceq $path) 'GUID root'
}
Test-Case 'missing and duplicate boot GUID paths rejected' {
    $path = '\\?\Volume{f8a45f85-a78d-11f1-aadb-00e04c239987}\'
    foreach ($paths in @(@(), @($path, $path), @('C:\'))) {
        $p = [pscustomobject]@{ DriveLetter = [char]0; AccessPaths = $paths }
        Assert-Throws { Get-RgspBootRoot $p } 'exactly one'
    }
}
Test-Case 'boot recovery checks size hash and one-shot marker' {
    $temp = Join-Path (Join-Path $PSScriptRoot '../out') ("boot-gate-test-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temp | Out-Null
    $root = (Resolve-Path $temp).Path + '\'
    $image = $root + 'rgsp-linux-boot-original.img'
    $marker = $root + 'RGSP_ANDROID_TRY.ONCE'
    try {
        $stream = [IO.File]::Open($image, 'CreateNew', 'ReadWrite', 'None')
        try { $stream.SetLength(67108864L) } finally { $stream.Dispose() }
        $sha = (Get-FileHash -LiteralPath $image).Hash.ToLowerInvariant()
        Assert-RgspBootRecovery $root $sha
        Assert-Throws { Assert-RgspBootRecovery $root ('0' * 64) } 'gate failed'
        New-Item -ItemType File -Path $marker | Out-Null
        Assert-Throws { Assert-RgspBootRecovery $root $sha } 'gate failed'
        Remove-Item -LiteralPath $marker
        $stream = [IO.File]::OpenWrite($image)
        try { $stream.SetLength(1) } finally { $stream.Dispose() }
        Assert-Throws { Assert-RgspBootRecovery $root $sha } 'gate failed'
    } finally {
        if (Test-Path -LiteralPath $marker) { Remove-Item -LiteralPath $marker }
        Remove-Item -LiteralPath $image
        Remove-Item -LiteralPath $temp
    }
}
Write-Host "RGSP_VENDOR_IO_TESTS_PASSED=$script:passed; no physical devices opened."
