'use client';

// [PRD-CARE-MODE-OPTIM-V4 2026-05-31] 关怀模式首页 V4 补齐（H5）
// 顶栏照搬标准模式：☰ 历史 / 宾尼小康标题 / 「宾尼小康 模式切换」胶囊 + 🎁 + ⋯更多，去掉会报错的 ⊕ 加圈
// 主体（蓝绿大卡 + 竖排功能卡片）保持原样；右下角新增悬浮 SOS（红圆 + 扩散光圈）
// 自上而下：
//   1. 顶部固定栏（☰ / 宾尼小康 / 模式切换胶囊 + 🎁 + ⋯更多）
//   2. 欢迎区（蓝绿渐变 + 时段问候 + 欢迎语 + 今日用药提醒 + 宾尼小康机器人 LOGO）
//   3. 核心入口区（5 张大字整行卡片）
//   4. 右下角悬浮 SOS

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { saveModePreference } from '@/lib/mode-preference';
import MoreMenu from '@/components/ai-chat/MoreMenu';

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
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
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
      // [需求4] 直接进入本人独立的「用药提醒」页面（health-plan/medications，H5 即 /ai-home/medication-reminder，取本人数据）
      onClick: () => navigate('/ai-home/medication-reminder'),
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
      title: '居家安全',
      desc: '紧急呼叫、烟雾报警、水浸报警',
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
      {/* 1. 顶部固定栏（[PRD-AIHOME-UNIFY-V1 2026-06-01 §需求1] 与标准版完全统一：
          ☰三横杠(带红点) → 档案/咨询/服务 三 Tab(当前停咨询·蓝下划线) → 🔔铃铛 → ⊕加号圈。
          原「宾尼小康 模式切换」胶囊、🎁邀请图标已全部移除。 */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 100,
          background: 'linear-gradient(180deg, #EAF6FF 0%, #DCEFFF 100%)',
          maxWidth: 750,
          margin: '0 auto',
        }}
        data-testid="care-home-topbar"
      >
        <div style={{ position: 'relative', height: 48, width: '100%' }}>
          {/* 1. 左：☰ 三横杠（带小红点 → 历史/侧边栏入口） */}
          <button
            aria-label="历史会话"
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
              color: '#1F2D3D',
            }}
          >
            <span style={{ position: 'relative', display: 'inline-block', width: 21, height: 17 }}>
              <svg width={21} height={17} viewBox="0 0 21 17" aria-hidden="true">
                <rect x={0} y={0} width={16} height={2.5} rx={1.25} fill="currentColor" />
                <rect x={0} y={7} width={16} height={2.5} rx={1.25} fill="currentColor" />
                <rect x={0} y={14} width={11} height={2.5} rx={1.25} fill="currentColor" />
              </svg>
              <span
                data-testid="care-home-hamburger-reddot"
                aria-hidden="true"
                style={{
                  position: 'absolute',
                  left: 16,
                  top: -8,
                  width: 8,
                  height: 8,
                  borderRadius: 9999,
                  background: '#FF3B30',
                  pointerEvents: 'none',
                }}
              />
            </span>
          </button>

          {/* 2~4. 中：档案 / 咨询 / 服务 三 Tab（当前停「咨询」，选中蓝色下划线） */}
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
              gap: 22,
              minWidth: 0,
              maxWidth: 'calc(100% - 120px)',
            }}
            data-testid="care-home-top-tabs"
            role="tablist"
          >
            {([
              { key: 'profile', label: '档案' },
              { key: 'consult', label: '咨询' },
              { key: 'service', label: '服务' },
            ] as const).map((tab) => {
              const active = tab.key === 'consult';
              return (
                <button
                  key={tab.key}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  data-testid={`care-home-top-tab-${tab.key}`}
                  onClick={() => {
                    if (tab.key === 'profile') { navigate('/health-profile'); return; }
                    if (tab.key === 'service') { navigate('/services'); return; }
                    // 咨询：停留当前页（关怀版咨询首页）
                  }}
                  style={{
                    position: 'relative',
                    background: 'transparent',
                    border: 'none',
                    padding: '0 2px',
                    height: '100%',
                    minHeight: 44,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    lineHeight: 1,
                  }}
                >
                  <span
                    style={{
                      fontSize: 16,
                      fontWeight: active ? 700 : 500,
                      color: active ? '#3FA9F5' : '#6B7B8C',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {tab.label}
                  </span>
                  <span
                    aria-hidden="true"
                    style={{
                      position: 'absolute',
                      bottom: 6,
                      left: '50%',
                      transform: 'translateX(-50%)',
                      width: active ? 20 : 0,
                      height: 3,
                      borderRadius: 2,
                      background: '#3FA9F5',
                    }}
                  />
                </button>
              );
            })}
          </div>

          {/* 5. 🔔 铃铛（带红/橙点 → 待办/消息提醒） */}
          <button
            type="button"
            onClick={() => navigate('/ai-home/medication-reminder')}
            aria-label="今日待办提醒"
            data-testid="care-home-topbar-bell"
            style={{
              position: 'absolute',
              right: 48,
              top: '50%',
              transform: 'translateY(-50%)',
              width: 32,
              height: 32,
              color: '#1F2D3D',
              background: 'transparent',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
            }}
          >
            <span style={{ position: 'relative', display: 'inline-flex', fontSize: 20, lineHeight: 1 }} aria-hidden="true">
              🔔
              <span
                data-testid="care-home-topbar-bell-reddot"
                style={{
                  position: 'absolute',
                  top: -3,
                  right: -3,
                  minWidth: 8,
                  height: 8,
                  borderRadius: 9999,
                  background: '#FF7A45',
                  boxShadow: '0 0 0 1.5px #fff',
                }}
              />
            </span>
          </button>

          {/* 6. ⊕ 加号圈（最右，点开「更多」菜单——统一 8 项） */}
          <button
            aria-label="更多菜单"
            onClick={() => setMoreMenuOpen(true)}
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
              color: '#1F2D3D',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <svg width={22} height={22} viewBox="0 0 22 22" aria-hidden="true" data-testid="care-home-more-icon-plus-circle">
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
          position: 'relative',
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
        {/* [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求3] 欢迎区右上角「模式切换」胶囊（方案1：胶囊带文字）
            - 显示当前模式名「关怀版 ▾」，点击弹下拉：标准版（可切换）/ 关怀版（当前打勾）
            - 与 ⊕菜单里的「切换模式」并存，两个入口同时存在 */}
        <div
          ref={modeDropdownRef}
          style={{ position: 'absolute', right: 16, top: 14, zIndex: 5 }}
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
              background: 'rgba(255,255,255,0.22)',
              color: '#FFFFFF',
              border: '1px solid rgba(255,255,255,0.45)',
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
            <span data-testid="care-home-mode-capsule-label">关怀版</span>
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
              {/* 标准版（切换） */}
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
                <span>标准版</span>
                <span aria-hidden="true" style={{ width: 14 }} />
              </div>
              {/* 关怀版（当前，高亮打勾） */}
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
                <span>关怀版</span>
                <span aria-hidden="true">✓</span>
              </div>
            </div>
          ) : null}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 28, fontWeight: 700, marginBottom: 6 }} data-testid="care-home-greeting">
            {greeting.text} {greeting.icon}
          </div>
          <div style={{ fontSize: 16, opacity: 0.95, marginBottom: 14 }} data-testid="care-home-welcome-text">
            我是宾尼小康，聊聊健康问题吧~
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

      {/* 4. 右下角悬浮 SOS（红圆 + 扩散光圈，点击进入紧急呼叫流程） */}
      <button
        type="button"
        onClick={() => navigate('/care-ai-home/sos')}
        aria-label="紧急呼叫 SOS"
        data-testid="care-home-sos-fab"
        style={{
          position: 'fixed',
          right: 18,
          bottom: 28,
          zIndex: 150,
          width: 64,
          height: 64,
          borderRadius: '50%',
          border: 'none',
          padding: 0,
          cursor: 'pointer',
          background: 'transparent',
        }}
      >
        <span className="care-home-sos-pulse care-home-sos-pulse-1" aria-hidden="true" />
        <span className="care-home-sos-pulse care-home-sos-pulse-2" aria-hidden="true" />
        <span className="care-home-sos-core" aria-hidden="true">SOS</span>
      </button>

      {/* [PRD-AIHOME-UNIFY-V1 2026-06-01 §需求2] 更多菜单与标准版统一为 8 项（ai-home-v2 变体）：
          💬发起新对话 / 🔀切换模式 / 👑会员中心 / 🎁邀请好友 / 📷扫一扫 / 🔤字体大小 / 📤立即分享 / ❓帮助与反馈 */}
      <MoreMenu
        visible={moreMenuOpen}
        onClose={() => setMoreMenuOpen(false)}
        menuVariant="ai-home-v2"
        currentModeLabel="关怀版"
        onNewChat={() => { setMoreMenuOpen(false); navigate('/care-ai-home'); }}
        onSwitchMode={() => { setMoreMenuOpen(false); handleSwitchToStandard(); }}
        onMemberCenter={() => { setMoreMenuOpen(false); navigate('/member-center'); }}
        onInviteFriend={() => { setMoreMenuOpen(false); navigate('/invite'); }}
        onScan={() => { setMoreMenuOpen(false); showToast('扫一扫开发中'); }}
        onFontSize={() => { setMoreMenuOpen(false); showToast('字体大小设置开发中'); }}
        onShare={() => { setMoreMenuOpen(false); showToast('请点击浏览器菜单分享'); }}
        onHelpFeedback={() => { setMoreMenuOpen(false); navigate('/feedback'); }}
      />

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

      <style jsx>{`
        .care-home-sos-core {
          position: absolute;
          left: 0;
          top: 0;
          width: 64px;
          height: 64px;
          border-radius: 50%;
          background: radial-gradient(circle, #ef5350 0%, #e53935 100%);
          color: #fff;
          font-size: 20px;
          font-weight: 800;
          letter-spacing: 1px;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 6px 18px rgba(229, 57, 53, 0.5);
          z-index: 2;
        }
        .care-home-sos-pulse {
          position: absolute;
          left: 0;
          top: 0;
          width: 64px;
          height: 64px;
          border-radius: 50%;
          background: rgba(229, 57, 53, 0.35);
          animation: care-home-sos-spread 2s ease-out infinite;
          z-index: 1;
        }
        .care-home-sos-pulse-2 {
          animation-delay: 1s;
        }
        @keyframes care-home-sos-spread {
          0% {
            transform: scale(1);
            opacity: 0.6;
          }
          100% {
            transform: scale(1.9);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
}
