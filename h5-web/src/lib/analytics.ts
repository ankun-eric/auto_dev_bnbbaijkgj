/**
 * 前端埋点工具（PRD v1.1 §6 EVT-01~EVT-10）
 *
 * 设计原则：
 * - 失败静默：埋点失败不能影响主业务流程
 * - 队列缓冲：网络异常时本地排队，恢复后批量回传
 * - 通用化：trackEvent(name, params) 即可，所有 ai_chat_* 事件统一走这一处
 */

import api from '@/lib/api';

interface TrackPayload {
  event: string;
  params: Record<string, any>;
  ts: number;
}

const QUEUE_KEY = '__track_event_queue__';
const MAX_QUEUE = 50;

function getStoredQueue(): TrackPayload[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(QUEUE_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.slice(0, MAX_QUEUE) : [];
  } catch {
    return [];
  }
}

function setStoredQueue(arr: TrackPayload[]) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(arr.slice(-MAX_QUEUE)));
  } catch {}
}

async function sendOne(payload: TrackPayload): Promise<boolean> {
  try {
    await api.post('/api/analytics/track', payload);
    return true;
  } catch {
    return false;
  }
}

let flushing = false;

async function flushQueue() {
  if (flushing) return;
  flushing = true;
  try {
    const q = getStoredQueue();
    if (q.length === 0) return;
    const remaining: TrackPayload[] = [];
    for (const item of q) {
      const ok = await sendOne(item);
      if (!ok) remaining.push(item);
    }
    setStoredQueue(remaining);
  } finally {
    flushing = false;
  }
}

export function trackEvent(event: string, params: Record<string, any> = {}) {
  const payload: TrackPayload = {
    event,
    params: params || {},
    ts: Date.now(),
  };
  if (typeof window !== 'undefined') {
    try {
      // eslint-disable-next-line no-console
      console.debug('[track]', event, params);
    } catch {}
  }
  sendOne(payload).then((ok) => {
    if (!ok) {
      const q = getStoredQueue();
      q.push(payload);
      setStoredQueue(q);
    }
  });
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    flushQueue();
  });
  setTimeout(() => flushQueue(), 3000);
}

/**
 * PRD v1.1 §6 事件常量（EVT-01 ~ EVT-10）
 * 三端（H5 / 小程序 / APP）必须使用相同的 event key。
 */
export const AI_CHAT_EVENTS = {
  /** EVT-01 进入对话页 */
  PAGE_VIEW: 'ai_chat_page_view',
  /** EVT-02 切换咨询对象 */
  TARGET_SWITCH: 'ai_chat_target_switch',
  /** EVT-03 归档原会话 */
  ARCHIVE_HISTORY: 'ai_chat_archive_history',
  /** EVT-04 档案行渲染 */
  PROFILE_ROW_SHOW: 'ai_chat_profile_row_show',
  /** EVT-05 ▽ 展开档案信息卡 */
  PROFILE_CARD_EXPAND: 'ai_chat_profile_card_expand',
  /** EVT-06 收起档案信息卡 */
  PROFILE_CARD_COLLAPSE: 'ai_chat_profile_card_collapse',
  /** EVT-07 点击「↓ 回到最新消息」 */
  SCROLL_TO_BOTTOM_CLICK: 'ai_chat_scroll_to_bottom_click',
  /** EVT-08 健康打卡卡片拖动结束 */
  PUNCHCARD_DRAG: 'ai_chat_punchcard_drag',
  /** EVT-09 冷启动「先完善本人档案」轻提示点击 */
  NO_SELF_PROFILE_TIP_CLICK: 'ai_chat_no_self_profile_tip_click',
  /** EVT-10 发送消息 */
  SEND: 'ai_chat_send',
} as const;

/** 咨询对象类型，统一参数枚举 */
export type AiChatTargetType = 'self' | 'family' | 'none';

/**
 * 统一封装的对话页事件上报接口（语义更清晰，便于后续替换实现）
 */
export const aiChatTrack = {
  pageView(defaultTarget: AiChatTargetType) {
    trackEvent(AI_CHAT_EVENTS.PAGE_VIEW, { default_target: defaultTarget });
  },
  targetSwitch(fromTarget: AiChatTargetType, toTarget: AiChatTargetType, extra: Record<string, any> = {}) {
    trackEvent(AI_CHAT_EVENTS.TARGET_SWITCH, { from_target: fromTarget, to_target: toTarget, ...extra });
  },
  archiveHistory(sessionId: string | number | null, messageCount: number) {
    trackEvent(AI_CHAT_EVENTS.ARCHIVE_HISTORY, { session_id: sessionId, message_count: messageCount });
  },
  profileRowShow(targetName: string) {
    trackEvent(AI_CHAT_EVENTS.PROFILE_ROW_SHOW, { target_name: targetName });
  },
  profileCardExpand(targetName: string) {
    trackEvent(AI_CHAT_EVENTS.PROFILE_CARD_EXPAND, { target_name: targetName });
  },
  profileCardCollapse(trigger: 'icon' | 'outside') {
    trackEvent(AI_CHAT_EVENTS.PROFILE_CARD_COLLAPSE, { trigger });
  },
  scrollToBottomClick(unreadCount: number) {
    trackEvent(AI_CHAT_EVENTS.SCROLL_TO_BOTTOM_CLICK, { unread_count: unreadCount });
  },
  punchcardDrag(fromY: number, toY: number) {
    trackEvent(AI_CHAT_EVENTS.PUNCHCARD_DRAG, { from_y: fromY, to_y: toY });
  },
  noSelfProfileTipClick() {
    trackEvent(AI_CHAT_EVENTS.NO_SELF_PROFILE_TIP_CLICK, {});
  },
  send(targetType: AiChatTargetType, extra: Record<string, any> = {}) {
    trackEvent(AI_CHAT_EVENTS.SEND, { target_type: targetType, ...extra });
  },
};

// ────────────────────────────────────────────────────────────────────────────
// [AICHAT-OPTIM-FIX-V1 F-08 2026-05-14] 宫格 + 胶囊 + 卡片 8 类埋点封装
// 后端 /api/analytics/track 白名单已在上版 PRD 加入：
//   menu_exposure / menu_click / capsule_exposure / capsule_click /
//   card_exposure / card_button_click / form_submit / card_fail
// ────────────────────────────────────────────────────────────────────────────

export const aiHomeFnTrack = {
  /** 宫格区首次进入视窗：menu_ids 数组 */
  menuExposure(menuIds: Array<number | string>) {
    trackEvent('menu_exposure', { menu_ids: menuIds });
  },
  /** 宫格卡片被点击 */
  menuClick(buttonId: number | string, buttonName: string, buttonType: string) {
    trackEvent('menu_click', {
      button_id: buttonId,
      button_name: buttonName,
      button_type: buttonType,
    });
  },
  /** chat 详情页胶囊条首次出现：button_ids 数组 */
  capsuleExposure(buttonIds: Array<number | string>) {
    trackEvent('capsule_exposure', { button_ids: buttonIds });
  },
  /** 胶囊被点击 */
  capsuleClick(buttonId: number | string, buttonName: string, buttonType: string) {
    trackEvent('capsule_click', {
      button_id: buttonId,
      button_name: buttonName,
      button_type: buttonType,
    });
  },
  /** 4 种卡片之一被渲染到对话流 */
  cardExposure(buttonId: number | string, cardType: string) {
    trackEvent('card_exposure', { button_id: buttonId, card_type: cardType });
  },
  /** 卡片主操作按钮被点击 */
  cardButtonClick(buttonId: number | string, cardType: string) {
    trackEvent('card_button_click', { button_id: buttonId, card_type: cardType });
  },
  /** upload 卡片用户提交了图片 */
  formSubmit(buttonId: number | string, success: boolean) {
    trackEvent('form_submit', { button_id: buttonId, success });
  },
  /** 任一卡片渲染失败（异常兜底） */
  cardFail(buttonId: number | string, errorMessage: string) {
    trackEvent('card_fail', { button_id: buttonId, error_message: errorMessage });
  },
};
