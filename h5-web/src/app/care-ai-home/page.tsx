'use client';

// [PRD-CARE-MODE-OPTIM-V1 2026-05-31] 关怀模式首页优化
// 自上而下三块：
//   1. 顶部固定栏（与标准模式一致：☰ 菜单 / 小康 / 模式切换胶囊 + 🎁 + ⊕加圈）
//   2. 欢迎区（蓝绿渐变 + 时段问候 + 小字 + 今日用药提醒 + 宾尼小康机器人 LOGO 窄白边白圈）
//   3. 核心入口区（5 张大字整行卡片）

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { saveModePreference } from '@/lib/mode-preference';

interface MedicationItem {
  id?: number;
  drug_name?: string;
  name?: string;
  schedule?: string;
  scheduled_time?: string;
  remind_time?: string;
  dose?: string;
  dosage?: string;
  done?: boolean;
}

function getGreeting(now: Date): { text: string; icon: string } {
  const h = now.getHours();
  if (h >= 5 && h < 11) return { text: '早上好', icon: '☀️' };
  if (h >= 11 && h < 18) return { text: '中午好', icon: '🌤️' };
  return { text: '晚上好', icon: '🌙' };
}

export default function CareAiHomePage() {
  const router = useRouter();
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

  const [medText, setMedText] = useState<string>('');
  const [modeDropdownOpen, setModeDropdownOpen] = useState(false);
  const [modeSwitching, setModeSwitching] = useState(false);
  const [toast, setToast] = useState<string>('');
  const modeDropdownRef = useRef<HTMLDivElement | null>(null);

  const greeting = useMemo(() => getGreeting(new Date()), []);

  const navigate = (path: string) => router.push(path);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 2000);
  };

  // 读取最新一条用药提醒
  useEffect(() => {
    const load = async () => {
      try {
        const res: any = await api.get('/api/medication-reminder/today');
        // 拦截器已返回 body；today 返回的是数组
        const items: MedicationItem[] = Array.isArray(res)
          ? res
          : res?.data?.items || res?.items || res?.data || [];
        if (Array.isArray(items) && items.length > 0) {
          const next = items.find((it) => !it.done) || items[0];
          const time = next.scheduled_time || next.remind_time || next.schedule || '';
          const drug = next.drug_name || next.name || '药品';
          setMedText(`${time ? time + ' ' : ''}请按时服用"${drug}"`);
        } else {
          setMedText('今日暂无用药提醒');
        }
      } catch {
        setMedText('今日暂无用药提醒');
      }
    };
    load();
  }, []);

  // 面板外点击收起
  useEffect(() => {
    if (!modeDropdownOpen) return;
    const onDocClick = (e: MouseEvent) => {
      if (modeDropdownRef.current && !modeDropdownRef.current.contains(e.target as Node)) {
        setModeDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [modeDropdownOpen]);

  const handleSwitchToStandard = async () => {
    if (modeSwitching) return;
    setModeSwitching(true);
    try {
      await saveModePreference('standard');
    } catch {
      /* 偏好保存失败不阻断跳转 */
    }
    showToast('已切换到标准模式 ✓');
    setModeDropdownOpen(false);
    setTimeout(() => router.push('/ai-home'), 300);
  };

  // 5 张大字整行卡片
  const cards = [
    {
      key: 'medication',
      icon: '💊',
      bg: 'linear-gradient(135deg, #42A5F5 0%, #1E88E5 100%)',
      title: '用药提醒',
      desc: '查看今日完整用药提醒列表',
      onClick: () => navigate('/health-profile?tab=self&focus=medication'),
    },
    {
      key: 'health-record',
      icon: '📈',
      bg: 'linear-gradient(135deg, #66BB6A 0%, #43A047 100%)',
      title: '健康记录',
      desc: '血压、血糖、心率、血氧、睡眠',
      onClick: () => navigate('/care-ai-home/today-health'),
    },
    {
      key: 'home-safety',
      icon: '🛡️',
      bg: 'linear-gradient(135deg, #FFA726 0%, #FB8C00 100%)',
      title: '居家安全设备',
      desc: '紧急呼叫器 / 烟雾报警器 / 水浸报警器',
      onClick: () => navigate('/home-safety'),
    },
    {
      key: 'sos',
      icon: '🆘',
      bg: 'linear-gradient(135deg, #EF5350 0%, #E53935 100%)',
      title: '紧急呼叫',
      desc: '一键 SOS 求助、联系家人与急救',
      onClick: () => navigate('/care-ai-home/sos'),
    },
    {
      key: 'info-card',
      icon: '🪪',
      bg: 'linear-gradient(135deg, #AB47BC 0%, #8E24AA 100%)',
      title: '个人信息卡',
      desc: '身份与健康名片，便于出示与求助',
      onClick: () => navigate('/care-ai-home/info-card'),
    },
  ];

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#F5F7FA',
        fontSize: 16,
        lineHeight: 1.6,
        color: '#212121',
        paddingBottom: 40,
      }}
      data-testid="care-ai-home-page"
    >
      {/* 1. 顶部固定栏（与标准模式一致） */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 100,
          background: 'linear-gradient(180deg, #F0F9FF 0%, #DBEAFE 100%)',
          maxWidth: 750,
          margin: '0 auto',
        }}
        data-testid="care-home-topbar"
      >
        <div style={{ position: 'relative', height: 48, width: '100%' }}>
          {/* 左：☰ 菜单 */}
          <button
            aria-label="菜单"
            onClick={() => navigate('/profile')}
            data-testid="care-home-hamburger-btn"
            style={{
              position: 'absolute',
              left: 8,
              top: '50%',
              transform: 'translateY(-50%)',
              width: 32,
              height: 32,
              background: 'transparent',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#0C4A6E',
            }}
          >
            <svg width={21} height={17} viewBox="0 0 21 17" aria-hidden="true">
              <rect x={0} y={0} width={16} height={2.5} rx={1.25} fill="currentColor" />
              <rect x={0} y={7} width={16} height={2.5} rx={1.25} fill="currentColor" />
              <rect x={0} y={14} width={11} height={2.5} rx={1.25} fill="currentColor" />
            </svg>
          </button>

          {/* 中：小康 */}
          <div
            style={{
              position: 'absolute',
              left: '50%',
              transform: 'translateX(-50%)',
              top: 0,
              bottom: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span
              style={{ fontSize: 18, fontWeight: 600, color: '#0C4A6E', lineHeight: 1 }}
              data-testid="care-home-topbar-title"
            >
              小康
            </span>
          </div>

          {/* 右：模式切换胶囊 + 🎁 + ⊕加圈 */}
          {/* 🎁 礼物 */}
          <button
            type="button"
            onClick={() => navigate('/invite')}
            aria-label="邀请好友"
            data-testid="care-home-invite-btn"
            style={{
              position: 'absolute',
              right: 44,
              top: '50%',
              transform: 'translateY(-50%)',
              width: 32,
              height: 32,
              background: 'transparent',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
            }}
          >
            <span style={{ fontSize: 20, lineHeight: 1 }} aria-hidden="true">🎁</span>
          </button>

          {/* 模式切换下拉胶囊（当前：关怀模式） */}
          <div
            ref={modeDropdownRef}
            style={{ position: 'absolute', right: 80, top: '50%', transform: 'translateY(-50%)' }}
            data-testid="care-home-mode-switcher"
          >
            <button
              type="button"
              onClick={() => setModeDropdownOpen((v) => !v)}
              disabled={modeSwitching}
              aria-haspopup="listbox"
              aria-expanded={modeDropdownOpen}
              aria-label="模式切换"
              data-testid="care-home-mode-capsule"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                background: '#E8F5E9',
                color: '#2E7D32',
                border: 'none',
                padding: '5px 10px',
                borderRadius: 14,
                fontSize: 13,
                fontWeight: 600,
                lineHeight: 1,
                whiteSpace: 'nowrap',
                cursor: modeSwitching ? 'default' : 'pointer',
                minHeight: 28,
              }}
            >
              <span data-testid="care-home-mode-capsule-label">关怀模式</span>
              <span
                aria-hidden="true"
                style={{
                  display: 'inline-block',
                  fontSize: 10,
                  lineHeight: 1,
                  transform: modeDropdownOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.15s ease',
                }}
              >
                ▾
              </span>
            </button>

            {modeDropdownOpen ? (
              <div
                role="listbox"
                data-testid="care-home-mode-dropdown-panel"
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 6px)',
                  right: 0,
                  minWidth: 120,
                  background: '#FFFFFF',
                  borderRadius: 10,
                  boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
                  border: '1px solid #E5E7EB',
                  overflow: 'hidden',
                  zIndex: 50,
                }}
              >
                {/* 标准模式（切换） */}
                <div
                  role="option"
                  aria-selected={false}
                  onClick={handleSwitchToStandard}
                  data-testid="care-home-mode-option-standard"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 8,
                    padding: '10px 14px',
                    fontSize: 14,
                    fontWeight: 500,
                    color: '#374151',
                    background: '#FFFFFF',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <span>标准模式</span>
                  <span aria-hidden="true" style={{ width: 14 }} />
                </div>
                {/* 关怀模式（当前，高亮打勾） */}
                <div
                  role="option"
                  aria-selected={true}
                  onClick={() => setModeDropdownOpen(false)}
                  data-testid="care-home-mode-option-care"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 8,
                    padding: '10px 14px',
                    fontSize: 14,
                    fontWeight: 600,
                    color: '#2E7D32',
                    background: '#E8F5E9',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <span>关怀模式</span>
                  <span aria-hidden="true">✓</span>
                </div>
              </div>
            ) : null}
          </div>

          {/* ⊕ 加圈 */}
          <button
            aria-label="更多"
            onClick={() => navigate('/invite')}
            data-testid="care-home-more-btn"
            style={{
              position: 'absolute',
              right: 8,
              top: '50%',
              transform: 'translateY(-50%)',
              width: 32,
              height: 32,
              background: 'transparent',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              color: '#0C4A6E',
            }}
          >
            <svg width={22} height={22} viewBox="0 0 22 22" aria-hidden="true">
              <circle cx={11} cy={11} r={9.5} fill="none" stroke="currentColor" strokeWidth={1.6} />
              <line x1={11} y1={6} x2={11} y2={16} stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" />
              <line x1={6} y1={11} x2={16} y2={11} stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* 2. 欢迎区（蓝绿渐变） */}
      <div
        style={{
          background: 'linear-gradient(135deg, #1976D2 0%, #43A047 100%)',
          color: '#FFFFFF',
          padding: '24px 20px',
          borderRadius: '0 0 24px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
        data-testid="care-home-welcome"
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 28, fontWeight: 700, marginBottom: 6 }} data-testid="care-home-greeting">
            {greeting.text} {greeting.icon}
          </div>
          <div style={{ fontSize: 16, opacity: 0.95, marginBottom: 14 }}>
            我是小康，有健康问题随时问我~
          </div>
          {/* 今日用药提醒 */}
          <div
            data-testid="care-home-med-reminder"
            style={{
              background: 'rgba(255,255,255,0.18)',
              borderRadius: 12,
              padding: '8px 12px',
              fontSize: 14,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              maxWidth: '100%',
            }}
          >
            <span aria-hidden="true">🔔</span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
              今日提醒：{medText || '加载中…'}
            </span>
          </div>
        </div>

        {/* 右侧：宾尼小康机器人 LOGO + 窄白边白圈（样式①） */}
        <div
          data-testid="care-home-robot-logo"
          style={{
            flexShrink: 0,
            width: 84,
            height: 84,
            borderRadius: '50%',
            background: '#FFFFFF',
            border: '2px solid rgba(255,255,255,0.9)',
            boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`${basePath}/binni-xiaokang-logo.png`}
            alt="宾尼小康"
            style={{ width: 74, height: 74, borderRadius: '50%', objectFit: 'cover' }}
          />
        </div>
      </div>

      {/* 3. 核心入口区 —— 5 张大字整行卡片 */}
      <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: 14 }} data-testid="care-home-cards">
        {cards.map((c) => (
          <button
            key={c.key}
            onClick={c.onClick}
            data-testid={`care-home-card-${c.key}`}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 16,
              width: '100%',
              background: '#FFFFFF',
              border: '1px solid #EEF1F4',
              borderRadius: 18,
              padding: '18px 16px',
              cursor: 'pointer',
              textAlign: 'left',
              boxShadow: '0 2px 10px rgba(0,0,0,0.04)',
            }}
          >
            <div
              style={{
                flexShrink: 0,
                width: 56,
                height: 56,
                borderRadius: 16,
                background: c.bg,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 28,
              }}
              aria-hidden="true"
            >
              {c.icon}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 21, fontWeight: 700, color: '#1F2937', marginBottom: 4 }}>
                {c.title}
              </div>
              <div style={{ fontSize: 14, color: '#9CA3AF', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {c.desc}
              </div>
            </div>
            <span style={{ flexShrink: 0, fontSize: 24, color: '#C4CDD5' }} aria-hidden="true">›</span>
          </button>
        ))}
      </div>

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
            zIndex: 200,
          }}
        >
          {toast}
        </div>
      )}
    </div>
  );
}
