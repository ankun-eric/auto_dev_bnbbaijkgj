'use client';

// [PRD-AIHOME-CARE-V1 2026-05-27] 关怀版 AI 首页
// 包含：顶栏（模式角标）、欢迎区、快捷胶囊、推荐问、AI 主动卡片、底部输入栏、SOS 悬浮球

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

interface WelcomeData {
  nickname: string;
  greeting: string;
  care_text: string;
  main_text: string;
}

interface ProactiveCards {
  health_brief: {
    blood_pressure: { systolic: number; diastolic: number; abnormal: boolean };
    blood_glucose: { value: number; unit: string; abnormal: boolean };
    sleep: { hours: number; abnormal: boolean };
    steps: { value: number; abnormal: boolean };
  };
  med_reminder: { items: { name: string; schedule: string; done: boolean }[] };
  home_safety: {
    devices: { type: string; name: string; status: string; battery: number; abnormal: boolean }[];
  };
}

export default function CareHomePage() {
  const router = useRouter();
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

  const [welcome, setWelcome] = useState<WelcomeData | null>(null);
  const [cards, setCards] = useState<ProactiveCards | null>(null);
  const [showSwitch, setShowSwitch] = useState(false);
  const [sosStage, setSosStage] = useState<0 | 1 | 2 | 3 | 4>(0);
  const [sosCountdown, setSosCountdown] = useState(5);
  const [sosEventId, setSosEventId] = useState<number | null>(null);
  const [inputText, setInputText] = useState('');
  const [sosCard, setSosCard] = useState<{ keyword: string } | null>(null);

  // 加载数据
  useEffect(() => {
    api.get('/api/care-v1/home/welcome').then((r) => setWelcome(r.data?.data || null)).catch(() => {});
    api
      .get('/api/care-v1/home/proactive-cards')
      .then((r) => setCards(r.data?.data || null))
      .catch(() => {});
  }, []);

  // SOS 倒计时
  useEffect(() => {
    if (sosStage !== 1) return;
    if (sosCountdown <= 0) {
      setSosStage(2);
      return;
    }
    const t = setTimeout(() => setSosCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [sosStage, sosCountdown]);

  const startSos = async (source: string, keyword?: string) => {
    setSosStage(1);
    setSosCountdown(5);
    try {
      const resp = await api.post('/api/care-v1/sos/events', {
        trigger_source: source,
        trigger_keyword: keyword,
      });
      setSosEventId(resp.data?.data?.id ?? null);
    } catch {}
  };

  const cancelSos = async () => {
    if (sosEventId) {
      try {
        await api.put(`/api/care-v1/sos/events/${sosEventId}/resolve`, {
          status: 'cancelled',
          countdown_remaining_ms: sosCountdown * 1000,
        });
      } catch {}
    }
    setSosStage(0);
    setSosEventId(null);
  };

  const dispatch120 = async () => {
    if (sosEventId) {
      try {
        await api.put(`/api/care-v1/sos/events/${sosEventId}/resolve`, {
          status: 'dispatched_120',
        });
      } catch {}
    }
    setSosStage(3);
    setTimeout(() => setSosStage(4), 2000);
  };

  const dispatchFamily = async () => {
    if (sosEventId) {
      try {
        await api.put(`/api/care-v1/sos/events/${sosEventId}/resolve`, {
          status: 'dispatched_family',
        });
      } catch {}
    }
    setSosStage(3);
    setTimeout(() => setSosStage(4), 2000);
  };

  const closeSos = async () => {
    if (sosEventId) {
      try {
        await api.put(`/api/care-v1/sos/events/${sosEventId}/resolve`, { status: 'closed' });
      } catch {}
    }
    setSosStage(0);
    setSosEventId(null);
  };

  const detectSosInText = async () => {
    if (!inputText.trim()) return;
    try {
      const resp = await api.post('/api/care-v1/sos/detect', { text: inputText });
      const r = resp.data?.data;
      if (r?.hit) {
        setSosCard({ keyword: (r.matched || []).join('、') });
      }
    } catch {}
  };

  const switchMode = async (mode: 'care' | 'standard') => {
    try {
      await api.put('/api/care-v1/user-preferences/ui-mode', { ui_mode: mode });
      localStorage.setItem('ui_mode', mode);
    } catch {}
    setShowSwitch(false);
    if (mode === 'standard') router.push(`${basePath}/`);
  };

  // ========== SOS 全屏覆盖层 ==========
  if (sosStage === 1) {
    return (
      <div
        style={{
          position: 'fixed',
          inset: 0,
          background: '#E53935',
          color: '#fff',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 22,
          zIndex: 9999,
        }}
      >
        <div style={{ fontSize: 28, fontWeight: 700, marginBottom: 24 }}>正在为您呼叫救援...</div>
        <div style={{ fontSize: 120, fontWeight: 900, lineHeight: 1, marginBottom: 32 }}>
          {sosCountdown}
        </div>
        <button
          onClick={cancelSos}
          style={{
            background: '#fff',
            color: '#E53935',
            fontSize: 22,
            fontWeight: 700,
            padding: '18px 60px',
            borderRadius: 16,
            border: 'none',
            minHeight: 56,
          }}
        >
          我没事 · 取消
        </button>
      </div>
    );
  }

  if (sosStage === 2) {
    return (
      <div
        style={{
          position: 'fixed',
          inset: 0,
          background: '#fff',
          padding: 22,
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div style={{ fontSize: 22, fontWeight: 700, color: '#3d2e1f', marginBottom: 32 }}>
          请选择呼叫对象
        </div>
        <button
          onClick={dispatch120}
          style={{
            background: '#E53935',
            color: '#fff',
            fontSize: 26,
            fontWeight: 800,
            padding: '24px 40px',
            borderRadius: 16,
            border: 'none',
            width: '100%',
            maxWidth: 360,
            minHeight: 110,
            marginBottom: 18,
          }}
        >
          🔴 呼叫 120 · 急救中心
        </button>
        <button
          onClick={dispatchFamily}
          style={{
            background: '#43A047',
            color: '#fff',
            fontSize: 22,
            fontWeight: 700,
            padding: '20px 40px',
            borderRadius: 16,
            border: 'none',
            width: '100%',
            maxWidth: 360,
            minHeight: 110,
            marginBottom: 24,
          }}
        >
          👨‍👩‍👧 呼叫家人
        </button>
        <span onClick={cancelSos} style={{ color: '#999', fontSize: 14 }}>
          先取消，我再看看
        </span>
      </div>
    );
  }

  if (sosStage === 3) {
    return (
      <div
        style={{
          position: 'fixed',
          inset: 0,
          background: '#fff',
          padding: 22,
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div style={{ fontSize: 22, fontWeight: 700, color: '#3d2e1f', marginBottom: 24 }}>
          正在呼叫 120...
        </div>
        <div
          style={{
            width: 60,
            height: 60,
            border: '6px solid #E53935',
            borderTopColor: 'transparent',
            borderRadius: '50%',
            animation: 'sos-spin 1s linear infinite',
          }}
        />
        <style>{`@keyframes sos-spin { to { transform: rotate(360deg); } }`}</style>
        <div style={{ marginTop: 32, fontSize: 16, color: '#555', textAlign: 'center', lineHeight: 1.7 }}>
          ✅ 已发送位置短信
          <br />
          ✅ 已附健康摘要
          <br />
          ✅ 已通知家人
        </div>
      </div>
    );
  }

  if (sosStage === 4) {
    return (
      <div style={{ padding: 22, minHeight: '100vh', background: '#f0f6fb' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 64 }}>✅</div>
          <div style={{ fontSize: 26, fontWeight: 800, color: '#43A047', marginTop: 8 }}>
            求救已送达
          </div>
        </div>
        <div
          style={{ background: '#fff', borderRadius: 18, padding: 18, marginBottom: 16, fontSize: 16, lineHeight: 1.9 }}
        >
          <div>📞 120 接听 ✓</div>
          <div>🚑 救护车出发 ✓</div>
          <div>⏱ 预计 8 分钟到达</div>
        </div>
        <div
          style={{ background: '#fff', borderRadius: 18, padding: 18, marginBottom: 24, fontSize: 16 }}
        >
          👨‍👩‍👧 李子（女儿）已查看 · 正在赶来
        </div>
        <button
          onClick={closeSos}
          style={{
            width: '100%',
            background: '#43A047',
            color: '#fff',
            fontSize: 20,
            fontWeight: 700,
            padding: 18,
            borderRadius: 14,
            border: 'none',
            minHeight: 56,
            marginBottom: 12,
          }}
        >
          我已安全
        </button>
        <button
          onClick={() => startSos('manual')}
          style={{
            width: '100%',
            background: '#fff',
            color: '#E53935',
            fontSize: 18,
            fontWeight: 700,
            padding: 16,
            borderRadius: 14,
            border: '2px solid #E53935',
            minHeight: 56,
          }}
        >
          再次呼叫
        </button>
      </div>
    );
  }

  // ========== 主页面 ==========
  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(180deg,#fff5e8 0%,#f0f6fb 100%)',
        paddingBottom: 100,
        position: 'relative',
        fontSize: 18,
      }}
    >
      {/* 顶栏 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          background: '#fff',
          height: 56,
          boxSizing: 'border-box',
        }}
      >
        <span style={{ fontSize: 24, color: '#555' }}>☰</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: '50%',
              background: 'linear-gradient(135deg,#5b8fd6,#1976D2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontWeight: 800,
              fontSize: 18,
            }}
          >
            康
          </div>
          <span style={{ fontSize: 16, fontWeight: 700 }}>宾尼小康</span>
        </div>
        <div
          onClick={() => setShowSwitch(true)}
          style={{
            background: 'linear-gradient(90deg,#ff9156,#ff6b3d)',
            color: '#fff',
            fontSize: 13,
            padding: '6px 12px',
            borderRadius: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            boxShadow: '0 4px 12px rgba(255,107,61,.3)',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          <span>👵</span>
          <span>关怀模式</span>
          <span>▼</span>
        </div>
      </div>

      {/* 切换弹层 */}
      {showSwitch && (
        <div
          onClick={() => setShowSwitch(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,.3)',
            zIndex: 1000,
            display: 'flex',
            justifyContent: 'flex-end',
            paddingTop: 60,
            paddingRight: 16,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#fff',
              borderRadius: 18,
              width: 260,
              overflow: 'hidden',
              boxShadow: '0 8px 32px rgba(0,0,0,.15)',
              alignSelf: 'flex-start',
            }}
          >
            <div
              style={{
                background: 'linear-gradient(90deg,#ff9156,#ff6b3d)',
                color: '#fff',
                padding: '14px 16px',
                fontSize: 16,
                fontWeight: 700,
              }}
            >
              🔄 切换使用模式
            </div>
            <div onClick={() => switchMode('care')} style={{ padding: 14, borderBottom: '1px solid #eee' }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#ff6b3d' }}>👵 关怀模式 ✓</div>
              <div style={{ fontSize: 13, color: '#888', marginTop: 4 }}>大字大按钮，语音优先</div>
            </div>
            <div onClick={() => switchMode('standard')} style={{ padding: 14 }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#3865a8' }}>🧑‍💼 标准模式</div>
              <div style={{ fontSize: 13, color: '#888', marginTop: 4 }}>功能更全，操作更高效</div>
            </div>
            <div style={{ background: '#f8f8f8', padding: 10, fontSize: 12, color: '#888', textAlign: 'center' }}>
              切换后立即生效，数据不会丢失
            </div>
          </div>
        </div>
      )}

      {/* 欢迎区 */}
      <div style={{ padding: '22px 22px 14px' }}>
        <div style={{ fontSize: 28, fontWeight: 800, color: '#3d2e1f', lineHeight: 1.3 }}>
          {welcome ? `${welcome.nickname}，${welcome.greeting}` : '您好，欢迎使用 ☀️'}
        </div>
        <div style={{ fontSize: 18, color: '#5a4838', marginTop: 8 }}>
          {welcome?.care_text || '今天也要好好照顾自己 ❤'}
        </div>
      </div>

      {/* 快捷胶囊行 */}
      <div style={{ display: 'flex', gap: 8, padding: '0 22px 14px' }}>
        {[
          { icon: '📋', label: '档案', bg: '#e3f2fd', path: '/health-profile' },
          { icon: '💊', label: '用药', bg: '#fff3e0', path: '/health-reminders' },
          { icon: '📷', label: '拍照问AI', bg: '#e8f5e9', path: '/ai-home' },
          { icon: '👨‍👩‍👧', label: '家人', bg: '#fce4ec', path: '/family' },
        ].map((c) => (
          <div
            key={c.label}
            onClick={() => router.push(`${basePath}${c.path}`)}
            style={{
              flex: 1,
              background: '#fff',
              borderRadius: 14,
              padding: '10px 0',
              textAlign: 'center',
              minHeight: 64,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              cursor: 'pointer',
            }}
          >
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: c.bg,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 4px',
                fontSize: 22,
              }}
            >
              {c.icon}
            </div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{c.label}</div>
          </div>
        ))}
      </div>

      {/* [PRD-SAFETY-ROPE-V1 2026-06-03] [BUGFIX-SAFETY-ROPE-V1 2026-06-03 Bug1]
          数字安全绳入口卡片 — 紧贴 SOS（在快捷胶囊下方做绿色横卡，作为页面内主入口） */}
      <div style={{ padding: '0 22px 14px' }}>
        <div
          data-testid="care-home-safety-rope-entry"
          onClick={() => router.push(`${basePath}/care-safety-rope`)}
          style={{
            background: 'linear-gradient(135deg, #66bb6a 0%, #2e7d32 100%)',
            borderRadius: 18,
            padding: '16px 18px',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            cursor: 'pointer',
            boxShadow: '0 6px 18px rgba(46,125,50,0.32)',
            border: '2px solid #fff',
          }}
        >
          <div style={{ fontSize: 40, marginRight: 14 }}>🪢</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 18, fontWeight: 800 }}>数字安全绳</div>
            <div style={{ fontSize: 13, opacity: 0.95, marginTop: 3 }}>
              每天点一下"我今天平安"，超时自动通知亲友
            </div>
          </div>
          <div style={{ fontSize: 24, marginLeft: 8, fontWeight: 700 }}>›</div>
        </div>
      </div>

      {/* 推荐问胶囊 */}
      <div
        style={{
          overflowX: 'auto',
          whiteSpace: 'nowrap',
          padding: '0 22px 14px',
          WebkitOverflowScrolling: 'touch',
        }}
      >
        {['我的血压怎么样？', '最近睡眠如何？', '今天饮食建议？', '帮我看看体检报告', '我能吃这个药吗？', '想问问医生'].map((q) => (
          <span
            key={q}
            onClick={() => router.push(`${basePath}/ai-home?q=${encodeURIComponent(q)}`)}
            style={{
              display: 'inline-block',
              padding: '8px 16px',
              background: '#fff5e8',
              color: '#c95a1d',
              borderRadius: 22,
              marginRight: 8,
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {q}
          </span>
        ))}
      </div>

      {/* AI 主动卡片 */}
      <div style={{ padding: '0 22px' }}>
        {sosCard && (
          <div
            style={{
              background: '#fff',
              borderLeft: '6px solid #E53935',
              borderRadius: 14,
              padding: 18,
              marginBottom: 16,
            }}
          >
            <div style={{ fontSize: 16, fontWeight: 700, color: '#E53935', marginBottom: 8 }}>
              🔴 SOS 关怀
            </div>
            <div style={{ fontSize: 16, marginBottom: 14, lineHeight: 1.6 }}>
              我刚刚听到您说"{sosCard.keyword}"，您还好吗？
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={() => setSosCard(null)}
                style={{
                  flex: 1,
                  background: '#f5f5f5',
                  border: 'none',
                  borderRadius: 12,
                  padding: 14,
                  fontSize: 16,
                  minHeight: 56,
                }}
              >
                我没事 ✕
              </button>
              <button
                onClick={() => {
                  setSosCard(null);
                  startSos('keyword_combo', sosCard.keyword);
                }}
                style={{
                  flex: 1,
                  background: '#E53935',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 12,
                  padding: 14,
                  fontSize: 16,
                  fontWeight: 700,
                  minHeight: 56,
                }}
              >
                我需要帮助 🆘
              </button>
            </div>
          </div>
        )}

        {/* 健康简报卡 */}
        {cards?.health_brief && (
          <div style={{ background: '#fff', borderRadius: 18, padding: 18, marginBottom: 16 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#43A047', marginBottom: 12 }}>
              🟢 健康简报 · 今日
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <div style={{ fontSize: 14, color: '#888' }}>🩸 血压</div>
                <div
                  style={{
                    fontSize: 22,
                    fontWeight: 800,
                    color: cards.health_brief.blood_pressure.abnormal ? '#E53935' : '#3d2e1f',
                  }}
                >
                  {cards.health_brief.blood_pressure.systolic}/{cards.health_brief.blood_pressure.diastolic}
                </div>
                <div style={{ fontSize: 12, color: '#888' }}>mmHg</div>
              </div>
              <div>
                <div style={{ fontSize: 14, color: '#888' }}>🩸 血糖</div>
                <div
                  style={{
                    fontSize: 22,
                    fontWeight: 800,
                    color: cards.health_brief.blood_glucose.abnormal ? '#E53935' : '#3d2e1f',
                  }}
                >
                  {cards.health_brief.blood_glucose.value}
                </div>
                <div style={{ fontSize: 12, color: '#888' }}>{cards.health_brief.blood_glucose.unit}</div>
              </div>
              <div>
                <div style={{ fontSize: 14, color: '#888' }}>😴 睡眠</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: '#3d2e1f' }}>
                  {cards.health_brief.sleep.hours}h
                </div>
              </div>
              <div>
                <div style={{ fontSize: 14, color: '#888' }}>👣 步数</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: '#3d2e1f' }}>
                  {cards.health_brief.steps.value}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 用药提醒卡 */}
        {cards?.med_reminder && (
          <div style={{ background: '#fff', borderRadius: 18, padding: 18, marginBottom: 16 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#FB8C00', marginBottom: 12 }}>
              🟠 用药提醒
            </div>
            {cards.med_reminder.items.map((m, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: i < cards.med_reminder.items.length - 1 ? 10 : 0,
                }}
              >
                <div style={{ fontSize: 16 }}>
                  💊 {m.name}（{m.schedule}）
                </div>
                <button
                  style={{
                    background: m.done ? '#ddd' : '#43A047',
                    color: '#fff',
                    border: 'none',
                    padding: '8px 14px',
                    borderRadius: 12,
                    minHeight: 40,
                    minWidth: 70,
                  }}
                >
                  {m.done ? '已吃 ✓' : '已吃 ✓'}
                </button>
              </div>
            ))}
          </div>
        )}

        {/* 居家安全卡 */}
        {cards?.home_safety && (
          <div style={{ background: '#fff', borderRadius: 18, padding: 18, marginBottom: 16 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#00897B', marginBottom: 12 }}>
              🩵 居家安全
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {cards.home_safety.devices.map((d, i) => (
                <div
                  key={i}
                  style={{
                    padding: 10,
                    borderRadius: 10,
                    background: d.abnormal ? '#fff3e0' : '#f5fafd',
                  }}
                >
                  <div style={{ fontSize: 14, fontWeight: 600 }}>
                    {d.type === 'emergency_caller' ? '🆘' : '🚨'} {d.name}
                  </div>
                  <div style={{ fontSize: 13, color: d.abnormal ? '#c95a1d' : '#888', marginTop: 4 }}>
                    {d.status === 'online' ? '在线' : '离线'} · 电量 {d.battery}%
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 底部输入栏 */}
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          background: '#fff',
          padding: 12,
          display: 'flex',
          gap: 10,
          alignItems: 'center',
          boxShadow: '0 -2px 8px rgba(0,0,0,.05)',
          zIndex: 100,
        }}
      >
        <input
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onBlur={detectSosInText}
          placeholder="✏️ 输入或按住右侧说话..."
          style={{
            flex: 1,
            border: '1px solid #ddd',
            borderRadius: 22,
            padding: '12px 16px',
            fontSize: 16,
            minHeight: 44,
            outline: 'none',
          }}
        />
        <div
          onClick={() => router.push(`${basePath}/ai-home`)}
          style={{
            width: 56,
            height: 56,
            borderRadius: '50%',
            background: 'linear-gradient(135deg,#ff9156,#ff6b3d)',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 24,
            cursor: 'pointer',
          }}
        >
          🎤
        </div>
      </div>

      {/* SOS 悬浮球 */}
      <div
        onClick={() => startSos('floating_button')}
        style={{
          position: 'fixed',
          right: 16,
          bottom: 96,
          width: 72,
          height: 72,
          borderRadius: '50%',
          background: '#E53935',
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 16,
          fontWeight: 800,
          boxShadow: '0 0 0 8px rgba(229,57,53,.2), 0 4px 16px rgba(229,57,53,.4)',
          zIndex: 99,
          cursor: 'pointer',
        }}
      >
        SOS
      </div>

      {/* [BUGFIX-SAFETY-ROPE-V1 2026-06-03 Bug1] 数字安全绳悬浮球——紧贴 SOS（左侧），双入口可见 */}
      <div
        data-testid="care-home-safety-rope-fab"
        onClick={() => router.push(`${basePath}/care-safety-rope`)}
        style={{
          position: 'fixed',
          right: 100,
          bottom: 96,
          width: 72,
          height: 72,
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #66bb6a 0%, #2e7d32 100%)',
          color: '#fff',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 13,
          fontWeight: 700,
          boxShadow: '0 0 0 8px rgba(46,125,50,.18), 0 4px 16px rgba(46,125,50,.4)',
          zIndex: 99,
          cursor: 'pointer',
          lineHeight: 1.1,
        }}
      >
        <span style={{ fontSize: 22 }}>🪢</span>
        <span style={{ fontSize: 10, marginTop: 2 }}>安全绳</span>
      </div>
    </div>
  );
}
