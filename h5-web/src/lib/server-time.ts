/**
 * [BUG-FIX-RESCHEDULE-V2 2026-05-07] 服务器时间工具。
 *
 * 用途：
 * - 改约弹窗按"服务器时间"过滤已过去的整段时段，避免依赖客户端本地时间被人为
 *   调快/调慢绕过过滤。
 *
 * 实现：
 * - 启动时（或首次需要服务器时间时）调用 GET /api/system/server-time，记录
 *   服务器与本地的偏移；之后 getServerNow() 返回 (Date.now() + offset)。
 * - 接口失败时降级使用本地时间，并在外部 UI 中提示"网络异常，时段以服务器为准"。
 */
import api from './api';

let _offsetMs = 0;
let _initialized = false;
let _initializing: Promise<void> | null = null;
let _lastFailed = false;

/**
 * 初始化服务器时间偏移。可重复调用，幂等：
 * - 首次调用：发起接口请求并记录 offset
 * - 后续调用：复用首次的 Promise，避免并发重复请求
 */
export function initServerTime(): Promise<void> {
  if (_initialized) return Promise.resolve();
  if (_initializing) return _initializing;
  _initializing = (async () => {
    try {
      const res: any = await api.get('/api/system/server-time');
      const data = res?.data || res;
      const serverMs = Number(data?.now_unix_ms);
      if (Number.isFinite(serverMs) && serverMs > 0) {
        _offsetMs = serverMs - Date.now();
        _initialized = true;
        _lastFailed = false;
        return;
      }
      _lastFailed = true;
    } catch (_e) {
      _lastFailed = true;
    } finally {
      _initializing = null;
    }
  })();
  return _initializing;
}

/**
 * 获取服务器时间（毫秒级）。如果尚未初始化，则用本地时间兜底。
 */
export function getServerNow(): Date {
  return new Date(Date.now() + _offsetMs);
}

/**
 * 上次拉取服务器时间是否失败（供 UI 顶部提示用户）。
 */
export function isServerTimeUnreliable(): boolean {
  return _lastFailed && !_initialized;
}

/**
 * 强制重新拉取服务器时间偏移（用于失败重试场景）。
 */
export function refreshServerTime(): Promise<void> {
  _initialized = false;
  _initializing = null;
  return initServerTime();
}

/**
 * 判断指定 Date 是否与服务器时间为同一天（按本地时区计算 yyyy-MM-dd）。
 */
export function isSameDayAsServer(d: Date): boolean {
  const now = getServerNow();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

/**
 * 解析"HH:mm-HH:mm"形式的时段字符串，返回 [开始小时数*60+分钟, 结束小时数*60+分钟]。
 * 跨日 24:00 → 1440。
 */
export function parseSlotRange(slot: string): [number, number] | null {
  const m = /^(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})$/.exec(slot || '');
  if (!m) return null;
  const sh = Number(m[1]);
  const sm = Number(m[2]);
  const eh = Number(m[3]);
  const em = Number(m[4]);
  if ([sh, sm, eh, em].some((n) => Number.isNaN(n))) return null;
  return [sh * 60 + sm, eh * 60 + em];
}

/**
 * 过滤已过去的整段时段。
 * - selectedDate：用户选中的日期（Date 对象，仅用 yyyy-MM-dd）
 * - slots：原始时段池（如 ['06:00-08:00', '08:00-10:00', ...]）
 * - 仅当 selectedDate == 服务器今天 时按 (时段结束 > 服务器现在的分钟数) 过滤；
 *   其它日期不过滤（全部展示）。
 */
export function filterPastSlots(
  selectedDate: Date | null,
  slots: string[],
): string[] {
  if (!selectedDate || !Array.isArray(slots) || slots.length === 0) return slots || [];
  if (!isSameDayAsServer(selectedDate)) return slots;
  const now = getServerNow();
  const nowMin = now.getHours() * 60 + now.getMinutes();
  const result: string[] = [];
  for (const s of slots) {
    const r = parseSlotRange(s);
    if (!r) {
      // 解析失败时保守保留
      result.push(s);
      continue;
    }
    const [, end] = r;
    if (end > nowMin) {
      result.push(s);
    }
  }
  return result;
}
