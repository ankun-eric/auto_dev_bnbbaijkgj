// [BUG-FIX-RESCHEDULE-V2 2026-05-07] 服务器时间工具（微信小程序版本）。
// 用途：改约弹窗按服务器时间过滤已过去的整段时段。

const { get } = require('./request');

let _offsetMs = 0;
let _initialized = false;
let _initPromise = null;
let _lastFailed = false;

function initServerTime() {
  if (_initialized) return Promise.resolve();
  if (_initPromise) return _initPromise;
  _initPromise = new Promise((resolve) => {
    get('/api/system/server-time', {}, { showLoading: false, suppressErrorToast: true })
      .then((res) => {
        const data = (res && res.data) || res || {};
        const serverMs = Number(data.now_unix_ms);
        if (isFinite(serverMs) && serverMs > 0) {
          _offsetMs = serverMs - Date.now();
          _initialized = true;
          _lastFailed = false;
        } else {
          _lastFailed = true;
        }
        resolve();
      })
      .catch(() => {
        _lastFailed = true;
        resolve();
      })
      .then(() => {
        _initPromise = null;
      });
  });
  return _initPromise;
}

function getServerNow() {
  return new Date(Date.now() + _offsetMs);
}

function isServerTimeUnreliable() {
  return _lastFailed && !_initialized;
}

function isSameDayAsServer(dateLike) {
  let d;
  if (dateLike instanceof Date) {
    d = dateLike;
  } else if (typeof dateLike === 'string') {
    // 兼容 'yyyy-MM-dd' 格式
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(dateLike);
    if (m) {
      d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    } else {
      d = new Date(dateLike);
    }
  } else {
    return false;
  }
  const now = getServerNow();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

function parseSlotRange(slot) {
  const m = /^(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})$/.exec(slot || '');
  if (!m) return null;
  const sh = Number(m[1]);
  const sm = Number(m[2]);
  const eh = Number(m[3]);
  const em = Number(m[4]);
  if ([sh, sm, eh, em].some((n) => isNaN(n))) return null;
  return [sh * 60 + sm, eh * 60 + em];
}

/**
 * 过滤已过去的整段时段。
 * - selectedDateStr: 'yyyy-MM-dd' 格式
 * - slots: 时段池数组
 * - 仅当 selectedDateStr == 服务器今天 时过滤；其它日期不过滤
 */
function filterPastSlots(selectedDateStr, slots) {
  if (!selectedDateStr || !Array.isArray(slots) || slots.length === 0) return slots || [];
  if (!isSameDayAsServer(selectedDateStr)) return slots;
  const now = getServerNow();
  const nowMin = now.getHours() * 60 + now.getMinutes();
  const result = [];
  for (let i = 0; i < slots.length; i++) {
    const r = parseSlotRange(slots[i]);
    if (!r) {
      result.push(slots[i]);
      continue;
    }
    if (r[1] > nowMin) {
      result.push(slots[i]);
    }
  }
  return result;
}

module.exports = {
  initServerTime,
  getServerNow,
  isServerTimeUnreliable,
  isSameDayAsServer,
  filterPastSlots,
};
