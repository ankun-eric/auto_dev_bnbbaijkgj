/**
 * [Bug-419 2026-05-08] H5 端「创建 AI 会话」统一工具方法
 *
 * 背景：PRD-411 Tab 化改造 + PRD-414 v1.1 ai_chat 模块上线后，H5 端
 * `ai-home` 调用 `POST /api/chat/sessions` 时使用了错误字段名 `member_id`
 * （应为 `family_member_id`）且未携带 `session_type`，导致后端 Pydantic
 * 校验 422 必现 + 前端异常未捕获 → 整页白屏。
 *
 * 本工具方法是 H5 端**所有创建 AI 会话调用**的唯一入口，统一负责：
 *   1. 字段名归一化：`member_id` 自动映射为 `family_member_id`
 *   2. `session_type` 缺失兜底为 `health_qa`（与后端 SessionType 枚举对齐）
 *   3. 所有错误内部 try/catch，**仅 Toast 提示，不向上抛**，避免页面级崩溃
 *   4. 对未知 session_type 控制台告警（开发期发现"某入口又写错"）
 *
 * 各入口（症状自查 / 体质分析 / 用药咨询 / 报告解读 / 报告对比 / 侧边栏新建 /
 * 历史会话切换 / 底部 Tab AI / ai-home 主页）必须调用本工具，不允许直接 axios。
 */
'use client';

import { Toast } from 'antd-mobile';
import api from './api';

/**
 * 后端 SessionType 枚举（与 backend/app/models/models.py SessionType 对齐）。
 * 任何不在此集合的 session_type 都会在控制台告警，但仍会发送给后端
 * （后端 _normalize_session_type 会做二次兜底）。
 */
const VALID_SESSION_TYPES = new Set<string>([
  'health_qa',
  'symptom_check',
  'tcm',
  'tcm_tongue',
  'tcm_face',
  'drug_query',
  'customer_service',
  'drug_identify',
  'constitution_test',
  'report_interpret',
  'report_compare',
]);

/**
 * 业务语义别名 → 合法枚举值（与后端 _SESSION_TYPE_ALIASES 保持一致）。
 * 例如：业务方写 'symptom' 时自动映射为 'symptom_check'，避免 422。
 */
const SESSION_TYPE_ALIASES: Record<string, string> = {
  general: 'health_qa',
  qa: 'health_qa',
  chat: 'health_qa',
  default: 'health_qa',
  constitution: 'constitution_test',
  drug: 'drug_query',
  symptom: 'symptom_check',
  report: 'report_interpret',
};

export interface CreateChatSessionPayload {
  /** 会话类型；缺省默认 health_qa */
  session_type?: string;
  /** 会话标题；缺省后端会写 "新对话" */
  title?: string;
  /** 咨询对象 family_member_id（标准字段名） */
  family_member_id?: number | null;
  /**
   * H5 早期实现误写的字段名，工具方法会自动归并到 family_member_id；
   * 新代码请使用 family_member_id，不要再写 member_id。
   */
  member_id?: number | null;
  /** 症状自查场景的结构化症状信息 */
  symptom_info?: Record<string, unknown>;
}

export interface CreateChatSessionResult {
  ok: boolean;
  /** 创建成功的 session id（字符串），失败时为 null */
  sessionId: string | null;
  /** 可读错误消息（失败时填充） */
  errorMessage?: string;
  /** 原始后端响应（成功时） */
  raw?: any;
}

/**
 * 把任意字符串归一化为合法的 session_type 值。
 * 优先级：直接命中枚举 > 别名表 > 兜底 health_qa。
 */
function normalizeSessionType(raw: string | undefined): string {
  if (!raw) return 'health_qa';
  if (VALID_SESSION_TYPES.has(raw)) return raw;
  const aliased = SESSION_TYPE_ALIASES[raw];
  if (aliased && VALID_SESSION_TYPES.has(aliased)) return aliased;
  if (typeof console !== 'undefined') {
    // eslint-disable-next-line no-console
    console.warn(
      `[createChatSession] 未知 session_type=${raw}，已兜底为 health_qa（后端会再做二次兜底）`,
    );
  }
  return 'health_qa';
}

/**
 * 创建 AI 会话。
 *
 * 内部已 try/catch；调用方按返回值的 `ok` 判断成功与否，**不要再 try/catch**。
 * 失败时已经通过 Toast 提示用户，**不会向上抛异常**——这是修复 H5 ai-home
 * "整片白屏" 的关键护栏（任意子组件抛错都不能让首页 unmount）。
 */
export async function createChatSession(
  payload: CreateChatSessionPayload = {},
  options: {
    /** 失败时是否主动 Toast，默认 true */
    showErrorToast?: boolean;
    /** 自定义失败文案，默认"创建会话失败，请重试" */
    errorToastText?: string;
  } = {},
): Promise<CreateChatSessionResult> {
  const showErrorToast = options.showErrorToast !== false;
  const errorToastText = options.errorToastText || '创建会话失败，请重试';

  // 1) 字段归一化
  const session_type = normalizeSessionType(payload.session_type);
  const family_member_id =
    payload.family_member_id !== undefined && payload.family_member_id !== null
      ? payload.family_member_id
      : payload.member_id !== undefined && payload.member_id !== null
        ? payload.member_id
        : null;

  // 2) 构造请求体（仅传非空字段，后端兜底逻辑生效）
  const body: Record<string, unknown> = { session_type };
  if (payload.title) body.title = payload.title;
  if (family_member_id !== null && family_member_id !== undefined) {
    body.family_member_id = family_member_id;
  }
  if (payload.symptom_info && typeof payload.symptom_info === 'object') {
    body.symptom_info = payload.symptom_info;
  }

  // 3) 发起请求 + 全错误兜底
  try {
    const res: any = await api.post('/api/chat/sessions', body);
    const data = res?.data || res;
    const id = data?.id ?? data?.session_id;
    if (id == null) {
      throw new Error('后端未返回 session id');
    }
    return { ok: true, sessionId: String(id), raw: data };
  } catch (err: any) {
    // [Bug-419 H-6] 仅 Toast，不向上抛 → 调用方页面布局保持完整
    let detail = '';
    try {
      const respData = err?.response?.data;
      if (respData) {
        if (typeof respData === 'string') detail = respData;
        else if (typeof respData.detail === 'string') detail = respData.detail;
        else if (Array.isArray(respData.messages) && respData.messages.length > 0) {
          detail = respData.messages.join('；');
        }
      }
    } catch {}
    if (showErrorToast) {
      try {
        Toast.show({ icon: 'fail', content: detail || errorToastText, duration: 2500 });
      } catch {
        // Toast 自身异常也吞掉，避免再次冒泡
      }
    }
    if (typeof console !== 'undefined') {
      // eslint-disable-next-line no-console
      console.error('[createChatSession] 创建会话失败:', err, 'detail=', detail);
    }
    return {
      ok: false,
      sessionId: null,
      errorMessage: detail || errorToastText,
    };
  }
}

export default createChatSession;
