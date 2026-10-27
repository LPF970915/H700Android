$keepDirs = @('rgsp-single-card-v3b-20260912')
$keepFiles = @('H700_Android_SingleCard_v3b.img')

Write-Host '=== Cleanup Start ===' -ForegroundColor Green

$deletedSize = 0
$deletedCount = 0

Get-ChildItem out -Directory | Where-Object { $keepDirs -notcontains $_.Name } | ForEach-Object {
    $dirSize = (Get-ChildItem $_.FullName -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    if ($dirSize -eq $null) { $dirSize = 0 }
    $deletedSize += $dirSize
    $sizeGB = [math]::Round($dirSize / 1GB, 2)
    Write-Host "Delete: $($_.Name) (${sizeGB} GB)"
    Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    $deletedCount++
}

Get-ChildItem out -File | Where-Object { $keepFiles -notcontains $_.Name } | ForEach-Object {
    $deletedSize += $_.Length
    $fileSizeGB = [math]::Round($_.Length / 1GB, 2)
    Write-Host "Delete: $($_.Name) (${fileSizeGB} GB)"
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    $deletedCount++
}

$totalDeletedGB = [math]::Round($deletedSize / 1GB, 2)
Write-Host ''
Write-Host '=== Cleanup Complete ===' -ForegroundColor Green
Write-Host "Deleted: $deletedCount items"
Write-Host "Freed: ${totalDeletedGB} GB"
Write-Host ''

$remaining = Get-ChildItem out -Recurse | Measure-Object -Property Length -Sum
$remainingGB = [math]::Round($remaining.Sum / 1GB, 2)
Write-Host '=== Remaining ===' -ForegroundColor Cyan
Write-Host "Files: $($remaining.Count)"
Write-Host "Size: ${remainingGB} GB"