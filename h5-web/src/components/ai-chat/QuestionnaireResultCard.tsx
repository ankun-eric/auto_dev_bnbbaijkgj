'use client';

/**
 * [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 问卷结果卡片
 *
 * 在对话流中渲染"图文摘要卡"，展示问卷提交后的关键字段，
 * 右上角支持「重新填写」按钮。
 */

interface QnResultField {
  key: string;
  label: string;
  value: string;
}

export interface QnResultCardPayload {
  template_code?: string;
  template_name?: string;
  summary_text?: string | null;
  fields: QnResultField[];
  icon?: string;
}

interface Props {
  payload: QnResultCardPayload;
  aiStatusText?: string | null;
  onRetry?: () => void;
}

const FIELD_ICON_MAP: Record<string, string> = {
  部位: '🧍',
  症状: '💢',
  持续时间: '⏱',
  持续: '⏱',
  维度: '📊',
};

export default function QuestionnaireResultCard({
  payload,
  aiStatusText,
  onRetry,
}: Props) {
  return (
    <div
      data-testid="qn-result-card"
      style={{
        background: 'linear-gradient(180deg, #FFFFFF 0%, #F7FCFB 100%)',
        border: '1px solid #E5F4F1',
        borderRadius: 12,
        padding: 0,
        maxWidth: 320,
        overflow: 'hidden',
        boxShadow: '0 1px 4px rgba(43,182,168,0.08)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 12px',
          borderBottom: '1px dashed #E5F4F1',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 18 }}>{payload.icon || '🩺'}</span>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#1F8E81' }}>
            {payload.template_name || '问卷结果'}
          </span>
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            data-testid="qn-result-retry-btn"
            style={{
              border: '1px solid #2BB6A8',
              background: '#fff',
              color: '#2BB6A8',
              borderRadius: 14,
              padding: '3px 10px',
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            📝 重新填写
          </button>
        )}
      </div>
      <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {payload.fields.map((f) => (
          <div
            key={f.key}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
            }}
          >
            <div
              style={{
                width: 52,
                flex: '0 0 52px',
                background: '#E6FAF7',
                color: '#1F8E81',
                borderRadius: 8,
                fontSize: 12,
                fontWeight: 600,
                textAlign: 'center',
                padding: '6px 2px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 2,
              }}
            >
              <span style={{ fontSize: 14 }}>{FIELD_ICON_MAP[f.label] || '•'}</span>
              <span>{f.label}</span>
            </div>
            <div
              style={{
                flex: 1,
                fontSize: 13,
                color: '#333',
                paddingTop: 4,
                lineHeight: 1.5,
                wordBreak: 'break-all',
              }}
            >
              {f.value || <span style={{ color: '#bbb' }}>—</span>}
            </div>
          </div>
        ))}
        {payload.summary_text && (
          <div
            style={{
              marginTop: 4,
              padding: '6px 8px',
              background: '#F2F4F7',
              borderRadius: 6,
              fontSize: 12,
              color: '#666',
              fontStyle: 'italic',
            }}
          >
            {payload.summary_text}
          </div>
        )}
      </div>
      {aiStatusText && (
        <div
          style={{
            padding: '8px 12px',
            borderTop: '1px dashed #E5F4F1',
            background: '#F7FCFB',
            color: '#1F8E81',
            fontSize: 12,
          }}
        >
          {aiStatusText}
        </div>
      )}
    </div>
  );
}
