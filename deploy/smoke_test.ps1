$ErrorActionPreference = 'Stop'
$base = 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27'
$body = @{ phone = '13800050505'; password = 'Smoke123!' } | ConvertTo-Json
$login = Invoke-RestMethod -Uri "$base/api/admin/login" -Method POST -ContentType 'application/json' -Body $body
$token = $login.access_token
Write-Host "LOGIN_OK token_len=$($token.Length)"
$h = @{ Authorization = "Bearer $token" }

$forms = Invoke-RestMethod -Uri "$base/api/admin/appointment-forms" -Headers $h
Write-Host "FORMS_LIST_OK count=$($forms.Count)"

$stamp = [int][double]::Parse((Get-Date -UFormat %s))
$createBody = @{ name = "Smoke_$stamp"; status = 'active' } | ConvertTo-Json
$form = Invoke-RestMethod -Uri "$base/api/admin/appointment-forms" -Method POST -Headers $h -ContentType 'application/json' -Body $createBody
Write-Host "FORM_CREATED id=$($form.id) name=$($form.name)"

$fieldBody = @{ field_name = 'xingming'; label = '姓名'; field_type = 'text'; is_required = $true; display_order = 1 } | ConvertTo-Json
$field = Invoke-RestMethod -Uri "$base/api/admin/appointment-forms/$($form.id)/fields" -Method POST -Headers $h -ContentType 'application/json' -Body $fieldBody
Write-Host "FIELD_CREATED id=$($field.id)"

$catBody = @{ name = "冒烟分类_$stamp" } | ConvertTo-Json
$cat = Invoke-RestMethod -Uri "$base/api/admin/products/categories" -Method POST -Headers $h -ContentType 'application/json' -Body $catBody
Write-Host "CAT_CREATED id=$($cat.id)"
$cid = $cat.id

$p1 = @{ name = "SmokeProductDate_$stamp"; category_id = $cid; fulfillment_type = 'in_store'; original_price = 120; sale_price = 100; price = 100; appointment_mode = 'date'; advance_days = 7; daily_quota = 5; purchase_appointment_mode = 'purchase_with_appointment' } | ConvertTo-Json
$prod1 = Invoke-RestMethod -Uri "$base/api/admin/products" -Method POST -Headers $h -ContentType 'application/json' -Body $p1
Write-Host "PRODUCT_DATE_OK id=$($prod1.id) mode=$($prod1.appointment_mode) advance=$($prod1.advance_days)"

$p2 = @{ name = "SmokeProductDateFail_$stamp"; category_id = $cid; fulfillment_type = 'in_store'; original_price = 120; sale_price = 100; price = 100; appointment_mode = 'date' } | ConvertTo-Json
try {
  Invoke-RestMethod -Uri "$base/api/admin/products" -Method POST -Headers $h -ContentType 'application/json' -Body $p2 | Out-Null
  Write-Host "NEGATIVE_DATE_FAIL: unexpectedly succeeded"
} catch {
  $err = $_.Exception.Response.StatusCode.Value__
  Write-Host "NEGATIVE_DATE_OK status=$err"
}

$p3 = @{ name = "SmokeProductForm_$stamp"; category_id = $cid; fulfillment_type = 'in_store'; original_price = 120; sale_price = 100; price = 100; appointment_mode = 'custom_form'; custom_form_id = $form.id; purchase_appointment_mode = 'appointment_later' } | ConvertTo-Json
$prod3 = Invoke-RestMethod -Uri "$base/api/admin/products" -Method POST -Headers $h -ContentType 'application/json' -Body $p3
Write-Host "PRODUCT_CUSTOM_FORM_OK id=$($prod3.id) form_id=$($prod3.custom_form_id)"

$ts = @(@{ start = '09:00'; end = '10:00'; capacity = 3 }, @{ start = '10:00'; end = '11:00'; capacity = 5 })
$p4 = @{ name = "SmokeProductSlot_$stamp"; category_id = $cid; fulfillment_type = 'in_store'; original_price = 120; sale_price = 100; price = 100; appointment_mode = 'time_slot'; time_slots = $ts; purchase_appointment_mode = 'appointment_later' } | ConvertTo-Json -Depth 5
$prod4 = Invoke-RestMethod -Uri "$base/api/admin/products" -Method POST -Headers $h -ContentType 'application/json' -Body $p4
Write-Host "PRODUCT_TIMESLOT_OK id=$($prod4.id) slots=$($prod4.time_slots.Count)"

Write-Host "ALL_SMOKE_PASSED"
