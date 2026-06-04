B=https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com
for p in /care-ai-home /care-ai-home/today-health /care-ai-home/sos /care-ai-home/info-card; do
  code=$(curl -sL -o /tmp/_pg.html -w '%{http_code}' "$B$p")
  has=$(grep -ci 'care-ai-home\|小康\|今日\|紧急\|信息卡\|html' /tmp/_pg.html)
  echo "$code  match=$has  $p"
done
