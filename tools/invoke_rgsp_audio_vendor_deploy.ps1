[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Backup', 'Apply', 'Restore')][string]$Mode = 'Plan',
    [Nullable[int]]$DiskNumber,
    [string]$BackupDirectory
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'invoke_rgsp_codec_vendor_deploy.ps1') `
    -Profile Audio -Mode $Mode -DiskNumber $DiskNumber -BackupDirectory $BackupDirectory
