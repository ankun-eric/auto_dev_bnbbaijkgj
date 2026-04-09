# Pack miniprogram; scp to host ~/.../uploads/ then docker cp into backend so /uploads/ URL returns 200:
# docker cp /home/ubuntu/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/<zip> 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-backend:/app/uploads/
$ErrorActionPreference = 'Stop'
$source = 'C:\auto_output\bnbbaijkgj\miniprogram'
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$rand = -join ((48..57) + (97..102) | Get-Random -Count 4 | ForEach-Object { [char]$_ })
$zipName = "miniprogram_${ts}_${rand}.zip"
$staging = Join-Path $env:TEMP "miniprogram_stage_$ts"
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging -Force | Out-Null
$null = robocopy $source $staging /E /XD node_modules .git .DS_Store __pycache__ .idea /NFL /NDL /NJH /NJS /NC /NS
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with exit code $LASTEXITCODE" }
$destZip = Join-Path 'C:\auto_output\bnbbaijkgj' $zipName
if (Test-Path $destZip) { Remove-Item $destZip -Force }
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $destZip -Force
Remove-Item $staging -Recurse -Force
$item = Get-Item $destZip
Write-Output "ZIP_NAME=$zipName"
Write-Output "ZIP_PATH=$($item.FullName)"
Write-Output "ZIP_BYTES=$($item.Length)"
