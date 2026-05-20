/**
 * [PRD-TCM-DRAWER-V12 2026-05-20] 通用问卷"对话内说明卡片"组件
 *
 * 用法：当按钮的 questionnaire_display_form=INLINE_CHAT 且 pre_card_enabled=true 时，
 * 在对话流中以 AI 气泡形式渲染本卡片。
 *
 * 渲染要素：封面图（可选）+ 主标题 + 副标题 + 说明 + 底部主按钮「开始测评」
 */
import React from 'react';

export interface QuestionnairePreCardData {
  buttonId: number;
  templateId?: number | null;
  templateCode?: string | null;
  title: string;
  subtitle?: string | null;
  coverImage?: string | null;
  description?: string | null;
  buttonText?: string;
  icon?: string | null;
  iconType?: 'url' | 'emoji' | 'default' | string | null;
}

interface QuestionnairePreCardProps {
  data: QuestionnairePreCardData;
  onStart: (data: QuestionnairePreCardData) => void;
}

export default function QuestionnairePreCard({ data, onStart }: QuestionnairePreCardProps) {
  const iconType = data.iconType || 'default';
  const iconRender = () => {
    if (data.coverImage) {
      // 封面图优先
      return (
        <div
          style={{
            width: '100%',
            height: 120,
            backgroundImage: `url(${data.coverImage})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            borderTopLeftRadius: 12,
            borderTopRightRadius: 12,
          }}
        />
      );
    }
    if (data.icon && iconType === 'url') {
      return (
        <div style={{ padding: 12, textAlign: 'center' }}>
          <img src={data.icon} alt="" style={{ width: 48, height: 48, borderRadius: 8 }} />
        </div>
      );
    }
    const emoji = (iconType === 'emoji' && data.icon) ? data.icon : '🌿';
    return (
      <div style={{
        width: 56, height: 56, fontSize: 36, lineHeight: '56px',
        textAlign: 'center', margin: '12px auto 0', borderRadius: 12,
        background: 'linear-gradient(135deg, #ECFEFF 0%, #CFFAFE 100%)',
      }}>
        {emoji}
      </div>
    );
  };

  return (
    <div
      data-testid="questionnaire-pre-card"
      style={{
        background: '#FFFFFF',
        borderRadius: 12,
        boxShadow: '0 2px 12px rgba(2, 132, 199, 0.10)',
        overflow: 'hidden',
        maxWidth: 320,
        margin: '4px 0',
        border: '1px solid #E0F2FE',
      }}
    >
      {iconRender()}
      <div style={{ padding: '12px 16px 6px' }}>
        <div
          data-testid="questionnaire-pre-card-title"
          style={{ fontSize: 16, fontWeight: 600, color: '#0F172A', lineHeight: '22px' }}
        >
          {data.title || '健康测评'}
        </div>
        {data.subtitle ? (
          <div
            data-testid="questionnaire-pre-card-subtitle"
            style={{ fontSize: 12, color: '#64748B', marginTop: 4, lineHeight: '18px' }}
          >
            {data.subtitle}
          </div>
        ) : null}
        {data.description ? (
          <div
            data-testid="questionnaire-pre-card-desc"
            style={{
              fontSize: 13, color: '#475569', marginTop: 8, lineHeight: '20px',
              background: '#F8FAFC', padding: '8px 10px', borderRadius: 8,
            }}
          >
            {data.description}
          </div>
        ) : null}
      </div>
      <div style={{ padding: '6px 16px 14px' }}>
        <button
          data-testid="questionnaire-pre-card-start-btn"
          type="button"
          onClick={() => onStart(data)}
          style={{
            display: 'block',
            width: '100%',
            height: 40,
            border: 'none',
            borderRadius: 20,
            color: '#FFFFFF',
            fontSize: 15,
            fontWeight: 600,
            cursor: 'pointer',
            background: 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)',
            boxShadow: '0 2px 8px rgba(2,132,199,0.25)',
          }}
        >
          {data.buttonText || '开始测评'}
        </button>
      </div>
    </div>
  );
}
