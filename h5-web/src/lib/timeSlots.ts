/**
 * [PRD-01 全平台固定时段切片体系 v1.0] H5 端 9 段时段常量与工具
 *
 * 全平台固定 9 段（每段 2 小时，最早 06:00，最晚 24:00），凌晨 00:00-06:00 不开放。
 * 与后端 `app/utils/time_slots.py` 保持完全一致；
 * PRD §4 异常处理：当 `/api/common/time-slots` 接口失败时，前端使用本常量兜底，
 * 确保下单 / 改期 / 看板渲染不阻塞。
 */

export interface TimeSlotItem {
  slot_no: number;
  start: string;
  end: string;
}

/** 段号 1-9 与后端响应一致的时段配置（兜底常量） */
export const FIXED_TIME_SLOTS: ReadonlyArray<TimeSlotItem> = [
  { slot_no: 1, start: "06:00", end: "08:00" },
  { slot_no: 2, start: "08:00", end: "10:00" },
  { slot_no: 3, start: "10:00", end: "12:00" },
  { slot_no: 4, start: "12:00", end: "14:00" },
  { slot_no: 5, start: "14:00", end: "16:00" },
  { slot_no: 6, start: "16:00", end: "18:00" },
  { slot_no: 7, start: "18:00", end: "20:00" },
  { slot_no: 8, start: "20:00", end: "22:00" },
  { slot_no: 9, start: "22:00", end: "24:00" },
] as const;

/** 段号 1-9 → "06:00-08:00" 形式标签 */
export function slotLabel(slotNo: number): string {
  if (!Number.isInteger(slotNo) || slotNo < 1 || slotNo > 9) return "";
  const s = FIXED_TIME_SLOTS[slotNo - 1];
  return `${s.start}-${s.end}`;
}

/**
 * 时间 → 段号 1-9（凌晨段 / 无效输入返回 null）。
 * 仅按 hour 归段；跨日订单按起始时间归段（PRD R-01-03）。
 */
export function appointmentToSlot(input: Date | string | null | undefined): number | null {
  if (!input) return null;
  const dt = typeof input === "string" ? new Date(input) : input;
  if (Number.isNaN(dt.getTime())) return null;
  const h = dt.getHours();
  if (h < 6) return null;
  if (h >= 22) return 9;
  return Math.floor((h - 6) / 2) + 1;
}

/**
 * 调用 `/api/common/time-slots` 拉取，失败时返回兜底常量。
 * 调用方需自行传入已封装好的 fetcher（避免与项目 api 客户端耦合）。
 */
export async function fetchTimeSlotsWithFallback(
  fetcher: () => Promise<{ slots: TimeSlotItem[] } | null | undefined>,
): Promise<ReadonlyArray<TimeSlotItem>> {
  try {
    const resp = await fetcher();
    const slots = resp?.slots;
    if (Array.isArray(slots) && slots.length === 9) {
      return slots;
    }
  } catch (_err) {
    // 接口失败 → 走兜底
  }
  return FIXED_TIME_SLOTS;
}
