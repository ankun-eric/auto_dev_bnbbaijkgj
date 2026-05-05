/**
 * [PRD-01 全平台固定时段切片体系 v1.0] 微信小程序端 9 段时段常量与工具
 *
 * 全平台固定 9 段（每段 2 小时，最早 06:00，最晚 24:00），凌晨 00:00-06:00 不开放。
 * 与后端 backend/app/utils/time_slots.py 保持完全一致；
 * PRD §4 异常处理：当 GET /api/common/time-slots 接口失败时，前端使用本常量兜底，
 * 确保下单 / 改期 / 时段选择不阻塞。
 */

const FIXED_TIME_SLOTS = Object.freeze([
  { slot_no: 1, start: '06:00', end: '08:00' },
  { slot_no: 2, start: '08:00', end: '10:00' },
  { slot_no: 3, start: '10:00', end: '12:00' },
  { slot_no: 4, start: '12:00', end: '14:00' },
  { slot_no: 5, start: '14:00', end: '16:00' },
  { slot_no: 6, start: '16:00', end: '18:00' },
  { slot_no: 7, start: '18:00', end: '20:00' },
  { slot_no: 8, start: '20:00', end: '22:00' },
  { slot_no: 9, start: '22:00', end: '24:00' },
]);

function slotLabel(slotNo) {
  if (!Number.isInteger(slotNo) || slotNo < 1 || slotNo > 9) return '';
  const s = FIXED_TIME_SLOTS[slotNo - 1];
  return s.start + '-' + s.end;
}

function appointmentToSlot(input) {
  if (!input) return null;
  const dt = input instanceof Date ? input : new Date(input);
  if (isNaN(dt.getTime())) return null;
  const h = dt.getHours();
  if (h < 6) return null;
  if (h >= 22) return 9;
  return Math.floor((h - 6) / 2) + 1;
}

/**
 * 调用 `/api/common/time-slots` 拉取，失败时返回兜底常量。
 * fetcher 由调用方注入（如使用 utils/request.js 封装的 GET）。
 */
function fetchTimeSlotsWithFallback(fetcher) {
  return Promise.resolve()
    .then(() => fetcher())
    .then((resp) => {
      const slots = resp && resp.slots;
      if (Array.isArray(slots) && slots.length === 9) return slots;
      return FIXED_TIME_SLOTS;
    })
    .catch(() => FIXED_TIME_SLOTS);
}

module.exports = {
  FIXED_TIME_SLOTS,
  slotLabel,
  appointmentToSlot,
  fetchTimeSlotsWithFallback,
};
