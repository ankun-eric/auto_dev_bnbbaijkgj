/**
 * [AI对话模式优化 PRD v1.0 §5] AI 对话模式 4 种卡片组件统一导出。
 *
 * 4 种卡片类型：
 *  - upload     ：文件上传卡片（适用 file_upload / photo_upload / photo_recognize_drug）
 *  - navigate   ：业务跳转卡片（适用 ai_chat_trigger / external_link）
 *  - sdk_call   ：SDK 调用卡片（适用 digital_human_call）
 *  - quick_ask  ：快捷提问卡片（适用 quick_ask）
 *
 * 视觉基调：蓝紫渐变（与 AI 对话模式视觉语言对齐）。
 * 各卡片支持 disabled 态（重复点击时旧卡片置灰）。
 *
 * 注意：本组件本期为 MVP 占位实现，确保 PRD 4 种卡片在对话流可被渲染、
 *       后端配置驱动，具体业务交互可在 v1.1 持续打磨。
 */
'use client';

import React from 'react';

export type ChatCardType = 'upload' | 'navigate' | 'sdk_call' | 'quick_ask';

export interface ChatCardButton {
  /** 卡片唯一 key（取自 chat_function_buttons.id 或 name） */
  key: string;
  /** 按钮类型枚举（PRD §3.2 7 种） */
  buttonType: string;
  /** 卡片标题 */
  title: string;
  /** 卡片副标题 */
  subtitle?: string;
  /** 封面图（可选，已废弃；新版统一用 Emoji 渲染头像） */
  coverImage?: string;
  /** [PRD-AICHAT-CAPSULE-V2 2026-05-15] Emoji 头像（取代 coverImage 成为主头像渲染源） */
  iconEmoji?: string;
  /** 主按钮副说明文字 */
  buttonSubDesc?: string;
  /** 关联 prompt 模板 ID（仅部分类型用） */
  promptTemplateId?: number;
  /** 外部链接（仅 external_link 用） */
  externalUrl?: string;
  /** 预设话术（仅 quick_ask 用） */
  presetPrompt?: string;
  /** 自动用户消息（点击后插入对话流的用户气泡文案） */
  autoUserMessage?: string;
}

export interface ChatCardProps {
  cardType: ChatCardType;
  button: ChatCardButton;
  /** 卡片是否禁用（重复点击折叠后置灰） */
  disabled?: boolean;
  /**
   * 用户与卡片交互回调：
   *  - upload  ：sub_action ∈ {album, camera}（[PRD-AICHAT-CAPSULE-V2 2026-05-15] 收口为 2 项；
   *               local/wechat 已废弃，存量数据自动忽略）
   *  - navigate / sdk_call ：sub_action = 'primary'
   *  - quick_ask ：sub_action ∈ {send, cancel}，payload 为用户编辑后的文本（通过 onQuickAskSend 回调透传）
   */
  onAction?: (subAction: string, payload?: any) => void;
}

const COLORS = {
  bg: 'linear-gradient(135deg, #EEF2FF 0%, #F5F3FF 100%)',
  border: '#E0E7FF',
  primary: '#6366F1',
  primaryDark: '#4F46E5',
  textPrimary: '#1F2937',
  textSecondary: '#6B7280',
  disabled: '#D1D5DB',
};

function CardShell({
  children,
  disabled,
}: {
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <div
      style={{
        background: disabled ? '#F3F4F6' : COLORS.bg,
        border: `1px solid ${disabled ? COLORS.disabled : COLORS.border}`,
        borderRadius: 16,
        padding: 16,
        margin: '8px 0',
        opacity: disabled ? 0.6 : 1,
        pointerEvents: disabled ? 'none' : 'auto',
      }}
      data-testid="ai-chat-card"
      data-disabled={disabled ? 'true' : 'false'}
    >
      {children}
    </div>
  );
}

/**
 * [Bug-470 2026-05-15] 判断一个字符串是否是合法的图片 URL，避免脏数据
 *   - 字面值 "无"
 *   - 单个 emoji（如 "💊"）
 *   - 空白字符串
 * 等被误用作 <img src> 时，浏览器会把它当作相对路径解析（如 /ai-home/无），
 * 触发 404 + 页面初始化卡死，进而导致 4 个上传按钮看起来"全部失灵"。
 */
function isValidImageUrl(s: any): boolean {
  if (typeof s !== 'string') return false;
  const t = s.trim();
  if (!t) return false;
  // 合法的 URL/路径形态
  if (t.startsWith('http://') || t.startsWith('https://')) return true;
  if (t.startsWith('/') || t.startsWith('./') || t.startsWith('data:image/') || t.startsWith('blob:')) return true;
  return false;
}

/**
 * [PRD-AICHAT-CAPSULE-V2 2026-05-15 需求 2] 头像统一渲染为「圆角方块底色 + 大号 Emoji」。
 * 规格：40x40，圆角 8px，背景 = 主题色 10% 透明度。
 * 兼容旧数据：当 iconEmoji 为空时，回退到 coverImage（仅 URL 合法时才作为 <img>），都没有则用 ✨。
 */
function CardHeader({ button }: { button: ChatCardButton }) {
  const emoji = (button.iconEmoji || '').trim();
  const hasEmoji = !!emoji;
  const hasValidImage = !hasEmoji && isValidImageUrl(button.coverImage);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
      {hasValidImage ? (
        <img
          src={button.coverImage}
          alt={button.title}
          style={{ width: 40, height: 40, borderRadius: 8, objectFit: 'cover' }}
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = 'none';
          }}
        />
      ) : (
        <div
          data-testid="card-header-emoji-avatar"
          style={{
            width: 40,
            height: 40,
            borderRadius: 8,
            // 主题色 10% 透明度（#6366F1 → rgba(99,102,241,0.10)）
            background: 'rgba(99, 102, 241, 0.10)',
            color: COLORS.primaryDark,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 22,
          }}
        >
          {hasEmoji ? emoji : '✨'}
        </div>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 16, fontWeight: 600, color: COLORS.textPrimary }}>
          {button.title}
        </div>
        {button.subtitle ? (
          <div style={{ fontSize: 12, color: COLORS.textSecondary, marginTop: 2 }}>
            {button.subtitle}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function PrimaryButton({
  text,
  subDesc,
  disabled,
  onClick,
}: {
  text: string;
  subDesc?: string;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <div>
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        style={{
          width: '100%',
          padding: '12px 16px',
          borderRadius: 12,
          border: 'none',
          background: disabled ? COLORS.disabled : COLORS.primary,
          color: '#fff',
          fontSize: 15,
          fontWeight: 600,
          cursor: disabled ? 'not-allowed' : 'pointer',
        }}
      >
        {text}
      </button>
      {subDesc ? (
        <div
          style={{
            fontSize: 12,
            color: COLORS.textSecondary,
            marginTop: 8,
            textAlign: 'center',
          }}
        >
          {subDesc}
        </div>
      ) : null}
    </div>
  );
}

// ─────────────────── A. upload 卡片 ───────────────────

export function UploadCard({ button, disabled, onAction }: ChatCardProps) {
  // [PRD-AICHAT-CAPSULE-V2 2026-05-15 需求 1] 入口收口为 2 项：相册 + 拍照
  // local（本机）和 wechat（微信）在 H5 形同摆设，全端一致移除
  const entries: Array<{ key: 'album' | 'camera'; label: string; icon: string }> = [
    { key: 'album', label: '相册', icon: '🖼️' },
    { key: 'camera', label: '拍照', icon: '📷' },
  ];
  return (
    <CardShell disabled={disabled}>
      <CardHeader button={button} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
        {entries.map((e) => (
          <button
            key={e.key}
            type="button"
            onClick={() => onAction?.(e.key)}
            disabled={disabled}
            style={{
              padding: '10px 4px',
              borderRadius: 12,
              border: `1px solid ${COLORS.border}`,
              background: '#fff',
              color: COLORS.textPrimary,
              cursor: disabled ? 'not-allowed' : 'pointer',
              fontSize: 12,
            }}
            data-testid={`upload-entry-${e.key}`}
          >
            <div style={{ fontSize: 22 }}>{e.icon}</div>
            <div style={{ marginTop: 4 }}>{e.label}</div>
          </button>
        ))}
      </div>
      {button.buttonSubDesc ? (
        <div
          style={{
            fontSize: 12,
            color: COLORS.textSecondary,
            marginTop: 12,
            textAlign: 'center',
          }}
        >
          {button.buttonSubDesc}
        </div>
      ) : null}
    </CardShell>
  );
}

// ─────────────────── B. navigate 卡片 ───────────────────

export function NavigateCard({ button, disabled, onAction }: ChatCardProps) {
  return (
    <CardShell disabled={disabled}>
      <CardHeader button={button} />
      <PrimaryButton
        text={button.title || '前往'}
        subDesc={button.buttonSubDesc}
        disabled={disabled}
        onClick={() => onAction?.('primary')}
      />
    </CardShell>
  );
}

// ─────────────────── C. sdk_call 卡片 ───────────────────

export function SdkCallCard({ button, disabled, onAction }: ChatCardProps) {
  return (
    <CardShell disabled={disabled}>
      <CardHeader button={button} />
      <PrimaryButton
        text="发起视频通话"
        subDesc={button.buttonSubDesc || 'AI 数字人，24 小时在线'}
        disabled={disabled}
        onClick={() => onAction?.('primary')}
      />
    </CardShell>
  );
}

// ─────────────────── D. quick_ask 卡片 ───────────────────
// [PRD-AICHAT-CAPSULE-V2 2026-05-15 需求 4.2] 可编辑版快捷提问卡片
// - 文本框多行可编辑，预填 presetPrompt（兜底 autoUserMessage / title），最长 500 字
// - 点击「发送」：把当前文本以「用户身份」发出，卡片自身置灰（disabled=true 由父组件控制）
// - 点击「取消」：交由父组件决定保留为灰色态或从对话区移除

export function QuickAskCard({ button, disabled, onAction }: ChatCardProps) {
  const defaultText =
    (button.presetPrompt || button.autoUserMessage || button.title || '').trim();
  const [text, setText] = React.useState<string>(defaultText);

  // PRD §4.2 文本框最大长度 500（与对话输入框一致）
  const MAX = 500;
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const v = e.target.value.slice(0, MAX);
    setText(v);
  };

  const sendDisabled = disabled || !text.trim();

  return (
    <CardShell disabled={disabled}>
      <CardHeader button={button} />
      <textarea
        data-testid="quick-ask-textarea"
        value={text}
        onChange={handleChange}
        disabled={disabled}
        rows={3}
        maxLength={MAX}
        placeholder="编辑你的问题…"
        style={{
          width: '100%',
          minHeight: 64,
          resize: 'vertical',
          padding: '10px 12px',
          fontSize: 14,
          lineHeight: 1.5,
          color: COLORS.textPrimary,
          background: disabled ? '#F3F4F6' : '#fff',
          border: `1px solid ${COLORS.border}`,
          borderRadius: 10,
          outline: 'none',
          boxSizing: 'border-box',
        }}
      />
      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: 8,
          marginTop: 10,
        }}
      >
        <button
          type="button"
          data-testid="quick-ask-cancel-btn"
          disabled={disabled}
          onClick={() => onAction?.('cancel')}
          style={{
            padding: '6px 16px',
            borderRadius: 999,
            border: `1px solid ${COLORS.border}`,
            background: '#fff',
            color: COLORS.textSecondary,
            fontSize: 13,
            cursor: disabled ? 'not-allowed' : 'pointer',
          }}
        >
          取消
        </button>
        <button
          type="button"
          data-testid="quick-ask-send-btn"
          disabled={sendDisabled}
          onClick={() => onAction?.('send', text.trim())}
          style={{
            padding: '6px 18px',
            borderRadius: 999,
            border: 'none',
            background: sendDisabled ? COLORS.disabled : COLORS.primary,
            color: '#fff',
            fontSize: 13,
            fontWeight: 500,
            cursor: sendDisabled ? 'not-allowed' : 'pointer',
          }}
        >
          发送
        </button>
      </div>
      {button.buttonSubDesc ? (
        <div
          style={{
            fontSize: 12,
            color: COLORS.textSecondary,
            marginTop: 6,
          }}
        >
          {button.buttonSubDesc}
        </div>
      ) : null}
    </CardShell>
  );
}

// ─────────────────── 统一调度器 ───────────────────

export function ChatCard(props: ChatCardProps) {
  switch (props.cardType) {
    case 'upload':
      return <UploadCard {...props} />;
    case 'navigate':
      return <NavigateCard {...props} />;
    case 'sdk_call':
      return <SdkCallCard {...props} />;
    case 'quick_ask':
      return <QuickAskCard {...props} />;
    default:
      return null;
  }
}

/**
 * 根据按钮类型推导卡片类型（PRD §4 9 项功能与按钮类型最终映射）。
 *
 * [AICHAT-OPTIM-FIX-V1 F-06 2026-05-14] 修订映射规则，兼容旧值：
 *   - medication_recognize / drug_identify / photo_upload / photo_recognize_drug / file_upload → upload
 *   - external_link → navigate
 *   - video_consult / live_chat / digital_human_call → sdk_call
 *   - quick_ask / prompt_template → quick_ask
 *   - ai_chat_trigger / ai_dialog_trigger → navigate（带卡片样式跳转）
 */
export function resolveCardType(buttonType: string): ChatCardType {
  switch (buttonType) {
    case 'file_upload':
    case 'photo_upload':
    case 'photo_recognize_drug':
    case 'medication_recognize':
    case 'drug_identify':
    // [PRD-PROMPT-CONFIG-V1 2026-05-14] 报告解读复用 upload 卡片（拍照/选相册/选文件三选一）
    case 'report_interpret':
      return 'upload';
    case 'external_link':
      return 'navigate';
    case 'ai_chat_trigger':
    case 'ai_dialog_trigger':
      // PRD: ai_dialog_trigger 旧值兜底，作为带卡片的 navigate 渲染
      return 'navigate';
    case 'digital_human_call':
    case 'video_consult':
    case 'live_chat':
      return 'sdk_call';
    case 'quick_ask':
    case 'prompt_template':
      return 'quick_ask';
    default:
      return 'navigate';
  }
}

/**
 * [AICHAT-OPTIM-FIX-V1 F-07] 后端 FunctionButton 接口数据 → ChatCardButton 适配器
 * 从 chat_function_buttons 表的 8 字段及通用字段填充卡片渲染所需 props。
 */
export interface BackendFunctionButton {
  id: number | string;
  name: string;
  /** [PRD-AICHAT-CAPSULE-V2 2026-05-15] Emoji 主图标字段（chat_function_buttons.icon） */
  icon?: string;
  /** @deprecated 旧字段，已不再使用，仅作向后兼容 */
  icon_url?: string;
  button_type: string;
  prompt_template_id?: number | null;
  external_url?: string | null;
  preset_prompt?: string | null;
  auto_user_message?: string | null;
  card_title?: string | null;
  card_subtitle?: string | null;
  card_cover_image?: string | null;
  button_sub_desc?: string | null;
}

export function backendButtonToCardButton(b: BackendFunctionButton): ChatCardButton {
  return {
    key: String(b.id),
    buttonType: b.button_type,
    title: b.card_title || b.name || '',
    subtitle: b.card_subtitle || undefined,
    // [PRD-AICHAT-CAPSULE-V2 2026-05-15 需求 2] 卡片头像不再使用 cover_url；
    // 统一改用 Emoji（chat_function_buttons.icon）。coverImage 仅作为旧数据回退渲染（CardHeader 内部判断）。
    coverImage: b.card_cover_image || undefined,
    iconEmoji: (b as any).icon || undefined,
    buttonSubDesc: b.button_sub_desc || undefined,
    promptTemplateId: b.prompt_template_id || undefined,
    externalUrl: b.external_url || undefined,
    presetPrompt: b.preset_prompt || undefined,
    autoUserMessage: b.auto_user_message || undefined,
  };
}

export default ChatCard;
