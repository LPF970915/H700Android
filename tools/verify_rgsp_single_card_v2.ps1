[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'rgsp_vendor_io.ps1')
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$candidate=Join-Path $root 'out/rgsp-single-card-v2-20260911'
$base=Join-Path $root 'out/rgsp-single-card-20260911'
$disk=@(Get-Disk | Where-Object {$_.FriendlyName -eq 'Generic MassStorageClass' -and $_.SerialNumber.Trim() -eq '000000001539' -and $_.Size -eq 62239277056L -and $_.BusType -eq 'USB' -and !$_.IsOffline})[0]
if(!$disk){throw 'target not found'}
$ranges=@(
 @{Name='prefix';Path=Join-Path $candidate 'prefix-212m.bin';Offset=0L},
 @{Name='system';Path=Join-Path $base 'system.raw.img';Offset=222298112L},
 @{Name='vendor';Path=Join-Path $base 'vendor.raw.img';Offset=8812232704L},
 @{Name='data';Path=Join-Path $base 'data.raw.img';Offset=10959716352L},
 @{Name='gpt-tail';Path=Join-Path $candidate 'gpt-tail.bin';Offset=62239275520L}
)
$s=[IO.File]::Open("\\.\PhysicalDrive$($disk.Number)",'Open','Read','ReadWrite')
try {
 foreach($r in $ranges){
  $expected=(Get-FileHash $r.Path -Algorithm SHA256).Hash
  $actual=Get-RgspRangeHash $s $r.Offset (Get-Item $r.Path).Length
  [pscustomobject]@{Name=$r.Name;Expected=$expected;Actual=$actual;Match=($expected -eq $actual)}
 }
} finally {$s.Dispose()}
Get-Partition -DiskNumber $disk.Number | Sort-Object PartitionNumber | Format-Table PartitionNumber,Offset,Size,GptType,DriveLetter -AutoSize
