/**
 * [PRD-INVITE-FAMILY-CARD-V1.1 2026-05-30] 邀请家人入口卡片 v1.1 位置调整补丁单元测试
 *
 * 运行：node h5-web/src/lib/__tests__/run_invite_card_v11_test.mjs
 *
 * 覆盖 PRD v1.1 验收 AC-16 ~ AC-23 + RC-05 ~ RC-08 的可单测部分：
 *  - card_location 字段构造（会员中心位 = member_center；档案位 = profile_list_top）
 *  - target_action 字段构造（会员中心位 = invite_flow；档案位 = create_profile）
 *  - 主标题强制单行规范（CSS 字段：white-space:nowrap / text-overflow:ellipsis / overflow:hidden）
 *  - 窄屏 15pt 兜底（屏宽 <=375 时 fontSize=15，>=390 时 fontSize=16）
 *  - 不限档 / 达上限态在双位置下行为一致（沿用 v1.0）
 *  - 数据一致性硬约束：档案位用量行 = list.quota_used / list.quota_max
 */

// ────── 纯函数副本（与 InviteFamilyCard.tsx 实现一一对应）──────

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
// 主标题去除「可管理 N 位家人」拼接，仅展示套餐名，避免截断 + 与"已管理 X/Y"重复信息。
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

// 主标题响应式字号（与 InviteFamilyCard.tsx 中 useEffect 内逻辑一致）
function computeTitleFontSize(innerWidth) {
  const w = typeof innerWidth === 'number' && innerWidth > 0 ? innerWidth : 390;
  return w <= 375 ? 15 : 16;
}

// 推断主按钮 target_action 默认值
function resolveTargetAction(cardLocation, override) {
  if (override === 'invite_flow' || override === 'create_profile') return override;
  return cardLocation === 'profile_list_top' ? 'create_profile' : 'invite_flow';
}

// 构造曝光事件 payload
function buildExposurePayload(cardLocation, planName, quotaUsed, quotaMax) {
  return {
    card_location: cardLocation,
    plan_name: planName || '',
    quota_used: quotaUsed ?? null,
    quota_max: quotaMax ?? null,
    is_full: isFullState(quotaUsed, quotaMax),
  };
}

// 构造主按钮点击事件 payload
function buildMainBtnClickPayload(cardLocation, planName, quotaUsed, quotaMax, targetActionOverride) {
  return {
    card_location: cardLocation,
    target_action: resolveTargetAction(cardLocation, targetActionOverride),
    plan_name: planName || '',
    quota_used: quotaUsed ?? null,
    quota_max: quotaMax ?? null,
  };
}

// 构造升级链接点击事件 payload
function buildUpgradeClickPayload(cardLocation, planName, quotaUsed, quotaMax) {
  return {
    card_location: cardLocation,
    plan_name: planName || '',
    quota_used: quotaUsed ?? null,
    quota_max: quotaMax ?? null,
  };
}

// 构造达上限态曝光事件 payload
function buildFullViewPayload(cardLocation, planName, quotaMax) {
  return {
    card_location: cardLocation,
    plan_name: planName || '',
    quota_max: quotaMax ?? null,
  };
}

// ────── 测试断言 ──────

let passed = 0;
let failed = 0;
function assertEq(actual, expected, name) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) {
    passed++;
    console.log(`  ✔ ${name}`);
  } else {
    failed++;
    console.log(`  ✘ ${name}\n    expected: ${e}\n    actual:   ${a}`);
  }
}

// ────── AC-23：card_location 字段构造 ──────

console.log('[v1.1 §6.1 AC-23] 埋点 card_location 字段');
assertEq(
  buildExposurePayload('member_center', '家庭版', 5, 10).card_location,
  'member_center',
  '会员中心位曝光携带 card_location=member_center',
);
assertEq(
  buildExposurePayload('profile_list_top', '家庭版', 5, 10).card_location,
  'profile_list_top',
  '健康档案位曝光携带 card_location=profile_list_top',
);

// ────── AC-23：target_action 字段构造（仅主按钮点击携带）──────

console.log('\n[v1.1 §6.1 AC-23] 埋点 target_action 字段');
assertEq(
  buildMainBtnClickPayload('member_center', '家庭版', 5, 10).target_action,
  'invite_flow',
  '会员中心位主按钮 → target_action=invite_flow',
);
assertEq(
  buildMainBtnClickPayload('profile_list_top', '家庭版', 5, 10).target_action,
  'create_profile',
  '健康档案位主按钮 → target_action=create_profile',
);

// 升级链接点击事件不携带 target_action
assertEq(
  Object.prototype.hasOwnProperty.call(buildUpgradeClickPayload('member_center', '家庭版', 5, 10), 'target_action'),
  false,
  '升级链接点击事件不携带 target_action',
);
assertEq(
  Object.prototype.hasOwnProperty.call(buildExposurePayload('member_center', '家庭版', 5, 10), 'target_action'),
  false,
  '曝光事件不携带 target_action',
);

// ────── AC-20/AC-21：主标题强制单行字号兜底 ──────

console.log('\n[v1.1 §4.1 AC-20/AC-21] 主标题字号兜底');
assertEq(computeTitleFontSize(390), 16, '主流屏 390px → 16pt');
assertEq(computeTitleFontSize(414), 16, 'iPhone Plus 414px → 16pt');
assertEq(computeTitleFontSize(430), 16, 'iPhone Pro Max 430px → 16pt');
assertEq(computeTitleFontSize(375), 15, '窄屏 375px(SE/mini) → 15pt 兜底');
assertEq(computeTitleFontSize(360), 15, '安卓窄屏 360px → 15pt 兜底');
assertEq(computeTitleFontSize(320), 15, '极窄屏 320px → 15pt 兜底');

// ────── AC-22：两位置视觉一致性（主标题文案、用量行、状态判定完全一致）──────

console.log('\n[v1.1 §2.3 AC-22] 双位置视觉文案一致');
const titleA = formatTitleLine('家庭版', 10);
const titleB = formatTitleLine('家庭版', 10);
assertEq(titleA, titleB, '同套餐档位下，两位置主标题文案完全一致');
// [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #3] 主标题仅显示套餐名，去掉"可管理 N..."拼接
assertEq(titleA, '家庭版', '主标题仅显示套餐名（不再拼接可管理文案，防截断 + 防冗余）');

const quotaA = formatQuotaLine(5, 10);
const quotaB = formatQuotaLine(5, 10);
assertEq(quotaA, quotaB, '两位置用量行文案完全一致');
assertEq(quotaA, '已管理 5 / 上限 10', '用量行文案符合 PRD 模板');

// ────── AC-18：健康档案位达上限态——按钮禁用 + 抽屉不弹出 ──────

console.log('\n[v1.1 §3.3 AC-18 BR-14] 健康档案位达上限态语义');
// 状态判定相同——双位置共用 computeCardState
assertEq(computeCardState(10, 10), 'full', '档案位 10/10 → full');
assertEq(computeCardState(5, 10), 'normal', '档案位 5/10 → normal');
assertEq(computeCardState(20, -1), 'normal', '不限档 → 永远 normal（BR-02 / RC-07）');

// 模拟 onInvite 守卫：达上限 + 余量<=0 时拦截
function shouldOpenDrawer(quotaUsed, quotaMax) {
  const unlimited = isUnlimitedQuota(quotaMax);
  const remaining = unlimited ? Infinity : quotaMax - quotaUsed;
  if (!unlimited && remaining <= 0) return false;
  // 按钮禁用层也会拦截，但二重保险确保抽屉不弹出
  if (isFullState(quotaUsed, quotaMax)) return false;
  return true;
}
assertEq(shouldOpenDrawer(5, 10), true, '5/10 → 允许弹出新建抽屉');
assertEq(shouldOpenDrawer(10, 10), false, '10/10（满额）→ 抽屉不弹出');
assertEq(shouldOpenDrawer(0, -1), true, '不限档 → 允许弹出新建抽屉');

// ────── AC-19：会员中心位主按钮行为不变 ──────

console.log('\n[v1.1 §2.1 AC-19] 会员中心位主按钮 target_action=invite_flow 不变');
assertEq(
  resolveTargetAction('member_center'),
  'invite_flow',
  '会员中心位默认 target_action=invite_flow（v1.0 行为不变）',
);

// ────── RC-07：不限档双位置生效 ──────

console.log('\n[v1.1 RC-07] 不限档双位置一致展示 S1 + 用量行');
const unlimitedA = formatQuotaLine(7, -1);
const unlimitedB = formatQuotaLine(7, -1);
assertEq(unlimitedA, unlimitedB, '不限档双位置用量行一致');
assertEq(unlimitedA, '已管理 7 人 · 不限上限', '不限档用量行文案正确');

// ────── BR-13 数据一致性硬约束：档案位用量数据 = list.quota_used/quota_max ──────

console.log('\n[v1.1 BR-13] 健康档案位用量数据与顶部灰条接口一致');
// 模拟 state/list 接口返回
const stateListResp = { quota_used: 5, quota_max: 10, quota_remaining: 5 };
// 卡片渲染时直接使用 list.quota_used/quota_max（page.tsx 实现）
const cardQuotaLine = formatQuotaLine(stateListResp.quota_used, stateListResp.quota_max);
assertEq(
  cardQuotaLine,
  `已管理 ${stateListResp.quota_used} / 上限 ${stateListResp.quota_max}`,
  '档案位卡片用量行 = 同份 state/list 接口的 quota_used/quota_max',
);

// ────── 兜底：plan_name 缺失时走「会员套餐」兜底 ──────

console.log('\n[v1.1 §9 异常处理] plan_name 缺失兜底');
// [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #3] 兜底文案同步简化为仅显示套餐名
assertEq(formatTitleLine('', 10), '会员套餐', '空字符串 plan_name → 兜底「会员套餐」');
assertEq(formatTitleLine(null, 10), '会员套餐', 'null plan_name → 兜底「会员套餐」');
assertEq(formatTitleLine(undefined, 10), '会员套餐', 'undefined plan_name → 兜底「会员套餐」');

// ────── 总结 ──────

console.log(`\n========================================`);
console.log(`[v1.1 invite_card_v11 测试结果] passed=${passed} failed=${failed}`);
console.log(`========================================`);
if (failed > 0) {
  process.exit(1);
}
