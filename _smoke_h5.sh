B=https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com
for p in /care-ai-home /care-ai-home/today-health /care-ai-home/sos /care-ai-home/info-card /binni-xiaokang-logo.png; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$B$p")
  echo "$code  $p"
done
echo "=== card-view token page (dynamic) ==="
curl -s -o /dev/null -w '%{http_code}  /care-ai-home/card-view/sometoken\n' "$B/care-ai-home/card-view/sometoken"
