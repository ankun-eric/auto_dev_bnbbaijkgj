BASE="https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
for p in "care-ai-home" "care-ai-home/sos" "care-ai-home/today-health" "care-ai-home/share-location/sometoken" "care-ai-home/info-card"; do
  code=$(curl -sL -o /dev/null -w "%{http_code}" "$BASE/$p")
  echo "$p -> $code"
done
echo "===== SOS page content check (扩散圈/长按/定位条 markers) ====="
curl -sL "$BASE/care-ai-home/sos" | grep -o -E "care-sos-ripple|care-sos-progress-ring|定位中|长按 3 秒求助" | sort | uniq -c
