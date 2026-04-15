$hex = -join (1..4 | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$filename = "miniprogram_${ts}_${hex}.zip"
Write-Output "FILENAME=$filename"
