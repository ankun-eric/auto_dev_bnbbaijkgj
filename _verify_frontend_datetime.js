// [BUG_FIX_TIMEZONE_GLOBAL_20260517] 验证前端 datetime 工具的兼容性
// 跑命令：node _verify_frontend_datetime.js

const { parseServerTime, formatRelativeTime, formatDateTime } = require('./miniprogram/utils/datetime.js');

function assert(cond, msg) {
  if (!cond) {
    console.error('FAIL:', msg);
    process.exitCode = 1;
  } else {
    console.log('PASS:', msg);
  }
}

// 1. 带 UTC 后缀
const iso1 = new Date(Date.now() - 5 * 60 * 1000).toISOString(); // 5 分钟前
const d1 = parseServerTime(iso1);
assert(d1 && Math.abs(Date.now() - d1.getTime() - 5 * 60 * 1000) < 2000, '带Z后缀 5分钟前 解析正确');
assert(formatRelativeTime(iso1) === '5 分钟前', '带Z后缀 → "5 分钟前"');

// 2. 不带时区后缀（老接口模拟） - 现在的时间戳去掉 Z
const isoNoTz = new Date(Date.now() - 5 * 60 * 1000).toISOString().replace('Z', '').replace(/\.\d+$/, '');
const d2 = parseServerTime(isoNoTz);
assert(d2 && Math.abs(Date.now() - d2.getTime() - 5 * 60 * 1000) < 5000, '无时区后缀 5分钟前 也按 UTC 解析正确');
const rel2 = formatRelativeTime(isoNoTz);
assert(rel2 === '5 分钟前' || rel2 === '4 分钟前' || rel2 === '刚刚', `无时区后缀 → 相对时间(${rel2}) 不应是 8 小时前`);

// 3. 带 +08:00 后缀（aware）
const isoCN = new Date(Date.now() - 5 * 60 * 1000).toISOString().replace('Z', '+00:00');
assert(formatRelativeTime(isoCN) === '5 分钟前', '带 +00:00 → "5 分钟前"');

// 4. null/空
assert(parseServerTime(null) === null, 'null → null');
assert(parseServerTime('') === null, '"" → null');
assert(formatRelativeTime(null) === '', 'null 相对时间 → ""');

// 5. 刚刚
const now = new Date().toISOString();
assert(formatRelativeTime(now) === '刚刚', '当前时间 → "刚刚"');

// 6. 用户场景验证：模拟服务端返回"刚刚"的对话时间
const justSavedNoTz = new Date().toISOString().replace('Z', '').replace(/\.\d+$/, '');
const r = formatRelativeTime(justSavedNoTz);
assert(r === '刚刚' || r === '1 分钟前' || r === '2 分钟前', `[关键场景] 刚保存的对话即便没有时区后缀也显示"${r}"，而不是"8小时前"`);

console.log('---- 全部测试完成 ----');
