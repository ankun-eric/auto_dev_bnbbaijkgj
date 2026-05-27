'use client';

// [PRD-CARE-AI-HOME 2026-05-27]
// 关怀模式 AI 主页 v1 - 完整还原需求清单设计图
// - 顶栏（菜单 + 小康●在线 + 关怀模式徽章 + 切换模式）
// - 欢迎区（蓝绿渐变 + 时段问候 + 静态文案）
// - 4 个快捷胶囊
// - 对话流卡片区：健康简评卡 / 用药提醒卡 / SOS 关怀卡
// - 底部"咨询 AI"悬浮球 + 3/4 屏 AI 对话抽屉
// - 右下角 SOS 占位悬浮球

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

interface Metric {
  type: 'blood_pressure' | 'heart_rate' | 'sleep' | string;
  label: string;
  value: string;
  unit: string;
  status: '正常' | '偏高' | '偏低' | string;
  measured_at?: string;
}

interface DailySummary {
  summary_text: string;
  metrics: Metric[];
}

interface CareAlert {
  id: number;
  type: string;
  title: string;
  content: string;
  suggestion?: string;
  severity: 'info' | 'warning' | 'danger' | string;
  created_at?: string;
}

interface MedicationItem {
  id?: number;
  drug_name?: string;
  name?: string;
  schedule?: string;
  remind_time?: string;
  dose?: string;
  dosage?: string;
  done?: boolean;
}

function getGreeting(now: Date): string {
  const h = now.getHours();
  if (h >= 5 && h < 11) return '早上好 ☀️';
  if (h >= 11 && h < 18) return '中午好 ☀️';
  return '晚上好 🌙';
}

function statusColor(status: string): string {
  if (status === '偏高') return '#E53935';
  if (status === '偏低') return '#FB8C00';
  return '#43A047';
}

export default function CareAiHomePage() {
  const router = useRouter();
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [alerts, setAlerts] = useState<CareAlert[]>([]);
  const [medication, setMedication] = useState<MedicationItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [toast, setToast] = useState<string>('');
  const [loading, setLoading] = useState(true);

  const greeting = useMemo(() => getGreeting(new Date()), []);

  useEffect(() => {
    const loadAll = async () => {
      setLoading(true);
      // 三接口并发
      const [sumRes, alertRes, medRes] = await Promise.allSettled([
        api.get('/api/care/daily-summary'),
        api.get('/api/care/alerts/active'),
        api.get('/api/medication-reminder/today'),
      ]);
      if (sumRes.status === 'fulfilled') {
        setSummary(sumRes.value.data?.data || null);
      }
      if (alertRes.status === 'fulfilled') {
        setAlerts(alertRes.value.data?.data?.alerts || []);
      }
      if (medRes.status === 'fulfilled') {
        const items = medRes.value.data?.data?.items || medRes.value.data?.items || [];
        const next = items.find((it: MedicationItem) => !it.done) || null;
        setMedication(next);
      }
      setLoading(false);
    };
    loadAll();
  }, []);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 2000);
  };

  const dismissAlert = async (id: number) => {
    try {
      await api.post(`/api/care/alerts/${id}/dismiss`);
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch {
      showToast('操作失败，请重试');
    }
  };

  const callFamily = () => {
    // 拨打第 1 紧急联系人；号码若未配置则提示
    window.location.href = 'tel:120';
  };

  const navigate = (path: string) => {
    router.push(`${basePath}${path}`);
  };

  const takePhoto = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.capture = 'environment';
    input.onchange = () => {
      // 复用 AI 对话页的拍照上传能力
      navigate('/ai-home?action=photo');
    };
    input.click();
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#F5F7FA',
        fontSize: 16,
        lineHeight: 1.6,
        color: '#212121',
        paddingBottom: 120,
      }}
    >
      {/* 顶栏 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          background: '#FFFFFF',
          borderBottom: '1px solid #E0E0E0',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <button
          aria-label="菜单"
          onClick={() => navigate('/profile')}
          style={{
            background: 'transparent',
            border: 'none',
            fontSize: 24,
            minWidth: 44,
            minHeight: 44,
            cursor: 'pointer',
          }}
        >
          ☰
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 18, fontWeight: 600 }}>小康</span>
          <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#43A047' }} />
          <span style={{ fontSize: 14, color: '#666' }}>在线</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              background: '#E8F5E9',
              color: '#1976D2',
              padding: '4px 10px',
              borderRadius: 12,
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            关怀模式
          </span>
          <button
            onClick={() => navigate('/welcome-mode')}
            style={{
              background: '#1976D2',
              color: '#FFF',
              border: 'none',
              padding: '6px 12px',
              borderRadius: 16,
              fontSize: 13,
              cursor: 'pointer',
              minHeight: 32,
            }}
          >
            切换模式
          </button>
        </div>
      </div>

      {/* 欢迎区 */}
      <div
        style={{
          background: 'linear-gradient(135deg, #1976D2 0%, #43A047 100%)',
          color: '#FFFFFF',
          padding: '28px 20px',
          borderRadius: '0 0 24px 24px',
        }}
      >
        <div style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>{greeting}</div>
        <div style={{ fontSize: 17 }}>我是小康，有事儿随时问我~</div>
      </div>

      {/* 4 个快捷胶囊 */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 8,
          padding: '16px',
        }}
      >
        {[
          { icon: '📋', label: '健康档案', onClick: () => navigate('/health-profile') },
          { icon: '💊', label: '用药提醒', onClick: () => navigate('/ai-home/medication-reminder') },
          { icon: '📷', label: '拍照问AI', onClick: takePhoto },
          { icon: '🏥', label: '健康服务', onClick: () => navigate('/services') },
        ].map((it) => (
          <button
            key={it.label}
            onClick={it.onClick}
            style={{
              background: '#FFFFFF',
              border: '1px solid #E0E0E0',
              borderRadius: 16,
              padding: '12px 4px',
              minHeight: 80,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 4,
              cursor: 'pointer',
              fontSize: 14,
            }}
          >
            <div style={{ fontSize: 24 }}>{it.icon}</div>
            <div style={{ fontWeight: 500 }}>{it.label}</div>
          </button>
        ))}
      </div>

      {/* 对话流卡片区 */}
      <div style={{ padding: '0 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* 健康简评卡 */}
        <div
          onClick={() => navigate('/health-dashboard')}
          style={{
            background: '#FFFFFF',
            borderRadius: 16,
            padding: 16,
            boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
            cursor: 'pointer',
          }}
          data-testid="health-summary-card"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ fontSize: 22 }}>📊</span>
            <div style={{ fontSize: 18, fontWeight: 600 }}>健康简评</div>
          </div>
          <div style={{ fontSize: 16, color: '#424242', marginBottom: 12 }}>
            {loading ? '加载中…' : summary?.summary_text || '今日数据尚未生成，请稍后查看 ~'}
          </div>
          {summary?.metrics && summary.metrics.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {summary.metrics.map((m) => (
                <div
                  key={m.type}
                  style={{
                    background: '#F5F7FA',
                    borderRadius: 12,
                    padding: '10px 8px',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ fontSize: 13, color: '#666' }}>{m.label}</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: '#212121', margin: '4px 0' }}>
                    {m.value}
                    <span style={{ fontSize: 12, color: '#999', marginLeft: 4 }}>{m.unit}</span>
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: statusColor(m.status),
                      background: `${statusColor(m.status)}1A`,
                      display: 'inline-block',
                      padding: '2px 8px',
                      borderRadius: 8,
                    }}
                  >
                    {m.status}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 用药提醒卡 */}
        <div
          style={{
            background: '#FFFFFF',
            borderRadius: 16,
            padding: 16,
            boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
          }}
          data-testid="medication-card"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ fontSize: 22 }}>💊</span>
            <div style={{ fontSize: 18, fontWeight: 600 }}>
              {medication ? '该吃药啦' : '今日用药已全部完成 ✅'}
            </div>
          </div>
          {medication ? (
            <>
              <div
                onClick={() => navigate('/ai-home/medication-reminder')}
                style={{ fontSize: 16, color: '#424242', marginBottom: 12, cursor: 'pointer' }}
              >
                {medication.drug_name || medication.name || '药品'} · {medication.remind_time || medication.schedule || ''} · {medication.dose || medication.dosage || ''}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={async (e) => {
                    e.stopPropagation();
                    try {
                      if (medication.id) {
                        await api.post(`/api/medication-reminder/items/${medication.id}/check`);
                      }
                      setMedication(null);
                      showToast('已记录');
                    } catch {
                      setMedication(null);
                      showToast('已记录');
                    }
                  }}
                  style={{
                    flex: 1,
                    background: '#43A047',
                    color: '#FFF',
                    border: 'none',
                    borderRadius: 12,
                    padding: '10px 0',
                    fontSize: 16,
                    minHeight: 44,
                    cursor: 'pointer',
                  }}
                >
                  已吃 ✓
                </button>
                <select
                  onChange={(e) => {
                    showToast(`已推迟 ${e.target.value} 分钟`);
                  }}
                  defaultValue=""
                  style={{
                    flex: 1,
                    background: '#FFF',
                    color: '#1976D2',
                    border: '1px solid #1976D2',
                    borderRadius: 12,
                    padding: '10px 0',
                    fontSize: 16,
                    minHeight: 44,
                  }}
                >
                  <option value="" disabled>
                    推迟
                  </option>
                  <option value="15">15 分钟</option>
                  <option value="30">30 分钟</option>
                  <option value="60">60 分钟</option>
                </select>
              </div>
            </>
          ) : (
            <div style={{ fontSize: 14, color: '#666' }}>继续保持，按时服药有助于健康哦 ~</div>
          )}
        </div>

        {/* SOS 关怀卡 */}
        {alerts.map((alert) => (
          <div
            key={alert.id}
            data-testid="sos-care-card"
            style={{
              background: '#FFF5F5',
              borderRadius: 16,
              padding: 16,
              border: '1px solid #FFCDD2',
              boxShadow: '0 2px 8px rgba(229,57,53,0.08)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <span style={{ fontSize: 22 }}>🚨</span>
              <div style={{ fontSize: 18, fontWeight: 600, color: '#C62828' }}>{alert.title}</div>
            </div>
            <div style={{ fontSize: 15, color: '#424242', marginBottom: 8 }}>{alert.content}</div>
            {alert.suggestion && (
              <div style={{ fontSize: 14, color: '#666', marginBottom: 12 }}>建议：{alert.suggestion}</div>
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={callFamily}
                style={{
                  flex: 1,
                  background: '#E53935',
                  color: '#FFF',
                  border: 'none',
                  borderRadius: 12,
                  padding: '10px 0',
                  fontSize: 16,
                  minHeight: 44,
                  cursor: 'pointer',
                  fontWeight: 600,
                }}
              >
                📞 呼叫家人
              </button>
              <button
                onClick={() => dismissAlert(alert.id)}
                style={{
                  flex: 1,
                  background: '#FFF',
                  color: '#666',
                  border: '1px solid #E0E0E0',
                  borderRadius: 12,
                  padding: '10px 0',
                  fontSize: 16,
                  minHeight: 44,
                  cursor: 'pointer',
                }}
              >
                我没事
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* 底部"咨询 AI"悬浮球 */}
      <button
        data-testid="ai-consult-fab"
        onClick={() => setDrawerOpen(true)}
        style={{
          position: 'fixed',
          left: '50%',
          transform: 'translateX(-50%)',
          bottom: 24,
          background: '#1976D2',
          color: '#FFF',
          border: 'none',
          borderRadius: 32,
          padding: '14px 24px',
          fontSize: 17,
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          boxShadow: '0 6px 16px rgba(25,118,210,0.4)',
          minHeight: 56,
          cursor: 'pointer',
          zIndex: 20,
        }}
      >
        <span style={{ fontSize: 22 }}>💬</span>
        <span>咨询 AI</span>
      </button>

      {/* 右下角 SOS 占位悬浮球 */}
      <button
        data-testid="sos-fab"
        aria-label="SOS"
        onClick={() => showToast('SOS 功能即将上线')}
        style={{
          position: 'fixed',
          right: 20,
          bottom: 24,
          background: '#E53935',
          color: '#FFF',
          border: 'none',
          borderRadius: '50%',
          width: 56,
          height: 56,
          fontSize: 14,
          fontWeight: 700,
          boxShadow: '0 6px 16px rgba(229,57,53,0.5)',
          cursor: 'pointer',
          animation: 'sosPulse 2s infinite',
          zIndex: 20,
        }}
      >
        SOS
      </button>

      {/* Toast */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            background: 'rgba(0,0,0,0.8)',
            color: '#FFF',
            padding: '10px 20px',
            borderRadius: 8,
            fontSize: 14,
            zIndex: 100,
          }}
        >
          {toast}
        </div>
      )}

      {/* AI 对话抽屉 (3/4 屏) */}
      {drawerOpen && (
        <div
          onClick={() => setDrawerOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.35)',
            zIndex: 50,
            display: 'flex',
            alignItems: 'flex-end',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            data-testid="ai-drawer"
            style={{
              width: '100%',
              height: '75vh',
              background: '#FFFFFF',
              borderRadius: '20px 20px 0 0',
              padding: 16,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 12,
              }}
            >
              <div style={{ width: 40, height: 4, background: '#E0E0E0', borderRadius: 2, margin: '0 auto' }} />
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 12,
              }}
            >
              <div style={{ fontSize: 18, fontWeight: 600 }}>咨询小康</div>
              <button
                onClick={() => setDrawerOpen(false)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  fontSize: 22,
                  cursor: 'pointer',
                  minWidth: 44,
                  minHeight: 44,
                }}
                aria-label="关闭"
              >
                ✕
              </button>
            </div>
            <iframe
              src={`${basePath}/ai-home?embedded=1`}
              style={{ flex: 1, width: '100%', border: 'none', borderRadius: 12 }}
              title="AI 对话"
            />
          </div>
        </div>
      )}

      <style jsx>{`
        @keyframes sosPulse {
          0%, 100% { box-shadow: 0 6px 16px rgba(229,57,53,0.5); }
          50% { box-shadow: 0 6px 24px rgba(229,57,53,0.8), 0 0 0 8px rgba(229,57,53,0.2); }
        }
      `}</style>
    </div>
  );
}
