$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$rand = -join ((48..57) + (97..102) | Get-Random -Count 4 | ForEach-Object { [char]$_ })
$zipName = "miniprogram_${timestamp}_${rand}.zip"
$dest = Join-Path "C:\auto_output\bnbbaijkgj" $zipName
Compress-Archive -Path "C:\auto_output\bnbbaijkgj\miniprogram\*" -DestinationPath $dest -Force
Write-Output $zipName
