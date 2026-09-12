# 清理旧版本构建，保留当前基线 v3b
$keepBaseline = 'rgsp-single-card-v3b-20260912'
$toDelete = @(
    'rgsp-single-card-20260911',
    'rgsp-single-card-v2-20260911',
    'rgsp-fix72-wifi-profile',
    'rgsp-fix70-wifi-deployment',
    'tf2-fix72-deploy-20260907-current-v2',
    'tf2-deploy-20260907',
    'h700-android10-preflight'
)

foreach ($dir in $toDelete) {
    $path = Join-Path 'D:\Works\H700Android\out' $dir
    if (Test-Path $path) {
        Write-Host "Deleting: $dir"
        Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "Cleanup complete. Preserved: $keepBaseline"
