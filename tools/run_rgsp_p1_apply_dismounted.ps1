$ErrorActionPreference = 'Stop'
$diskNumber = 3
$dir = 'D:\Works\H700Android\out\tf2-p1-readonly-20260909-r2'
trap {
    $_ | Out-File -LiteralPath (Join-Path $dir 'dismount-error.log') -Encoding utf8
    throw
}
$disk = Get-Disk -Number $diskNumber
if ($disk.BusType -ne 'USB' -or $disk.Size -ne 125069950976L -or
    $disk.PartitionStyle -ne 'GPT' -or $disk.IsBoot -or $disk.IsSystem) {
    throw 'TF2 identity gate failed before dismount.'
}
foreach ($partition in @(Get-Partition -DiskNumber $diskNumber)) {
    if ($partition.DriveLetter) {
        Remove-PartitionAccessPath -DiskNumber $diskNumber `
            -PartitionNumber $partition.PartitionNumber `
            -AccessPath "$($partition.DriveLetter):\"
    }
}
& 'D:\Works\H700Android\tools\invoke_rgsp_p1_repair_deploy.ps1' `
    -Mode Apply -DiskNumber $diskNumber -Directory $dir
exit $LASTEXITCODE
