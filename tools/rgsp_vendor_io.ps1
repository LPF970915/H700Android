# Pure stream/identity helpers. Loading this file does not open a disk.
Set-StrictMode -Version Latest

function Assert-RgspVendorDisk($Disk, $Parts) {
    if ($Disk.BusType -ne 'USB' -or $Disk.Size -ne 125069950976L -or
        $Disk.PartitionStyle -ne 'GPT' -or $Disk.IsBoot -or $Disk.IsSystem -or
        $Disk.IsOffline -or $Disk.IsReadOnly) { throw 'TF2 USB disk identity mismatch.' }
    $geometry = @(
        @(1048576L, 268435456L, '0720745f-bbfb-4940-bef7-8595c6f34f4b'),
        @(269484032L, 8589934592L, '096d7fa1-62e8-c242-9876-cfdd5a92b8eb'),
        @(8859418624L, 2147483648L, '6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8'),
        @(11006902272L, 17179869184L, '734716ed-e7d9-e74f-9b3e-4f1cb8d448ed'),
        @(28186771456L, 96883162624L, '324a1514-de37-6344-8d09-ed5dd8b90da2')
    )
    if (@($Parts).Count -ne 5) { throw 'Expected exactly five partitions.' }
    for ($i = 0; $i -lt 5; $i++) {
        if ($Parts[$i].PartitionNumber -ne $i + 1 -or
            $Parts[$i].Offset -ne $geometry[$i][0] -or
            $Parts[$i].Size -ne $geometry[$i][1] -or
            ([guid]$Parts[$i].Guid).ToString() -ne $geometry[$i][2]) {
            throw "TF2 partition $($i + 1) mismatch."
        }
    }
}

function Get-RgspRangeHash([IO.Stream]$Stream, [long]$Offset, [long]$Length) {
    if ($Offset -lt 0 -or $Length -le 0) { throw 'Invalid hash range.' }
    [void]$Stream.Seek($Offset, 'Begin')
    $buffer = New-Object byte[] (4MB)
    $hash = [Security.Cryptography.SHA256]::Create()
    try {
        $left = $Length
        while ($left -gt 0) {
            $n = $Stream.Read($buffer, 0, [int][Math]::Min($left, $buffer.Length))
            if ($n -le 0) { throw 'Unexpected EOF while hashing.' }
            [void]$hash.TransformBlock($buffer, 0, $n, $buffer, 0)
            $left -= $n
        }
        [void]$hash.TransformFinalBlock([byte[]]@(), 0, 0)
        return ([BitConverter]::ToString($hash.Hash) -replace '-', '').ToLowerInvariant()
    } finally { $hash.Dispose() }
}

function Get-RgspBootRoot($Partition) {
    $letter = [string]$Partition.DriveLetter
    if ($letter -cmatch '^[A-Z]$') { return "${letter}:\" }
    $paths = @($Partition.AccessPaths | Where-Object {
        $_ -match '^\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}\\$'
    })
    if ($paths.Count -ne 1) { throw 'Expected exactly one ANBOOT volume path.' }
    return $paths[0]
}

function Assert-RgspRangePreimage([IO.Stream]$Stream, [long]$Offset, [long]$Length,
    [string]$Expected) {
    if ((Get-RgspRangeHash $Stream $Offset $Length) -ne $Expected) {
        throw 'Live preimage differs from verified backup; no writes.'
    }
}

function Assert-RgspBootRecovery([string]$BootRoot, [string]$Expected) {
    # .NET accepts volume GUID paths without assigning a Windows drive letter.
    if (@([IO.Directory]::GetFileSystemEntries($BootRoot, 'RGSP_ANDROID_TRY.ONCE')).Count -ne 0) {
        throw 'ANBOOT recovery/one-shot gate failed.'
    }
    $stream = [IO.File]::OpenRead($BootRoot + 'rgsp-linux-boot-original.img')
    try {
        if ($stream.Length -ne 67108864L -or
            (Get-RgspRangeHash $stream 0 $stream.Length) -ne $Expected) {
            throw 'ANBOOT recovery/one-shot gate failed.'
        }
    } finally { $stream.Dispose() }
}

function Copy-RgspRange([IO.Stream]$Source, [IO.Stream]$Destination,
    [long]$SourceOffset, [long]$DestinationOffset, [long]$Length) {
    if ($SourceOffset -lt 0 -or $DestinationOffset -lt 0 -or $Length -le 0) {
        throw 'Invalid copy range.'
    }
    [void]$Source.Seek($SourceOffset, 'Begin')
    [void]$Destination.Seek($DestinationOffset, 'Begin')
    $buffer = New-Object byte[] (4MB)
    $left = $Length
    while ($left -gt 0) {
        $n = $Source.Read($buffer, 0, [int][Math]::Min($left, $buffer.Length))
        if ($n -le 0) { throw 'Unexpected source EOF while copying.' }
        $Destination.Write($buffer, 0, $n)
        $left -= $n
    }
    if ($Destination -is [IO.FileStream]) { $Destination.Flush($true) }
    else { $Destination.Flush() }
}

function Invoke-RgspVendorTransaction([IO.Stream]$Disk, [IO.Stream]$Image,
    [IO.Stream]$Recovery, [long]$Offset, [long]$Length,
    [string]$Expected, [string]$RecoveryExpected) {
    # Validate BOTH already-open sources before the first destination write.
    if ($Image.Length -ne $Length -or $Recovery.Length -ne $Length -or
        (Get-RgspRangeHash $Image 0 $Length) -ne $Expected -or
        (Get-RgspRangeHash $Recovery 0 $Length) -ne $RecoveryExpected) {
        throw 'Locked image/recovery integrity failed; no writes.'
    }
    try {
        Copy-RgspRange $Image $Disk 0 $Offset $Length
        if ((Get-RgspRangeHash $Disk $Offset $Length) -ne $Expected) {
            throw 'Vendor readback mismatch.'
        }
    } catch {
        $failure = $_.Exception.Message
        try {
            Copy-RgspRange $Recovery $Disk 0 $Offset $Length
            if ((Get-RgspRangeHash $Disk $Offset $Length) -ne $RecoveryExpected) {
                throw 'Recovery readback mismatch.'
            }
        } catch {
            throw "VENDOR_ROLLBACK_FAILED; retain card in reader. Cause: $failure; recovery: $_"
        }
        throw "VENDOR_ROLLBACK_VERIFIED; original operation failed: $failure"
    }
}

function Write-RgspNewJson([string]$Path, $Value) {
    $bytes = [Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 12) + "`n")
    $stream = [IO.File]::Open($Path, 'CreateNew', 'Write', 'None')
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
}
