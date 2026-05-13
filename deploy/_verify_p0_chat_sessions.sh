#!/bin/bash
# ============================================================
# Hotfix P0 验证脚本：服务器非UI自动化测试
# 覆盖：登录、空列表、创建会话、列表非空、活跃度检查、删除
# 修复目标：BUG-460/461/462 在生产可用
# ============================================================

BASE="https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
PASS=0
FAIL=0
TOTAL=0
FAIL_DETAILS=""

assert_eq() {
    local name="$1"; local expect="$2"; local actual="$3"
    TOTAL=$((TOTAL+1))
    if [ "$expect" = "$actual" ]; then
        PASS=$((PASS+1))
        echo "  [PASS] $name (expected=$expect, got=$actual)"
    else
        FAIL=$((FAIL+1))
        echo "  [FAIL] $name (expected=$expect, got=$actual)"
        FAIL_DETAILS="$FAIL_DETAILS\n  - $name: expected=$expect, got=$actual"
    fi
}

assert_contains() {
    local name="$1"; local needle="$2"; local haystack="$3"
    TOTAL=$((TOTAL+1))
    if echo "$haystack" | grep -q "$needle"; then
        PASS=$((PASS+1))
        echo "  [PASS] $name"
    else
        FAIL=$((FAIL+1))
        echo "  [FAIL] $name (need '$needle' in: ${haystack:0:200})"
        FAIL_DETAILS="$FAIL_DETAILS\n  - $name: missing '$needle'"
    fi
}

PH="13900049$(date +%H%M%S | tail -c 4)"
echo "Test phone: $PH"

# ───── T1: 注册 + 登录 ─────
echo ""
echo "── T1: 注册新用户 ──"
REG=$(curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"phone\":\"$PH\",\"password\":\"user123\",\"nickname\":\"P0VerifyU\"}" \
  "$BASE/api/auth/register")
TOTAL=$((TOTAL+1))
if echo "$REG" | grep -q "access_token"; then
    PASS=$((PASS+1)); echo "  [PASS] 注册成功"
    T=$(echo "$REG" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
else
    FAIL=$((FAIL+1)); echo "  [FAIL] 注册失败: $REG"; T=""
    FAIL_DETAILS="$FAIL_DETAILS\n  - T1 注册失败"
fi

if [ -z "$T" ]; then
    echo ""
    echo "===== 注册失败，无法继续测试 ====="
    exit 1
fi

H="Authorization: Bearer $T"
HC="X-Client-Source: h5-customer"
HT="X-Client-Type: h5-user"

# ───── T2: 空列表 GET ─────
echo ""
echo "── T2: 新用户访问 GET /api/chat-sessions（应返回 200 + 空列表） ──"
RESP=$(curl -s -w "\nHTTP_STATUS=%{http_code}" -H "$H" -H "$HC" -H "$HT" "$BASE/api/chat-sessions")
STATUS=$(echo "$RESP" | grep "HTTP_STATUS=" | cut -d= -f2)
BODY=$(echo "$RESP" | sed '/HTTP_STATUS=/d')
assert_eq "T2-1: 状态码=200（BUG-460 核心修复）" "200" "$STATUS"
assert_eq "T2-2: 返回内容是空列表" "[]" "$BODY"

# ───── T3: 创建会话 ─────
echo ""
echo "── T3: POST /api/chat-sessions 创建新会话 ──"
RESP=$(curl -s -w "\nHTTP_STATUS=%{http_code}" -X POST \
    -H "Content-Type: application/json" -H "$H" -H "$HC" -H "$HT" \
    -d '{"session_type":"health_qa","title":"P0 验证会话"}' \
    "$BASE/api/chat-sessions")
STATUS=$(echo "$RESP" | grep "HTTP_STATUS=" | cut -d= -f2)
BODY=$(echo "$RESP" | sed '/HTTP_STATUS=/d')
assert_eq "T3-1: 状态码=200" "200" "$STATUS"
assert_contains "T3-2: 包含 id 字段" '"id"' "$BODY"
assert_contains "T3-3: 包含 family_member_relation=self（BUG-461）" '"family_member_relation":"self"' "$BODY"
SID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
echo "  created session_id=$SID"

# ───── T4: 列表非空 ─────
echo ""
echo "── T4: 创建后 GET /api/chat-sessions 列表非空 ──"
RESP=$(curl -s -w "\nHTTP_STATUS=%{http_code}" -H "$H" -H "$HC" -H "$HT" "$BASE/api/chat-sessions")
STATUS=$(echo "$RESP" | grep "HTTP_STATUS=" | cut -d= -f2)
BODY=$(echo "$RESP" | sed '/HTTP_STATUS=/d')
assert_eq "T4-1: 状态码=200" "200" "$STATUS"
assert_contains "T4-2: 列表包含刚创建的会话标题" "P0 验证会话" "$BODY"
assert_contains "T4-3: 包含 family_member_relation 字段（BUG-461 Fix-B）" 'family_member_relation' "$BODY"
assert_contains "T4-4: 包含 family_member_id 字段（BUG-461 Fix-B）" 'family_member_id' "$BODY"

# ───── T5: active-check（业务规则 6h） ─────
echo ""
echo "── T5: GET /api/chat-sessions/active-check（BUG-461 业务规则） ──"
RESP=$(curl -s -w "\nHTTP_STATUS=%{http_code}" -H "$H" -H "$HC" -H "$HT" "$BASE/api/chat-sessions/active-check")
STATUS=$(echo "$RESP" | grep "HTTP_STATUS=" | cut -d= -f2)
BODY=$(echo "$RESP" | sed '/HTTP_STATUS=/d')
assert_eq "T5-1: 状态码=200" "200" "$STATUS"
assert_contains "T5-2: 包含 should_new_session 字段" "should_new_session" "$BODY"
assert_contains "T5-3: 包含 threshold_hours 字段" "threshold_hours" "$BODY"

# ───── T6: 删除会话（BUG-462 接口对齐） ─────
if [ -n "$SID" ]; then
    echo ""
    echo "── T6: DELETE /api/chat-sessions/$SID（BUG-462 接口） ──"
    RESP=$(curl -s -w "\nHTTP_STATUS=%{http_code}" -X DELETE -H "$H" -H "$HC" -H "$HT" "$BASE/api/chat-sessions/$SID")
    STATUS=$(echo "$RESP" | grep "HTTP_STATUS=" | cut -d= -f2)
    BODY=$(echo "$RESP" | sed '/HTTP_STATUS=/d')
    assert_eq "T6-1: 删除状态码=200" "200" "$STATUS"
    assert_contains "T6-2: 返回删除成功" "删除成功" "$BODY"

    # 删除后列表应当不再包含
    RESP=$(curl -s -H "$H" -H "$HC" -H "$HT" "$BASE/api/chat-sessions")
    TOTAL=$((TOTAL+1))
    if ! echo "$RESP" | grep -q "P0 验证会话"; then
        PASS=$((PASS+1)); echo "  [PASS] T6-3: 删除后列表中不再包含"
    else
        FAIL=$((FAIL+1)); echo "  [FAIL] T6-3: 删除后列表中仍包含"
        FAIL_DETAILS="$FAIL_DETAILS\n  - T6-3: 删除后仍存在"
    fi
fi

# ───── T7: 已登录页面 /chat-history 的接口连通性 ─────
echo ""
echo "── T7: 多次连续请求 /api/chat-sessions 稳定性（10 次循环） ──"
ALL_OK=1
for i in $(seq 1 10); do
    CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "$H" -H "$HC" -H "$HT" "$BASE/api/chat-sessions")
    if [ "$CODE" != "200" ]; then
        ALL_OK=0
        echo "  [FAIL] 第 $i 次请求返回 $CODE"
    fi
done
TOTAL=$((TOTAL+1))
if [ $ALL_OK -eq 1 ]; then
    PASS=$((PASS+1)); echo "  [PASS] T7: 10 次连续请求全部 200"
else
    FAIL=$((FAIL+1))
    FAIL_DETAILS="$FAIL_DETAILS\n  - T7 稳定性测试失败"
fi

# ───── T8: H5 页面入口可达 ─────
echo ""
echo "── T8: H5 前端页面可达性 ──"
H5_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/ai-home")
TOTAL=$((TOTAL+1))
if [ "$H5_CODE" = "200" ] || [ "$H5_CODE" = "307" ] || [ "$H5_CODE" = "302" ]; then
    PASS=$((PASS+1)); echo "  [PASS] T8: ai-home 页面可达（status=$H5_CODE）"
else
    FAIL=$((FAIL+1)); echo "  [FAIL] T8: ai-home 页面不可达（status=$H5_CODE）"
    FAIL_DETAILS="$FAIL_DETAILS\n  - T8 ai-home 不可达"
fi

# ───── 汇总 ─────
echo ""
echo "================================================"
echo "    P0 验证汇总：$PASS / $TOTAL PASS, $FAIL FAIL"
echo "================================================"
if [ $FAIL -gt 0 ]; then
    echo ""
    echo "失败用例："
    echo -e "$FAIL_DETAILS"
    exit 1
fi
echo "全部通过 ✓"
