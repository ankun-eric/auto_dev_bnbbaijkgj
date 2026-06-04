#!/bin/bash
BASE="https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/miniprogram"
for f in miniprogram_20260523_230121_4564.zip miniprogram_member_free_20260527_012314_ff60.zip; do
  code=$(curl -sL -o /dev/null -w '%{http_code}' "$BASE/$f")
  echo "$f -> $code"
done
ls -la /var/www/miniprogram/miniprogram_member_free_20260527_012314_ff60.zip
echo DONE
