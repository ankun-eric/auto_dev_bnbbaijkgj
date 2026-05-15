'use client';

/**
 * [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 自查卡片气泡
 * 用户侧消息气泡，显示部位、症状、持续时间、咨询人
 */

interface Props {
  payload: {
    archiveName?: string;
    archiveAge?: number | null;
    archiveGender?: string | null;
    bodyPart?: { id: number; name: string; icon: string };
    symptoms?: string[];
    duration?: string;
  };
  onReopen?: () => void;
}

export default function HealthSelfCheckCard({ payload, onReopen }: Props) {
  return (
    <div
      style={{
        background: '#e6f4ff',
        border: '1px solid #91caff',
        borderRadius: 12,
        padding: '12px 14px',
        maxWidth: 360,
        position: 'relative',
        fontSize: 13,
        color: '#333',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 6,
        }}
      >
        <div style={{ fontWeight: 600, color: '#1677ff' }}>🩺 健康自查</div>
        {onReopen && (
          <div
            onClick={onReopen}
            style={{
              fontSize: 11,
              color: '#1677ff',
              cursor: 'pointer',
              padding: '2px 6px',
              border: '1px solid #91caff',
              borderRadius: 4,
              background: '#fff',
            }}
          >
            重新自查
          </div>
        )}
      </div>
      {payload.archiveName && (
        <div style={{ marginBottom: 6, color: '#666', fontSize: 12 }}>
          咨询人：{payload.archiveName}
          {payload.archiveAge != null ? `（${payload.archiveAge}岁` : ''}
          {payload.archiveGender ? `·${payload.archiveGender}` : ''}
          {payload.archiveAge != null ? '）' : ''}
        </div>
      )}
      <div
        style={{
          borderTop: '1px dashed #91caff',
          margin: '6px 0',
        }}
      />
      <div style={{ marginBottom: 6 }}>
        <span style={{ color: '#888' }}>部位：</span>
        <span style={{ marginRight: 4 }}>{payload.bodyPart?.icon || '🧩'}</span>
        <span>{payload.bodyPart?.name || '-'}</span>
      </div>
      <div style={{ marginBottom: 6 }}>
        <span style={{ color: '#888' }}>症状：</span>
        {(payload.symptoms || []).map((s) => (
          <span
            key={s}
            style={{
              display: 'inline-block',
              padding: '2px 8px',
              background: '#fff',
              border: '1px solid #91caff',
              borderRadius: 10,
              marginRight: 4,
              marginBottom: 4,
              fontSize: 12,
              color: '#1677ff',
            }}
          >
            {s}
          </span>
        ))}
      </div>
      <div>
        <span style={{ color: '#888' }}>持续：</span>
        <span>{payload.duration}</span>
      </div>
    </div>
  );
}
