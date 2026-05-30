/**
 * [PRD-INVITE-FAMILY-CARD-V1 2026-05-30] 邀请家人入口卡片纯函数单元测试
 *
 * 运行：node h5-web/src/lib/__tests__/run_invite_card_test.mjs
 *
 * 覆盖 PRD §2.3 / §3.3 / §5（业务规则）：
 *  - BR-02：不限档（max=-1 / >=9999）永远不进达上限态
 *  - BR-01：含本人口径展示
 *  - F1 / F2 状态判定：X<Y → normal，X>=Y 且有限档 → full
 *  - 异常处理：plan_name 缺失走兜底；max=null 时不进入达上限态
 */

// 直接复制纯函数实现（避免 ts/jsx 依赖）
// 真实组件实现见 h5-web/src/app/member-center/components/InviteFamilyCard.tsx
function isUnlimitedQuota(quotaMax) {
  if (quotaMax === null || quotaMax === undefined) return false;
  return quotaMax === -1 || quotaMax >= 9999;
}

function isFullState(quotaUsed, quotaMax) {
  if (isUnlimitedQuota(quotaMax)) return false;
  if (quotaUsed === null || quotaUsed === undefined) return false;
  if (quotaMax === null || quotaMax === undefined) return false;
  return quotaUsed >= quotaMax;
}

function computeCardState(quotaUsed, quotaMax) {
  return isFullState(quotaUsed, quotaMax) ? 'full' : 'normal';
}

// [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #3]
// 历史："可管理 N 位家人" / "不限家人数" / "可管理家人"
// 现状：会员级别行在档案列表/会员中心两处均会被容器宽度截断（如"普通会员 · 可管理 10..."），
//       且数字已在顶部"已管理 X/Y"卡片中清晰呈现，重复信息。
// 修复：formatBenefitPhrase 一律返回空串，主标题仅显示套餐名（"家庭版" / "尊享版"），
//       formatTitleLine 当 phrase 为空时不再拼接" · "。
function formatBenefitPhrase(_quotaMax) {
  return '';
}

function formatTitleLine(planName, quotaMax) {
  const name = (planName && String(planName).trim()) || '会员套餐';
  const phrase = formatBenefitPhrase(quotaMax);
  return phrase ? `${name} · ${phrase}` : name;
}

function formatQuotaLine(quotaUsed, quotaMax) {
  if (isUnlimitedQuota(quotaMax)) {
    const used = (typeof quotaUsed === 'number' && quotaUsed >= 0) ? quotaUsed : 0;
    return `已管理 ${used} 人 · 不限上限`;
  }
  if (quotaMax === null || quotaMax === undefined) return '';
  const used = (typeof quotaUsed === 'number' && quotaUsed >= 0) ? quotaUsed : 0;
  return `已管理 ${used} / 上限 ${quotaMax}`;
}

// ─── 测试断言 ───
let passed = 0;
let failed = 0;
function assertEq(actual, expected, name) {
  if (actual === expected) {
    passed++;
    console.log(`  ✔ ${name}`);
  } else {
    failed++;
    console.log(`  ✘ ${name}\n    expected: ${JSON.stringify(expected)}\n    actual:   ${JSON.stringify(actual)}`);
  }
}

console.log('[InviteFamilyCard] BR-02 不限档判定');
assertEq(isUnlimitedQuota(-1), true, 'max=-1 视为不限');
assertEq(isUnlimitedQuota(9999), true, 'max=9999 视为不限');
assertEq(isUnlimitedQuota(10000), true, 'max=10000 视为不限');
assertEq(isUnlimitedQuota(20), false, 'max=20 非不限');
assertEq(isUnlimitedQuota(0), false, 'max=0 非不限（PRD 不限定特殊化）');
assertEq(isUnlimitedQuota(null), false, 'max=null 非不限');
assertEq(isUnlimitedQuota(undefined), false, 'max=undefined 非不限');

console.log('\n[InviteFamilyCard] F1/F2 达上限态判定');
assertEq(isFullState(3, 10), false, '3/10 → 正常态');
assertEq(isFullState(9, 10), false, '9/10 → 正常态');
assertEq(isFullState(10, 10), true, '10/10 → 达上限态');
assertEq(isFullState(11, 10), true, '11/10（脏数据）→ 达上限态');
assertEq(isFullState(0, 0), true, '0/0（异常）→ 达上限态');
assertEq(isFullState(20, -1), false, '20/-1（不限档）→ 永远正常态');
assertEq(isFullState(20, 9999), false, '20/9999（不限档）→ 永远正常态');
assertEq(isFullState(20, 99999), false, '20/99999（不限档）→ 永远正常态');
assertEq(isFullState(null, 10), false, 'used=null → 兜底正常态');
assertEq(isFullState(5, null), false, 'max=null → 兜底正常态');

console.log('\n[InviteFamilyCard] computeCardState 状态计算');
assertEq(computeCardState(3, 10), 'normal', '3/10 normal');
assertEq(computeCardState(10, 10), 'full', '10/10 full');
assertEq(computeCardState(20, 9999), 'normal', '不限档不会 full');

console.log('\n[InviteFamilyCard] 权益短语（#3 修复后：一律返回空串，去重 + 防截断）');
assertEq(formatBenefitPhrase(10), '', '有限档 10：不再展示「可管理 N 位家人」');
assertEq(formatBenefitPhrase(20), '', '有限档 20：不再展示「可管理 N 位家人」');
assertEq(formatBenefitPhrase(-1), '', '不限档 -1：不再展示「不限家人数」');
assertEq(formatBenefitPhrase(9999), '', '不限档 9999：不再展示「不限家人数」');
assertEq(formatBenefitPhrase(null), '', '空 max：不再展示兜底文案');

console.log('\n[InviteFamilyCard] 主标题（#3 修复后：仅展示套餐名，去掉" · 可管理 N..."避免截断）');
assertEq(formatTitleLine('家庭版', 10), '家庭版', '家庭版（不再拼可管理文案）');
assertEq(formatTitleLine('尊享版', 20), '尊享版', '尊享版（不再拼可管理文案）');
assertEq(formatTitleLine('尊享版', 9999), '尊享版', '尊享版（不限档同样仅显示套餐名）');
assertEq(formatTitleLine('', 10), '会员套餐', '空套餐名走兜底「会员套餐」');
assertEq(formatTitleLine(null, 10), '会员套餐', 'null 套餐名走兜底「会员套餐」');
assertEq(formatTitleLine(undefined, undefined), '会员套餐', '套餐名+max 都缺失走兜底');

console.log('\n[InviteFamilyCard] 用量行');
assertEq(formatQuotaLine(3, 10), '已管理 3 / 上限 10', '已管理 3 / 上限 10');
assertEq(formatQuotaLine(10, 10), '已管理 10 / 上限 10', '已管理 10 / 上限 10（达上限）');
assertEq(formatQuotaLine(0, 10), '已管理 0 / 上限 10', '已管理 0 / 上限 10');
assertEq(formatQuotaLine(null, 10), '已管理 0 / 上限 10', 'used=null 兜底为 0');
assertEq(formatQuotaLine(3, -1), '已管理 3 人 · 不限上限', '不限档 -1 用量行');
assertEq(formatQuotaLine(3, 9999), '已管理 3 人 · 不限上限', '不限档 9999 用量行');
assertEq(formatQuotaLine(0, 9999), '已管理 0 人 · 不限上限', '不限档 used=0');
assertEq(formatQuotaLine(3, null), '', 'max=null 用量行隐藏（PRD 异常处理）');

console.log(`\n汇总：${passed} passed, ${failed} failed`);
if (failed > 0) {
  process.exit(1);
}
