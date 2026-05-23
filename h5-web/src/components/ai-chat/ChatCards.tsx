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
// [PRD-AICHAT-FUNCCARD-V2 2026-05-20] 引入统一新版功能卡片渲染器
import FunctionCardV2, { type FunctionCardV2Data } from './FunctionCardV2';

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
  // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 新字段透传：AI 开场白 / 子类型 / 跳转先弹卡片开关
  /** AI 开场白：可留空。非空时，点击按钮后 AI 先冒一句话再弹卡片 */
  aiOpening?: string;
  /** AI 功能子类型（仅 button_type=ai_function 时生效） */
  aiFunctionType?: string;
  /** 页面跳转：是否先弹卡片再跳转（仅 button_type=page_navigate 时生效） */
  preCardForNavigate?: boolean;
  /** 拍照/上传用途（如 interpret_report / identify_medicine / upload） */
  capturePurpose?: string;
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

// [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 卡片视觉规范（方案 A · 极简扁平 · 天空蓝）
// 与 ai-home 主页同色系 #0EA5E9（替代旧靛紫色 #6366F1），实现视觉统一。
const COLORS = {
  bg: '#FFFFFF',                                  // 卡片背景：纯白
  border: '#BAE6FD',                              // 1px 浅蓝描边
  primary: '#0EA5E9',                             // 主色：天空蓝
  primaryDark: '#0284C7',                         // hover/press
  textPrimary: '#0F172A',                         // 标题字色
  textSecondary: '#475569',                       // 说明字色
  disabled: '#D1D5DB',
  // [PRD §3.5.1] 卡片阴影 + Emoji 头像底色
  shadow: '0 2px 8px rgba(14, 165, 233, 0.08)',
  emojiAvatarBg: 'rgba(14, 165, 233, 0.10)',
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
        boxShadow: disabled ? 'none' : COLORS.shadow,
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
            // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 主题色 10% 透明度（天空蓝）
            background: COLORS.emojiAvatarBg,
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

// [PRD-AICHAT-FUNCCARD-V2 2026-05-20] 把 ChatCardButton 适配到 FunctionCardV2Data
// [PRD-AICHAT-FUNCCARD-V2-DESIGN-D 2026-05-20 v1.2] 按方案 D 决策 12：
//   - 主按钮文案前端硬编码「开始」，组件内部忽略 buttonText
//   - 此处 buttonText 字段保留供旧逻辑/类型兼容（不会被渲染）
function buttonToFcv2Data(button: ChatCardButton, override?: Partial<FunctionCardV2Data>): FunctionCardV2Data {
  const emoji = (button.iconEmoji || '').trim();
  const iconType: FunctionCardV2Data['iconType'] = emoji
    ? 'emoji'
    : isValidImageUrl(button.coverImage)
    ? 'url'
    : 'default';
  return {
    title: button.title || '',
    subtitle: button.subtitle || null,
    coverImage: isValidImageUrl(button.coverImage) ? (button.coverImage as string) : null,
    icon: emoji || (isValidImageUrl(button.coverImage) ? (button.coverImage as string) : null),
    iconType,
    buttonSubDesc: button.buttonSubDesc || null,
    // v1.2 方案 D：按钮固定显示「开始」，此处 buttonText 仅用于旧逻辑兼容，组件内部忽略
    buttonText: '开始',
    ...override,
  };
}

// ─────────────────── A. upload 卡片（新版样式） ───────────────────

export function UploadCard({ button, disabled, onAction }: ChatCardProps) {
  const entries: Array<{ key: string; label: string; icon: string }> = [
    { key: 'album', label: '相册', icon: '🖼️' },
    { key: 'camera', label: '拍照', icon: '📷' },
  ];
  if (button.capturePurpose === 'interpret_report') {
    entries.push({ key: 'history', label: '历史报告', icon: '📋' });
  }
  const gridCols = entries.length >= 3 ? 'repeat(3, 1fr)' : 'repeat(2, 1fr)';
  const data = buttonToFcv2Data(button, {
    buttonText: '开始',
    disabled,
  });
  return (
    <FunctionCardV2
      data={data}
      hideButton
      testid="function-card-v2-upload"
    >
      <div style={{ display: 'grid', gridTemplateColumns: gridCols, gap: 10 }}>
        {entries.map((e) => (
          <button
            key={e.key}
            type="button"
            data-fcv2-stop="1"
            onClick={(ev) => {
              ev.stopPropagation();
              onAction?.(e.key);
            }}
            disabled={disabled}
            style={{
              padding: '12px 4px',
              borderRadius: 14,
              border: '1px solid #E0F2FE',
              background: '#F0F9FF',
              color: '#0F172A',
              cursor: disabled ? 'not-allowed' : 'pointer',
              fontSize: 13,
              fontWeight: 500,
              transition: 'background .15s',
            }}
            data-testid={`upload-entry-${e.key}`}
          >
            <div style={{ fontSize: 24, lineHeight: 1 }}>{e.icon}</div>
            <div style={{ marginTop: 6 }}>{e.label}</div>
          </button>
        ))}
      </div>
      {button.buttonSubDesc ? (
        <div
          data-testid="fcv2-upload-btn-sub-desc"
          style={{
            fontSize: 12,
            lineHeight: '18px',
            color: '#94A3B8',
            textAlign: 'center',
            marginTop: 12,
          }}
        >
          {button.buttonSubDesc}
        </div>
      ) : null}
    </FunctionCardV2>
  );
}

// ─────────────────── B. navigate 卡片（新版样式） ───────────────────

export function NavigateCard({ button, disabled, onAction }: ChatCardProps) {
  const data = buttonToFcv2Data(button, {
    buttonText: '开始',
    disabled,
  });
  return (
    <FunctionCardV2
      data={data}
      onClick={() => onAction?.('primary')}
      testid="function-card-v2-navigate"
    />
  );
}

// ─────────────────── C. sdk_call 卡片（新版样式） ───────────────────

export function SdkCallCard({ button, disabled, onAction }: ChatCardProps) {
  const data = buttonToFcv2Data(button, {
    buttonText: '开始',
    buttonSubDesc: button.buttonSubDesc || 'AI 数字人，24 小时在线',
    disabled,
  });
  return (
    <FunctionCardV2
      data={data}
      onClick={() => onAction?.('primary')}
      testid="function-card-v2-sdk-call"
    />
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

  // [PRD-AICHAT-FUNCCARD-V2 2026-05-20] quick_ask 仍保留旧 CardShell + 自定义 footer，
  // 但用 FunctionCardV2 同款标题/描述视觉规范覆盖头部色值，以保持品牌一致。
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
export function resolveCardType(buttonType: string, aiFunctionType?: string | null): ChatCardType {
  // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 新两大类映射：
  //   - page_navigate            -> navigate 卡片
  //   - ai_function + 子类型      -> 按子类型派发（同老映射）
  if (buttonType === 'page_navigate') return 'navigate';
  if (buttonType === 'ai_function') {
    switch (aiFunctionType || '') {
      case 'photo_upload':
      case 'file_upload':
      case 'medicine_recognize':
      case 'report_interpret':
      case 'image_capture':
        return 'upload';
      case 'quick_ask':
        return 'quick_ask';
      case 'ai_dialog_trigger':
      case 'health_self_check':
      default:
        return 'navigate';
    }
  }
  // ─── 老枚举 ───
  switch (buttonType) {
    case 'file_upload':
    case 'photo_upload':
    case 'photo_recognize_drug':
    case 'medication_recognize':
    case 'drug_identify':
    case 'report_interpret':
      return 'upload';
    case 'external_link':
      return 'navigate';
    case 'ai_chat_trigger':
    case 'ai_dialog_trigger':
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
  // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 新字段
  ai_function_type?: string | null;
  ai_opening?: string | null;
  pre_card_for_navigate?: boolean | null;
  capture_purpose?: string | null;
  grid_sort?: number | null;
  capsule_sort?: number | null;
}

export function backendButtonToCardButton(b: BackendFunctionButton): ChatCardButton {
  return {
    key: String(b.id),
    buttonType: b.button_type,
    title: b.card_title || b.name || '',
    subtitle: b.card_subtitle || undefined,
    coverImage: b.card_cover_image || undefined,
    iconEmoji: (b as any).icon || undefined,
    buttonSubDesc: b.button_sub_desc || undefined,
    promptTemplateId: b.prompt_template_id || undefined,
    externalUrl: b.external_url || undefined,
    presetPrompt: b.preset_prompt || undefined,
    autoUserMessage: b.auto_user_message || undefined,
    // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 新字段透传
    aiOpening: (b.ai_opening || '').trim() || undefined,
    aiFunctionType: b.ai_function_type || undefined,
    preCardForNavigate: !!b.pre_card_for_navigate,
    capturePurpose: b.capture_purpose || undefined,
  };
}

export default ChatCard;
