#!/bin/bash
# 在服务器上诊断 /api/chat-sessions 返回内容
BASE="https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
PH="13900048801"

echo "=== Step 1: register ==="
curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"phone\":\"$PH\",\"password\":\"user123\",\"nickname\":\"diagU\"}" \
  "$BASE/api/auth/register"
echo ""

echo "=== Step 2: login ==="
LOGIN_RESP=$(curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"phone\":\"$PH\",\"password\":\"user123\"}" \
  "$BASE/api/auth/login")
echo "$LOGIN_RESP"
T=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")
echo "TOKEN=$T"

echo "=== Step 3: GET /api/chat-sessions (empty user) ==="
curl -s -w "\nSTATUS=%{http_code}\n" \
  -H "Authorization: Bearer $T" \
  -H "X-Client-Source: h5-customer" \
  -H "X-Client-Type: h5-user" \
  "$BASE/api/chat-sessions"

echo ""
echo "=== Step 4: POST /api/chat-sessions (create one) ==="
curl -s -w "\nSTATUS=%{http_code}\n" \
  -X POST -H "Content-Type: application/json" \
  -H "Authorization: Bearer $T" \
  -H "X-Client-Source: h5-customer" \
  -H "X-Client-Type: h5-user" \
  -d '{"session_type":"health_qa","title":"诊断测试会话"}' \
  "$BASE/api/chat-sessions"

echo ""
echo "=== Step 5: GET /api/chat-sessions (after create) ==="
curl -s -w "\nSTATUS=%{http_code}\n" \
  -H "Authorization: Bearer $T" \
  -H "X-Client-Source: h5-customer" \
  -H "X-Client-Type: h5-user" \
  "$BASE/api/chat-sessions"
