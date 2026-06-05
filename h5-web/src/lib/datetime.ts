/**
 * [BUG_FIX_TIMEZONE_GLOBAL_20260517] 统一时间格式化工具（H5 / Web 端）
 * [PRD-HOME-SAFETY-V1 BUGFIX 2026-05-27] 后端统一 utcnow() + 'Z'
 * [BUG_FIX_H5_GLOBAL_CRASH_20260528] 恢复全站使用的导出函数
 * [BUG_FIX_TIMEZONE_BJ_UNIFIED_20260530] 全局固定北京时间口径，新增 formatFriendlyTime / formatFullTime
 *
 * 设计目标（医疗类产品标准）：
 * - 时区基准固定为北京时间（东八区 +08:00），与设备本地时区无关
 * - 后端 datetime 应统一以 UTC（"+00:00" 或 "Z" 后缀）返回；老接口若无时区
 *   后缀（如 "2026-05-30 10:32:41" / "2026-05-30T02:32:41"），强制按 UTC 解析
 *   再换算为北京时间显示，避免依赖浏览器/设备本地时区
 * - 全前端任何展示后端时间的位置都必须使用本文件提供的函数，禁止散写 `new Date(serverTimeStr)`
 */

const BJ_OFFSET_MIN = 8 * 60;

export function parseServerTime(iso?: string | number | Date | null): Date | null {
  if (iso === null || iso === undefined || iso === '') return null;
  if (iso instanceof Date) return Number.isNaN(iso.getTime()) ? null : iso;
  if (typeof iso === 'number') {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  let s = String(iso).trim();
  if (!s) return null;
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/.test(s);
  if (!hasTz) {
    if (s.includes(' ') && !s.includes('T')) s = s.replace(' ', 'T');
    s = s + 'Z';
  }
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
}

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

interface BjParts {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
}

function toBjParts(d: Date): BjParts {
  const utcMs = d.getTime();
  const bjMs = utcMs + BJ_OFFSET_MIN * 60 * 1000;
  const bj = new Date(bjMs);
  return {
    year: bj.getUTCFullYear(),
    month: bj.getUTCMonth() + 1,
    day: bj.getUTCDate(),
    hour: bj.getUTCHours(),
    minute: bj.getUTCMinutes(),
    second: bj.getUTCSeconds(),
  };
}

function nowBjParts(): BjParts {
  return toBjParts(new Date());
}

function bjStartOfDayUtcMs(p: BjParts): number {
  return Date.UTC(p.year, p.month - 1, p.day) - BJ_OFFSET_MIN * 60 * 1000;
}

export function formatDateTime(
  iso?: string | number | Date | null,
  pattern: string = 'YYYY-MM-DD HH:mm:ss',
): string {
  const d = parseServerTime(iso);
  if (!d) return iso == null || iso === '' ? '-' : String(iso);
  const p = toBjParts(d);
  return pattern
    .replace('YYYY', String(p.year))
    .replace('MM', pad2(p.month))
    .replace('DD', pad2(p.day))
    .replace('HH', pad2(p.hour))
    .replace('mm', pad2(p.minute))
    .replace('ss', pad2(p.second));
}

export function formatFullTime(iso?: string | number | Date | null): string {
  return formatDateTime(iso, 'YYYY-MM-DD HH:mm:ss');
}

export function formatDate(iso?: string | number | Date | null): string {
  return formatDateTime(iso, 'YYYY-MM-DD');
}

export function formatTime(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  const p = toBjParts(d);
  return `${pad2(p.hour)}:${pad2(p.minute)}`;
}

export function formatRelativeTime(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  const diffMs = Date.now() - d.getTime();
  if (diffMs < 0) return formatDateTime(iso);
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return '刚刚';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} 分钟前`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour} 小时前`;
  const day = Math.floor(hour / 24);
  if (day < 30) return `${day} 天前`;
  return formatDate(iso);
}

/**
 * [BUG_FIX_TIMEZONE_BJ_UNIFIED_20260530] 友好时间显示（北京时间口径）
 * - 今日（按北京时间切日）→ 今日 HH:mm
 * - 昨日 → 昨日 HH:mm
 * - 2~6 天前 → X 天前
 * - 7 天及以上但同年 → MM-DD
 * - 跨年 → YYYY-MM-DD
 * 与设备本地时区无关，海外/UTC 浏览器看到的也是北京时间。
 */
export function formatFriendlyTime(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  const target = toBjParts(d);
  const now = nowBjParts();
  const targetStartUtc = bjStartOfDayUtcMs(target);
  const todayStartUtc = bjStartOfDayUtcMs(now);
  const diffDays = Math.floor((todayStartUtc - targetStartUtc) / 86400000);
  const hh = pad2(target.hour);
  const mm = pad2(target.minute);
  if (diffDays === 0) return `今日 ${hh}:${mm}`;
  if (diffDays === 1) return `昨日 ${hh}:${mm}`;
  if (diffDays >= 2 && diffDays <= 6) return `${diffDays} 天前`;
  if (target.year === now.year) return `${pad2(target.month)}-${pad2(target.day)}`;
  return `${target.year}-${pad2(target.month)}-${pad2(target.day)}`;
}

/**
 * [BUG_FIX_MEDICAL_RECORDS_TIME_FORMAT_20260605] 就医资料记录列表时间格式化
 * - 今天的记录：今日 HH:mm
 * - 非今天的记录：YYYY-MM-DD HH:mm
 * 与设备本地时区无关，统一使用北京时间。
 */
export function formatRecordTime(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  const now = nowBjParts();
  const target = toBjParts(d);
  const targetStartUtc = bjStartOfDayUtcMs(target);
  const todayStartUtc = bjStartOfDayUtcMs(now);
  const diffDays = Math.floor((todayStartUtc - targetStartUtc) / 86400000);

  if (diffDays === 0) {
    return `今日 ${pad2(target.hour)}:${pad2(target.minute)}`;
  }
  return formatDateTime(iso, 'YYYY-MM-DD HH:mm');
}

/**
 * [PRD-SAFETY-ROPE-SPOKEN-TIME 2026-06-06] 数字安全绳 Banner 时间口语化
 * 将时段（小时数）转为口语化称呼
 */
function hourPeriod(hour: number): string {
  if (hour >= 0 && hour < 6) return '凌晨';
  if (hour >= 6 && hour < 12) return '上午';
  if (hour >= 12 && hour < 14) return '中午';
  if (hour >= 14 && hour < 18) return '下午';
  return '晚上';
}

/**
 * [PRD-SAFETY-ROPE-SPOKEN-TIME 2026-06-06] 口语化分钟显示
 * 整点→点，半→半，其他→:xx
 */
function spokenMinutes(minute: number): string {
  if (minute === 0) return '点';
  if (minute === 30) return '点半';
  return `:${pad2(minute)}`;
}

/**
 * [PRD-SAFETY-ROPE-SPOKEN-TIME 2026-06-06] 口语化日期前缀
 * 今天/明天/后天/绝对日期
 */
function spokenDatePrefix(diffDays: number, target: BjParts, now: BjParts): string {
  if (diffDays === 0) return '今天';
  if (diffDays === -1) return '明天';
  if (diffDays === -2) return '后天';
  if (target.year === now.year) return `${target.month}月${target.day}日`;
  return `${target.year}年${target.month}月${target.day}日`;
}

/**
 * [PRD-SAFETY-ROPE-SPOKEN-TIME 2026-06-06] 口语化日期前缀（用于"上次签到"——过去时间）
 */
function spokenDatePrefixPast(diffDays: number, target: BjParts, now: BjParts): string {
  if (diffDays === 0) return '今天';
  if (diffDays === 1) return '昨天';
  if (diffDays >= 2 && diffDays <= 6) return `${diffDays}天前`;
  if (target.year === now.year) return `${target.month}月${target.day}日`;
  return `${target.year}年${target.month}月${target.day}日`;
}

/**
 * [PRD-SAFETY-ROPE-SPOKEN-TIME 2026-06-06] 精确时间后缀（括号内）
 */
function preciseSuffix(target: BjParts, now: BjParts): string {
  if (target.year === now.year) {
    return `${pad2(target.month)}-${pad2(target.day)} ${pad2(target.hour)}:${pad2(target.minute)}`;
  }
  return `${target.year}-${pad2(target.month)}-${pad2(target.day)} ${pad2(target.hour)}:${pad2(target.minute)}`;
}

/**
 * [PRD-SAFETY-ROPE-SPOKEN-TIME 2026-06-06] 口语化"上次签到"时间
 * 格式：今天下午3:30已签到（06-06 15:30）
 * 用于数字安全绳 Banner 区域的"上次签到"时间显示
 */
export function formatSpokenTime(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  const target = toBjParts(d);
  const now = nowBjParts();
  const targetStartUtc = bjStartOfDayUtcMs(target);
  const todayStartUtc = bjStartOfDayUtcMs(now);
  const diffDays = Math.floor((todayStartUtc - targetStartUtc) / 86400000);
  const period = hourPeriod(target.hour);
  const hour = target.hour === 0 ? 12 : target.hour > 12 ? target.hour - 12 : target.hour;
  const minStr = spokenMinutes(target.minute);
  const prefix = spokenDatePrefixPast(diffDays, target, now);
  const suffix = preciseSuffix(target, now);
  return `${prefix}${period}${hour}${minStr}已签到（${suffix}）`;
}

/**
 * [PRD-SAFETY-ROPE-SPOKEN-TIME 2026-06-06] 口语化"下次签到截止"时间
 * 格式：最晚明天下午3点半前签到（06-07 15:30）
 * 用于数字安全绳 Banner 区域的"下次签到截止"时间显示
 */
export function formatSpokenDeadline(iso?: string | number | Date | null): string {
  const d = parseServerTime(iso);
  if (!d) return '';
  const target = toBjParts(d);
  const now = nowBjParts();
  const targetStartUtc = bjStartOfDayUtcMs(target);
  const todayStartUtc = bjStartOfDayUtcMs(now);
  const diffDays = Math.floor((todayStartUtc - targetStartUtc) / 86400000);
  const period = hourPeriod(target.hour);
  const hour = target.hour === 0 ? 12 : target.hour > 12 ? target.hour - 12 : target.hour;
  const minStr = spokenMinutes(target.minute);
  const prefix = spokenDatePrefix(diffDays, target, now);
  const suffix = preciseSuffix(target, now);
  return `最晚${prefix}${period}${hour}${minStr}前签到（${suffix}）`;
}
