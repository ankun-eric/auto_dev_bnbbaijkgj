param(
    [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
    [string[]]$GhArgs
)

$delays = @(10, 20, 40)
$maxAttempts = 4
for ($i = 1; $i -le $maxAttempts; $i++) {
    Write-Host "[gh-retry] attempt $i : gh $($GhArgs -join ' ')"
    $output = & gh @GhArgs 2>&1
    $code = $LASTEXITCODE
    $output | ForEach-Object { Write-Host $_ }
    if ($code -eq 0) {
        exit 0
    }
    if ($i -lt $maxAttempts) {
        $d = $delays[$i - 1]
        Write-Host "[gh-retry] failed (exit $code), sleeping $d s..."
        Start-Sleep -Seconds $d
    }
}
Write-Host "[gh-retry] all attempts failed"
exit 1
