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
  /** 封面图（可选） */
  coverImage?: string;
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
   *  - upload  ：sub_action ∈ {album, camera, local, wechat}
   *  - navigate / sdk_call / quick_ask ：sub_action = 'primary'
   */
  onAction?: (subAction: string) => void;
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

function CardHeader({ button }: { button: ChatCardButton }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
      {button.coverImage ? (
        <img
          src={button.coverImage}
          alt={button.title}
          style={{ width: 40, height: 40, borderRadius: 10, objectFit: 'cover' }}
        />
      ) : (
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 10,
            background: COLORS.primary,
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 20,
          }}
        >
          ✨
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
  const entries: Array<{ key: 'album' | 'camera' | 'local' | 'wechat'; label: string; icon: string }> = [
    { key: 'album', label: '相册', icon: '🖼️' },
    { key: 'camera', label: '拍照', icon: '📷' },
    { key: 'local', label: '本机', icon: '📁' },
    { key: 'wechat', label: '微信', icon: '💬' },
  ];
  return (
    <CardShell disabled={disabled}>
      <CardHeader button={button} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
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

export function QuickAskCard({ button, disabled, onAction }: ChatCardProps) {
  return (
    <CardShell disabled={disabled}>
      <CardHeader button={button} />
      <PrimaryButton
        text={button.title || '立即提问'}
        subDesc={button.buttonSubDesc}
        disabled={disabled}
        onClick={() => onAction?.('primary')}
      />
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
 */
export function resolveCardType(buttonType: string): ChatCardType {
  switch (buttonType) {
    case 'file_upload':
    case 'photo_upload':
    case 'photo_recognize_drug':
      return 'upload';
    case 'ai_chat_trigger':
    case 'external_link':
      return 'navigate';
    case 'digital_human_call':
      return 'sdk_call';
    case 'quick_ask':
      return 'quick_ask';
    default:
      return 'navigate';
  }
}

export default ChatCard;
