/**
 * [双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0]
 * 改约失败错误码 → 文案映射表 + 统一错误展示工具。
 *
 * 与后端 backend/app/api/unified_orders.py 中的 RESCHEDULE_* 错误码常量一致。
 * 一旦后端新增了错误码而前端没来得及加映射，则展示后端 message 字段作为兜底，
 * 而不是统一的"预约失败"。
 */

export const RESCHEDULE_ERROR_TEXT: Record<string, string> = {
  RESCHEDULE_NO_PERMISSION: '无权操作此订单',
  RESCHEDULE_ORDER_NOT_FOUND: '订单不存在或无权操作此订单',
  RESCHEDULE_ORDER_STATUS_INVALID: '当前订单状态不允许改约',
  RESCHEDULE_LIMIT_EXCEEDED: '该订单已达改约次数上限，无法继续改约',
  RESCHEDULE_NOT_ALLOWED: '该商品不支持改约',
  RESCHEDULE_TIME_EXPIRED: '所选时段已过期，请选择未来时间',
  RESCHEDULE_TIME_OUT_OF_RANGE: '所选日期超出可改约范围',
  RESCHEDULE_TIME_CONFLICT: '所选时段已被预约满，请选其他时段',
  RESCHEDULE_REFUND_IN_PROGRESS: '该订单退款处理中，暂不允许调整预约时间',
  RESCHEDULE_PARTIALLY_USED: '该订单已部分核销，无法修改预约时间',
  RESCHEDULE_INTERNAL_ERROR: '改约失败，请稍后重试或联系客服',
};

/**
 * 从 axios 抛出的错误对象提取最具体的中文文案。
 * 优先级：
 *   1. 结构化 detail（{code, message, detail}）→ 用 code 映射，无映射则用 message
 *   2. 旧版 detail 字符串 → 直接显示
 *   3. detail 为数组（Pydantic 校验错误）→ 取第一条 msg
 *   4. data.message 字段
 *   5. 网络层错误（无 response）→ "网络异常，请稍后重试"
 *   6. 都没有 → "改约失败，请稍后重试或联系客服"
 */
export function extractRescheduleErrorText(err: unknown): string {
  // axios error
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const e = err as any;
  const data = e?.response?.data;
  if (data) {
    const detail = data.detail;
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const code = typeof detail.code === 'string' ? detail.code : '';
      if (code && RESCHEDULE_ERROR_TEXT[code]) {
        return RESCHEDULE_ERROR_TEXT[code];
      }
      if (typeof detail.message === 'string' && detail.message) {
        return detail.message;
      }
      if (typeof detail.detail === 'string' && detail.detail) {
        return detail.detail;
      }
    }
    if (typeof detail === 'string' && detail) return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (typeof first === 'string') return first;
      if (first && typeof first.msg === 'string') return first.msg;
    }
    if (typeof data.message === 'string' && data.message) return data.message;
    if (typeof data.code === 'string' && RESCHEDULE_ERROR_TEXT[data.code]) {
      return RESCHEDULE_ERROR_TEXT[data.code];
    }
  }
  // 网络层错误（无 response）
  if (e && !e.response) {
    if (e.code === 'ECONNABORTED' || /timeout/i.test(String(e.message))) {
      return '网络异常，请稍后重试';
    }
    if (e.message && /Network Error/i.test(String(e.message))) {
      return '网络异常，请稍后重试';
    }
  }
  // HTTP 状态码兜底
  if (e?.response?.status) {
    return `改约失败（${e.response.status}），请稍后重试或联系客服`;
  }
  return '改约失败，请稍后重试或联系客服';
}
