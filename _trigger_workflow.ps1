$tag = Get-Content _apk_tag.txt -Raw
$tag = $tag.Trim()
Write-Output "TAG=$tag"
$ok = $false
$delays = @(10, 20, 40)
for ($i = 0; $i -lt 3; $i++) {
    $n = $i + 1
    Write-Output "Attempt ${n}: gh workflow run android-build.yml -f version=$tag"
    gh workflow run android-build.yml -f version=$tag 2>&1
    if ($LASTEXITCODE -eq 0) {
        $ok = $true
        break
    }
    $s = $delays[$i]
    Write-Output "Failed, sleep ${s}s"
    Start-Sleep -Seconds $s
}
if ($ok) { Write-Output "TRIGGERED OK" } else { Write-Output "TRIGGER FAILED"; exit 1 }
