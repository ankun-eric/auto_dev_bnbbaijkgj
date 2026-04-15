$zipPath = "C:\auto_output\bnbbaijkgj\miniprogram_20260415_225929_26df.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath }
Compress-Archive -Path "C:\auto_output\bnbbaijkgj\miniprogram\*" -DestinationPath $zipPath
if (Test-Path $zipPath) {
    $size = (Get-Item $zipPath).Length
    Write-Output "ZIP_CREATED=$zipPath SIZE=$size"
} else {
    Write-Output "ZIP_FAILED"
}
