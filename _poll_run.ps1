param([string]$RunId = "26182491925")
$maxMin = 30
$start = Get-Date
while ($true) {
    $elapsed = (Get-Date) - $start
    if ($elapsed.TotalMinutes -gt $maxMin) {
        Write-Output "TIMEOUT after $maxMin minutes"
        exit 2
    }
    $json = gh run view $RunId --json status,conclusion 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        Write-Output "gh view failed, retry"
        Start-Sleep -Seconds 10
        continue
    }
    try {
        $obj = $json | ConvertFrom-Json
    } catch {
        Write-Output "parse fail: $json"
        Start-Sleep -Seconds 10
        continue
    }
    $em = [math]::Round($elapsed.TotalMinutes, 1)
    Write-Output "[$em min] status=$($obj.status) conclusion=$($obj.conclusion)"
    if ($obj.status -eq "completed") {
        if ($obj.conclusion -eq "success") {
            Write-Output "BUILD SUCCESS"
            exit 0
        } else {
            Write-Output "BUILD FAILED: $($obj.conclusion)"
            exit 1
        }
    }
    Start-Sleep -Seconds 30
}
