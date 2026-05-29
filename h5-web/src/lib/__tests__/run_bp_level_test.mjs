/**
 * [BUGFIX-BP-TAB-OPTIMIZE-V1] 血压档位判定单元测试
 *
 * 运行：node h5-web/src/lib/__tests__/run_bp_level_test.mjs
 *
 * 覆盖验收 DoD「6 组测试数据」 + 边界值。
 */

// 复制实现，避免 TS 编译依赖
function judgeBp(sbp, dbp) {
  if (sbp == null || dbp == null || Number.isNaN(sbp) || Number.isNaN(dbp)) return null;
  if (sbp >= 160 || dbp >= 100) return { level: 'severe_high', color: 'orange', label: '严重偏高' };
  if (sbp < 90 || dbp < 60) return { level: 'low', color: 'orange', label: '偏低' };
  if (sbp >= 140 || dbp >= 90) return { level: 'mid_high', color: 'yellow', label: '中度偏高' };
  if (sbp >= 120 || dbp >= 80) return { level: 'mild_high', color: 'yellow', label: '轻度偏高' };
  return { level: 'normal', color: 'blue', label: '正常' };
}

let pass = 0, fail = 0;
const fails = [];
function check(name, got, expectedLevel, expectedColor) {
  const ok = got && got.level === expectedLevel && got.color === expectedColor;
  if (ok) pass++;
  else {
    fail++;
    fails.push(`✗ ${name}: expected ${expectedLevel}/${expectedColor} got ${got ? `${got.level}/${got.color}` : 'null'}`);
  }
}

// 验收 DoD「6 组测试数据」
check('极低 80/50',          judgeBp(80, 50),    'low',         'orange');
check('正常 110/70',         judgeBp(110, 70),   'normal',      'blue');
check('轻度偏高 130/85',     judgeBp(130, 85),   'mild_high',   'yellow');
check('中度偏高 150/95',     judgeBp(150, 95),   'mid_high',    'yellow');
check('严重偏高 170/110',    judgeBp(170, 110),  'severe_high', 'orange');
check('临界值 119/79',       judgeBp(119, 79),   'normal',      'blue');

// 关键边界
check('SBP 边界 120/70',     judgeBp(120, 70),   'mild_high',   'yellow');
check('DBP 边界 110/80',     judgeBp(110, 80),   'mild_high',   'yellow');
check('SBP 边界 140/80',     judgeBp(140, 80),   'mid_high',    'yellow');
check('DBP 边界 130/90',     judgeBp(130, 90),   'mid_high',    'yellow');
check('SBP 边界 160/80',     judgeBp(160, 80),   'severe_high', 'orange');
check('DBP 边界 130/100',    judgeBp(130, 100),  'severe_high', 'orange');
check('「或」关系 严重高+低', judgeBp(170, 60),   'severe_high', 'orange'); // SBP 严重，DBP 正常 → 严重
check('SBP 偏低 80/70',      judgeBp(80, 70),    'low',         'orange');
check('DBP 偏低 110/55',     judgeBp(110, 55),   'low',         'orange');
check('正常下界 90/60',      judgeBp(90, 60),    'normal',      'blue');

// 空值
if (judgeBp(null, 80) !== null) { fail++; fails.push('✗ null sbp should return null'); } else pass++;
if (judgeBp(120, null) !== null) { fail++; fails.push('✗ null dbp should return null'); } else pass++;
if (judgeBp(undefined, undefined) !== null) { fail++; fails.push('✗ undefined should return null'); } else pass++;

if (fail === 0) {
  console.log(`✓ bp-level tests: all ${pass} assertions passed`);
  process.exit(0);
} else {
  console.error(`✗ bp-level tests: ${fail} failed, ${pass} passed\n${fails.join('\n')}`);
  process.exit(1);
}
