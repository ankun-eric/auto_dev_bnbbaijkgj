'use client';

// [PRD-MED-PLAN-ENTRY-V1 2026-05-17] 标记为强制动态渲染，跳过静态预渲染；并在 default export 外层补 Suspense 兜底，配合内部 useSearchParams。
export const dynamic = 'force-dynamic';
export const dynamicParams = true;

/**
 * [PRD-健康档案路径统一 2026-05-16] 健康档案 v2 设计搬迁回主路径 /health-profile
 *
 * 历史：PRD-469（2026-05-12）曾把新版部署到 /health-profile-v2，旧 /health-profile 改为 404。
 * 现状：v2 设计稳定，按本 PRD 将 v2 内容搬回 /health-profile，并彻底删除 /health-profile-v2。
 *
 * 信息架构：
 *   家庭成员条（"+"按钮）→ Hero 卡 → 粘性 5 Tab（滚动联动）
 *     Tab 1 今日数据 6 宫格
 *     Tab 2 健康信息（既往病史 / 过敏史 / 家族病史 / 个人习惯）
 *     Tab 3 用药计划
 *     Tab 4 共管与提醒
 *     Tab 5 健康事件
 *
 * 视觉规范：v5 健康绿主色 + 圆角 12/16px + 病历卡左侧 3px 竖线
 */

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import NewFamilyMemberModal from '@/components/health-profile-v5/NewFamilyMemberModal';
import { formatGender } from '@/utils/format';
// [PRD-HEALTH-OPT-V1 2026-05-14 R2] 中部「我的设备」卡片已移除，由顶部右上角设备图标替代
// import DeviceListBlock from '@/components/health-profile-v5/DeviceListBlock';
import HealthInfoBlock from '@/components/health-profile-v5/HealthInfoBlock';
import CareReminderBlock from '@/components/health-profile-v5/CareReminderBlock';
import HealthEventsBlock from '@/components/health-profile-v5/HealthEventsBlock';
import { BH_TOKENS } from '@/lib/health-tokens';

// ─── [PRD-HEALTH-OPT-V1 2026-05-14 R1] 设计 Token：蓝白渐变 + 大圆角 ───
const T = {
  brand50: BH_TOKENS.brand50,
  brand100: BH_TOKENS.brand100,
  brand200: BH_TOKENS.brand200,
  brand300: BH_TOKENS.brand300,
  brand400: BH_TOKENS.brand400,
  brand500: BH_TOKENS.brand500,
  brand600: BH_TOKENS.brand600,
  brand700: BH_TOKENS.brand700,
  brand800: BH_TOKENS.brand800,
  yellow: BH_TOKENS.yellow,
  warn: BH_TOKENS.warn,
  textPrimary: BH_TOKENS.textPrimary,
  textSecondary: BH_TOKENS.textSecondary,
  cardLineGreen: BH_TOKENS.cardLineGreen,
  cardLineYellow: BH_TOKENS.cardLineYellow,
  shadow: BH_TOKENS.shadow,
  gradient: BH_TOKENS.gradient,
};

const TAB_LIST = [
  { id: 'today-data', label: '今日数据' },
  { id: 'health-info', label: '健康信息' },
  { id: 'medication-plan', label: '用药计划' },
  { id: 'care-reminder', label: '共管与提醒' },
  { id: 'health-events', label: '健康事件' },
];

interface FamilyMember {
  id: number;
  user_id: number;
  is_self: boolean;
  nickname: string;
  relationship_type?: string;
  relation_type_name?: string;
  birthday?: string;
  gender?: string;
  height?: number;
  weight?: number;
  member_user_id?: number | null;
}

interface HealthProfileBasic {
  id: number;
  name?: string;
  gender?: string;
  birthday?: string;
  height?: number | null;
  weight?: number | null;
  blood_type?: string;
}

interface MetricSnapshot {
  metric_type: string;
  value: Record<string, any> | null;
  measured_at: string | null;
  source: string | null;
  is_abnormal: boolean;
}

interface TodayMetricsResponse {
  profile_id: number;
  blood_pressure: MetricSnapshot;
  blood_glucose: MetricSnapshot;
  heart_rate: MetricSnapshot;
  sleep: MetricSnapshot;
  spo2: MetricSnapshot;
  medication: { checked: number; total: number; has_overdue: boolean };
}

interface MedicationPlanCard {
  plan_id: number;
  drug_name: string;
  dosage?: string;
  schedule: string[];
  time_chips: { scheduled_time: string; checked: boolean }[];
  weekly_completed: number;
  weekly_total: number;
  weekly_rate: number;
}

interface HeroMetric {
  label: string;
  count: number;
  unit: string;
}

// ─── 病历卡组件（v5 风格） ─────────────────────────────────────────────────
export function V5Card({
  children,
  abnormal = false,
  onClick,
  testid,
  style,
}: {
  children: React.ReactNode;
  abnormal?: boolean;
  onClick?: () => void;
  testid?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      data-testid={testid}
      onClick={onClick}
      style={{
        background: '#FFFFFF',
        borderLeft: abnormal ? T.cardLineYellow : T.cardLineGreen,
        borderRadius: BH_TOKENS.cardRadius,
        padding: 16,
        boxShadow: BH_TOKENS.cardShadow,
        cursor: onClick ? 'pointer' : 'default',
        position: 'relative',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export const HP_V5_TOKEN = T;

function HealthProfileV2PageInner() {
  const router = useRouter();

  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);
  const [profile, setProfile] = useState<HealthProfileBasic | null>(null);
  const [todayMetrics, setTodayMetrics] = useState<TodayMetricsResponse | null>(null);
  const [medications, setMedications] = useState<MedicationPlanCard[]>([]);
  const [activeTab, setActiveTab] = useState<string>('today-data');
  const isScrollingRef = useRef(false);
  const [isLinked, setIsLinked] = useState(false);
  const [showAddMember, setShowAddMember] = useState(false);
  const [heroMetrics, setHeroMetrics] = useState<HeroMetric[]>([]);
  // [PRD-469 v2 P0 M4] 用药计划 Tab 双分段切换
  const [medSegment, setMedSegment] = useState<'today' | 'all'>('today');
  const [showHeroEdit, setShowHeroEdit] = useState(false);
  const [heroEditDraft, setHeroEditDraft] = useState<HealthProfileBasic | null>(null);
  // [PRD-MED-PLAN-ENTRY-V1 2026-05-17] 用药入口 Hero 文案 + 摘要卡数据
  const [medHero, setMedHero] = useState<{ display_text: string; status: string; remaining_today: number } | null>(null);
  const [medSummary, setMedSummary] = useState<Array<{ id: number; name: string; dosage: string; frequency_text: string; timing_text: string; status_text: string }>>([]);
  const searchParams = useSearchParams();

  const fetchMembers = useCallback(async () => {
    try {
      const res: any = await api.get('/api/family/members');
      const data = res.data || res;
      const items: FamilyMember[] = Array.isArray(data.items) ? data.items : [];
      setMembers(items);
      if (items.length > 0 && selectedMemberId == null) {
        const self = items.find((m) => m.is_self) || items[0];
        setSelectedMemberId(self.id);
      }
    } catch {
      setMembers([]);
    }
  }, [selectedMemberId]);

  const fetchProfile = useCallback(async (memberId: number) => {
    try {
      const res: any = await api.get(`/api/health/profile/member/${memberId}`);
      const data = res.data || res;
      setProfile(data);
      return data?.id as number | undefined;
    } catch {
      setProfile(null);
      return undefined;
    }
  }, []);

  const fetchTodayMetrics = useCallback(async (profileId: number) => {
    try {
      const res: any = await api.get(`/api/health-profile-v3/${profileId}/today-metrics`);
      const data = res.data || res;
      setTodayMetrics(data);
    } catch {
      setTodayMetrics(null);
    }
  }, []);

  const fetchMedication = useCallback(async (profileId: number) => {
    try {
      const res: any = await api.get(`/api/health-profile-v3/${profileId}/medication-plan`);
      const data = res.data || res;
      setMedications(Array.isArray(data.items) ? data.items : []);
    } catch {
      setMedications([]);
    }
  }, []);

  // [PRD-MED-PLAN-ENTRY-V1] Hero 第 4 格文案
  const fetchMedHero = useCallback(async () => {
    try {
      const res: any = await api.get('/api/medication-plans/hero-count');
      const data = res.data || res;
      setMedHero({ display_text: data.display_text, status: data.status, remaining_today: data.remaining_today });
    } catch {
      setMedHero(null);
    }
  }, []);

  // [PRD-MED-PLAN-ENTRY-V1] 摘要卡：仅服药中
  const fetchMedSummary = useCallback(async () => {
    try {
      const res: any = await api.get('/api/medication-plans/summary');
      const data = res.data || res;
      setMedSummary(Array.isArray(data.items) ? data.items : []);
    } catch {
      setMedSummary([]);
    }
  }, []);

  const fetchHeroSummary = useCallback(async (profileId: number) => {
    try {
      const res: any = await api.get(`/api/prd469/summary/${profileId}`);
      const data = res.data || res;
      setHeroMetrics(Array.isArray(data.hero_metrics) ? data.hero_metrics : []);
    } catch {
      setHeroMetrics([]);
    }
  }, []);

  const fetchLinkStatus = useCallback(async (memberId: number) => {
    try {
      const res: any = await api.get('/api/family/management');
      const data = res.data || res;
      const items = Array.isArray(data.items) ? data.items : [];
      setIsLinked(items.some((it: any) => it.managed_member_id === memberId && it.status === 'active'));
    } catch {
      setIsLinked(false);
    }
  }, []);

  useEffect(() => { fetchMembers(); }, [fetchMembers]);

  // [PRD-MED-PLAN-ENTRY-V1] ?focus=medication 自动滚动定位
  useEffect(() => {
    const f = searchParams?.get('focus');
    if (f === 'medication') {
      setTimeout(() => {
        const el = document.getElementById('medication-plan');
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 300);
    }
  }, [searchParams, medSummary.length]);

  useEffect(() => {
    if (selectedMemberId == null) return;
    (async () => {
      const profileId = await fetchProfile(selectedMemberId);
      if (profileId != null) {
        await Promise.all([
          fetchTodayMetrics(profileId),
          fetchMedication(profileId),
          fetchLinkStatus(selectedMemberId),
          fetchHeroSummary(profileId),
          fetchMedHero(),
          fetchMedSummary(),
        ]);
      }
    })();
  }, [selectedMemberId, fetchProfile, fetchTodayMetrics, fetchMedication, fetchLinkStatus, fetchHeroSummary]);

  // [PRD-469 M5] 修复：从添加用药页返回时，强制刷新用药计划
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        const flag = sessionStorage.getItem('medication_changed');
        if (flag && profile?.id != null) {
          sessionStorage.removeItem('medication_changed');
          fetchMedication(profile.id);
        }
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', onVisible);
    // 挂载时也检测一次
    onVisible();
    return () => {
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', onVisible);
    };
  }, [profile?.id, fetchMedication]);

  // 滚动联动 Tab
  useEffect(() => {
    const onScroll = () => {
      if (isScrollingRef.current) return;
      const trigger = window.innerHeight / 3 + 60;
      for (const tab of TAB_LIST) {
        const el = document.getElementById(tab.id);
        if (!el) continue;
        const rect = el.getBoundingClientRect();
        if (rect.top <= trigger && rect.bottom >= trigger) {
          setActiveTab(tab.id);
          break;
        }
      }
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleTabClick = useCallback((id: string) => {
    setActiveTab(id);
    isScrollingRef.current = true;
    const el = document.getElementById(id);
    if (el) {
      const top = el.getBoundingClientRect().top + window.scrollY - 100;
      window.scrollTo({ top, behavior: 'smooth' });
    }
    setTimeout(() => { isScrollingRef.current = false; }, 800);
  }, []);

  const selectedMember = useMemo(
    () => members.find((m) => m.id === selectedMemberId) || null,
    [members, selectedMemberId]
  );

  // ─── 成员条（头像化 + "+" 添加按钮）─────────────────────────────────
  const renderMemberBar = () => (
    <div
      data-testid="prd469-member-bar"
      style={{ background: T.brand50, padding: '12px 16px', display: 'flex', gap: 12, overflowX: 'auto' }}
    >
      {members.map((m) => {
        const active = m.id === selectedMemberId;
        const hasLink = !!m.member_user_id;
        const avatar = m.is_self ? '🙂' : relationEmoji(m.relation_type_name || m.relationship_type || '');
        return (
          <div
            key={m.id}
            onClick={() => setSelectedMemberId(m.id)}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              minWidth: 64, cursor: 'pointer', position: 'relative',
            }}
          >
            <div
              style={{
                width: 48, height: 48, borderRadius: '50%',
                background: active ? T.brand500 : '#fff',
                color: active ? '#fff' : T.brand700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 22, fontWeight: 600,
                border: active ? `2px solid ${T.brand600}` : `1px solid ${T.brand200}`,
                boxShadow: active ? '0 4px 12px rgba(34,197,94,0.25)' : 'none',
              }}
            >{avatar}</div>
            {hasLink && (
              <div
                style={{
                  width: 10, height: 10, borderRadius: '50%', background: T.brand500,
                  position: 'absolute', top: 0, right: 6, border: '2px solid #fff',
                }}
              />
            )}
            <span style={{ fontSize: 13, color: T.brand800, marginTop: 4 }}>
              {m.is_self ? '本人' : (m.relation_type_name || m.nickname)}
            </span>
          </div>
        );
      })}
      <div
        onClick={() => setShowAddMember(true)}
        data-testid="prd469-add-member-btn"
        style={{
          minWidth: 64, display: 'flex', flexDirection: 'column',
          alignItems: 'center', cursor: 'pointer',
        }}
      >
        <div
          style={{
            width: 48, height: 48, borderRadius: '50%',
            background: '#fff', border: `2px dashed ${T.brand400}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 24, color: T.brand500,
          }}
        >+</div>
        <span style={{ fontSize: 13, color: T.brand800, marginTop: 4 }}>添加</span>
      </div>
    </div>
  );

  // ─── Hero（v5 设计稿对齐：头像+姓名+四格健康摘要+编辑按钮） ────────────
  const renderHero = () => {
    if (!profile) return null;
    const age = profile.birthday ? calcAge(profile.birthday) : null;
    // 5 行基础信息收纳到副标题，主体改为 4 格健康摘要指标
    const baseLine = [
      profile.gender ? formatGender(profile.gender) : '',
      age != null ? `${age} 岁` : '',
      profile.height ? `${profile.height} cm` : '',
      profile.weight ? `${profile.weight} kg` : '',
      profile.blood_type ? `${profile.blood_type}型` : '',
    ].filter(Boolean).join(' · ') || '未填基础信息';

    const metrics: HeroMetric[] = heroMetrics.length > 0 ? heroMetrics : [
      { label: '既往病史', count: 0, unit: '项' },
      { label: '过敏史', count: 0, unit: '项' },
      { label: '家族遗传', count: 0, unit: '项' },
      { label: '在用药品', count: 0, unit: '种' },
    ];

    return (
      <div style={{ padding: '12px 16px' }}>
        <div
          data-testid="prd469-hero-card"
          style={{
            background: T.gradient, color: '#fff', borderRadius: 16, padding: 20,
            boxShadow: T.shadow, position: 'relative',
          }}
        >
          {/* 编辑基本信息按钮 [PRD-469 v2 P1] */}
          <button
            data-testid="prd469-hero-edit-btn"
            onClick={() => {
              setHeroEditDraft(profile);
              setShowHeroEdit(true);
            }}
            style={{
              position: 'absolute', top: 12, right: 12,
              padding: '4px 10px', borderRadius: 12,
              background: 'rgba(255,255,255,0.25)', color: '#fff',
              border: '1px solid rgba(255,255,255,0.4)',
              fontSize: 12, fontWeight: 500, cursor: 'pointer',
            }}
          >✏️ 编辑</button>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div
              style={{
                width: 64, height: 64, borderRadius: '50%',
                background: 'rgba(255,255,255,0.25)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 32, fontWeight: 700,
              }}
            >
              {selectedMember?.is_self ? '🙂' : relationEmoji(selectedMember?.relation_type_name || '')}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>{profile.name || '未填'}</div>
              <div style={{ fontSize: 13, opacity: 0.9 }}>
                {selectedMember?.is_self ? '本人' : (selectedMember?.relation_type_name || '家庭成员')}
                {isLinked && (
                  <span
                    style={{
                      marginLeft: 8, padding: '2px 8px', borderRadius: 10,
                      background: 'rgba(255,255,255,0.3)', fontSize: 11, fontWeight: 600,
                    }}
                  >✓ 已关联</span>
                )}
              </div>
              <div style={{ fontSize: 12, opacity: 0.75, marginTop: 4 }}>{baseLine}</div>
            </div>
          </div>

          {/* 四格健康摘要指标（设计稿对齐） */}
          <div
            data-testid="prd469-hero-metrics"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginTop: 16 }}
          >
            {metrics.map((m) => {
              // [PRD-MED-PLAN-ENTRY-V1 2026-05-17] 第 4 格「在用药品」升级为主入口：使用新文案规则 + 跳用药提醒页
              const isMed = m.label === '在用药品' || m.label === '长期用药';
              const medText = medHero?.display_text || '今日用药 0';
              return (
                <div
                  key={m.label}
                  data-testid={`prd469-hero-metric-${m.label}`}
                  onClick={isMed ? () => router.push('/ai-home/medication-reminder') : undefined}
                  style={{
                    textAlign: 'center', padding: '10px 4px',
                    background: 'rgba(255,255,255,0.18)', borderRadius: 10,
                    cursor: isMed ? 'pointer' : 'default',
                  }}
                >
                  {isMed ? (
                    <>
                      <div style={{ fontSize: 14, fontWeight: 700, lineHeight: 1.2 }}>{medText}</div>
                      <div style={{ fontSize: 11, opacity: 0.85, marginTop: 2 }}>{m.label}</div>
                    </>
                  ) : (
                    <>
                      <div style={{ fontSize: 20, fontWeight: 700 }}>{m.count}</div>
                      <div style={{ fontSize: 11, opacity: 0.85, marginTop: 2 }}>{m.label}</div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  };

  // ─── Hero 编辑弹层 ─────────────────────────────────────────────────
  const renderHeroEditModal = () => {
    if (!showHeroEdit || !heroEditDraft) return null;
    const saveHero = async () => {
      if (!heroEditDraft || !selectedMemberId) return;
      try {
        await api.put(`/api/health/profile/member/${selectedMemberId}`, {
          name: heroEditDraft.name,
          gender: heroEditDraft.gender,
          birthday: heroEditDraft.birthday,
          height: heroEditDraft.height,
          weight: heroEditDraft.weight,
          blood_type: heroEditDraft.blood_type,
        });
        setProfile(heroEditDraft);
        setShowHeroEdit(false);
        Toast.show({ content: '已保存', icon: 'success' });
        if (selectedMemberId) await fetchProfile(selectedMemberId);
      } catch {
        Toast.show({ content: '保存失败', icon: 'fail' });
      }
    };

    return (
      <div
        data-testid="prd469-hero-edit-modal"
        style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          zIndex: 100, display: 'flex', alignItems: 'flex-end',
        }}
      >
        <div style={{ background: '#fff', width: '100%', borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '14px 16px', borderBottom: `1px solid ${T.brand100}`, display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 17, fontWeight: 700 }}>编辑基本信息</span>
            <span onClick={() => setShowHeroEdit(false)} style={{ fontSize: 22, color: '#9ca3af', cursor: 'pointer' }}>×</span>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
            <HeroEditRow label="姓名" value={heroEditDraft.name || ''}
              onChange={(v) => setHeroEditDraft({ ...heroEditDraft, name: v })} />
            <HeroEditRow label="性别" value={heroEditDraft.gender || ''}
              onChange={(v) => setHeroEditDraft({ ...heroEditDraft, gender: v })}
              options={['男', '女', '其他']} />
            <HeroEditRow label="生日" value={heroEditDraft.birthday || ''}
              onChange={(v) => setHeroEditDraft({ ...heroEditDraft, birthday: v })}
              inputType="date" />
            <HeroEditRow label="身高 (cm)" value={String(heroEditDraft.height ?? '')}
              onChange={(v) => setHeroEditDraft({ ...heroEditDraft, height: v ? Number(v) : null })}
              inputType="number" />
            <HeroEditRow label="体重 (kg)" value={String(heroEditDraft.weight ?? '')}
              onChange={(v) => setHeroEditDraft({ ...heroEditDraft, weight: v ? Number(v) : null })}
              inputType="number" />
            <HeroEditRow label="血型" value={heroEditDraft.blood_type || ''}
              onChange={(v) => setHeroEditDraft({ ...heroEditDraft, blood_type: v })}
              options={['A', 'B', 'AB', 'O', '未知']} />
          </div>
          <div style={{ padding: 16, borderTop: `1px solid ${T.brand100}`, display: 'flex', gap: 12 }}>
            <button onClick={() => setShowHeroEdit(false)}
              style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: '#fff', border: `1px solid ${T.brand200}`, fontSize: 15, fontWeight: 600 }}>取消</button>
            <button onClick={saveHero} data-testid="prd469-hero-save"
              style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: T.brand500, color: '#fff', border: 'none', fontSize: 15, fontWeight: 600 }}>保存</button>
          </div>
        </div>
      </div>
    );
  };

  // ─── [PRD-HEALTH-OPT-V1 R3] 粘性 Tab：吸顶 + 高度 48px + 白底 + 轻微阴影 ─
  const renderStickyTabs = () => (
    <div
      data-testid="prd469-sticky-tabs"
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 50,
        background: '#FFFFFF',
        borderBottom: `1px solid ${T.brand200}`,
        boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
        height: BH_TOKENS.tabHeight,
      }}
    >
      <div style={{ display: 'flex', overflowX: 'auto', height: '100%' }}>
        {TAB_LIST.map((t) => {
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => handleTabClick(t.id)}
              data-testid={`prd469-tab-${t.id}`}
              style={{
                flex: '0 0 auto', padding: '0 16px', height: '100%',
                background: 'none', border: 'none',
                fontSize: 15, fontWeight: active ? 700 : 500,
                color: active ? T.brand600 : T.textSecondary,
                borderBottom: active ? `2px solid ${T.brand600}` : '2px solid transparent',
                cursor: 'pointer',
              }}
            >{t.label}</button>
          );
        })}
      </div>
    </div>
  );

  // ─── [PRD-HEALTH-OPT-V1 R2] 顶部右上角设备图标入口 ─
  const renderTopDeviceEntry = () => (
    <div
      data-testid="bh-top-device-entry"
      onClick={() => router.push('/devices')}
      style={{
        position: 'absolute', top: 12, right: 16,
        width: 36, height: 36, borderRadius: 18,
        background: 'rgba(255,255,255,0.92)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer', zIndex: 5,
        boxShadow: '0 2px 8px rgba(74, 158, 224, 0.15)',
      }}
      title="设备管理"
    >
      <span style={{ fontSize: 18 }}>⌚</span>
    </div>
  );

  // ─── Tab 1：今日数据 6 宫格 ─────────────────────────────────────────
  const renderTodayMetrics = () => {
    const tm = todayMetrics;
    const cells = [
      {
        id: 'blood_pressure',
        label: '血压',
        unit: 'mmHg',
        icon: '💓',
        value: tm?.blood_pressure?.value
          ? `${tm.blood_pressure.value.systolic || '-'}/${tm.blood_pressure.value.diastolic || '-'}`
          : '—',
        abnormal: tm?.blood_pressure?.is_abnormal,
      },
      {
        id: 'blood_glucose',
        label: '血糖',
        unit: 'mmol/L',
        icon: '🩸',
        value: tm?.blood_glucose?.value?.value ?? '—',
        abnormal: tm?.blood_glucose?.is_abnormal,
      },
      {
        id: 'heart_rate',
        label: '心率',
        unit: 'bpm',
        icon: '❤️',
        value: tm?.heart_rate?.value?.value ?? '—',
        abnormal: tm?.heart_rate?.is_abnormal,
      },
      {
        id: 'sleep',
        label: '睡眠',
        unit: 'h',
        icon: '🌙',
        value: tm?.sleep?.value?.duration_h ?? '—',
        abnormal: tm?.sleep?.is_abnormal,
      },
      {
        id: 'spo2',
        label: '血氧',
        unit: '%',
        icon: '🫁',
        value: tm?.spo2?.value?.value ?? '—',
        abnormal: tm?.spo2?.is_abnormal,
      },
    ];

    return (
      <div id="today-data" data-testid="prd469-today-data" style={{ padding: '12px 16px' }}>
        <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: '8px 0 12px' }}>今日数据</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          {cells.map((c) => (
            <V5Card
              key={c.id}
              abnormal={!!c.abnormal}
              testid={`prd469-metric-${c.id}`}
              onClick={() => router.push(`/health-metric/${c.id}?profileId=${profile?.id || ''}`)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <span style={{ fontSize: 13, color: T.textSecondary }}>{c.icon} {c.label}</span>
                {c.abnormal && (
                  <span
                    style={{
                      fontSize: 11, fontWeight: 600, color: '#fff', background: T.yellow,
                      padding: '2px 6px', borderRadius: 6,
                    }}
                  >异常</span>
                )}
              </div>
              <div style={{ marginTop: 8 }}>
                <span style={{ fontSize: 22, fontWeight: 700, color: T.textPrimary }}>{c.value}</span>
                <span style={{ fontSize: 13, color: T.textSecondary, marginLeft: 4 }}>{c.unit}</span>
              </div>
              <div style={{ position: 'absolute', top: 12, right: 12, fontSize: 14, color: T.brand500 }}>›</div>
            </V5Card>
          ))}
          <V5Card
            abnormal={!!tm?.medication?.has_overdue}
            testid="prd469-metric-medication"
            onClick={() => handleTabClick('medication-plan')}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
              <span style={{ fontSize: 13, color: T.textSecondary }}>💊 用药提醒</span>
              {tm?.medication?.has_overdue && (
                <span
                  style={{
                    fontSize: 11, fontWeight: 600, color: '#fff', background: T.yellow,
                    padding: '2px 6px', borderRadius: 6,
                  }}
                >待服</span>
              )}
            </div>
            <div style={{ marginTop: 8 }}>
              <span style={{ fontSize: 22, fontWeight: 700, color: T.textPrimary }}>
                {tm?.medication?.checked ?? 0}/{tm?.medication?.total ?? 0}
              </span>
              <span style={{ fontSize: 13, color: T.textSecondary, marginLeft: 4 }}>已服</span>
            </div>
            <div style={{ height: 6, background: T.brand100, borderRadius: 3, marginTop: 8 }}>
              <div
                style={{
                  width: `${tm?.medication?.total ? (tm.medication.checked / tm.medication.total) * 100 : 0}%`,
                  height: '100%', background: T.brand500, borderRadius: 3,
                }}
              />
            </div>
          </V5Card>
        </div>
      </div>
    );
  };

  // ─── Tab 3：用药计划（[PRD-MED-PLAN-ENTRY-V1] 摘要卡职责）─────────
  const renderMedicationPlan = () => {
    const list = medSummary;
    return (
      <div id="medication-plan" data-testid="prd469-medication-plan" style={{ padding: '12px 16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '8px 0 12px' }}>
          <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: 0 }}>用药计划</h3>
          {list.length > 0 && (
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                data-testid="med-summary-all-btn"
                onClick={() => router.push('/ai-home/medication-plans')}
                style={{
                  padding: '6px 14px', background: '#fff', color: T.brand600,
                  border: `1px solid ${T.brand500}`, borderRadius: 16, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                }}
              >全部</button>
              <button
                data-testid="med-summary-add-btn"
                onClick={() => router.push('/ai-home/medication-plans/new')}
                style={{
                  padding: '6px 14px', background: T.brand500, color: '#fff',
                  border: 'none', borderRadius: 16, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                }}
              >+ 新增</button>
            </div>
          )}
        </div>
        {list.length === 0 ? (
          <V5Card>
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <button
                data-testid="med-summary-empty-btn"
                onClick={() => router.push('/ai-home/medication-plans/new')}
                style={{
                  padding: '12px 24px', background: T.brand500, color: '#fff',
                  border: 'none', borderRadius: 24, fontSize: 15, fontWeight: 600, cursor: 'pointer',
                }}
              >+ 添加第一条用药计划</button>
            </div>
          </V5Card>
        ) : (
          <div
            data-testid="med-summary-list"
            style={{ maxHeight: 'min(480px, 60vh)', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}
          >
            {list.map((m) => (
              <V5Card key={m.id} testid={`med-summary-item-${m.id}`} style={{ cursor: 'default' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 16, fontWeight: 700, color: T.textPrimary }}>💊 {m.name}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#fff', background: T.brand500, padding: '2px 8px', borderRadius: 10 }}>{m.status_text}</span>
                </div>
                <div style={{ fontSize: 13, color: T.textSecondary, marginTop: 6 }}>
                  {m.dosage && <span>{m.dosage} · </span>}
                  <span>{m.frequency_text}</span>
                  {m.timing_text && <span> · {m.timing_text}</span>}
                </div>
              </V5Card>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div style={{ background: BH_TOKENS.bgPage, minHeight: '100vh', paddingBottom: 80, position: 'relative' }}>
      <GreenNavBar>我的健康档案</GreenNavBar>
      {renderTopDeviceEntry()}
      {renderMemberBar()}
      {renderHero()}
      {/* [PRD-HEALTH-OPT-V1 R2] 中部「我的设备」卡片已移除；改由顶部右上角图标进入设备管理页 */}
      {renderStickyTabs()}
      {renderTodayMetrics()}
      <HealthInfoBlock profileId={profile?.id} token={T} />
      {renderMedicationPlan()}
      <CareReminderBlock
        profileId={profile?.id}
        token={T}
        isLinked={isLinked}
        memberId={selectedMember?.id}
        isSelf={!!selectedMember?.is_self}
      />
      <HealthEventsBlock profileId={profile?.id} token={T} />

      {showAddMember && (
        <NewFamilyMemberModal
          onClose={() => setShowAddMember(false)}
          onSuccess={() => {
            setShowAddMember(false);
            fetchMembers();
            Toast.show({ content: '已添加家庭成员', icon: 'success' });
          }}
        />
      )}

      {renderHeroEditModal()}
    </div>
  );
}

function HeroEditRow({
  label, value, onChange, options, inputType,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options?: string[];
  inputType?: string;
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>{label}</div>
      {options ? (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {options.map((o) => (
            <button
              key={o}
              data-testid={`prd469-hero-${label}-${o}`}
              onClick={() => onChange(o)}
              style={{
                padding: '6px 14px', borderRadius: 14,
                background: value === o ? '#22c55e' : '#f3f4f6',
                color: value === o ? '#fff' : '#374151',
                border: 'none', fontSize: 13, cursor: 'pointer',
              }}
            >{o}</button>
          ))}
        </div>
      ) : (
        <input
          type={inputType || 'text'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          data-testid={`prd469-hero-input-${label}`}
          style={{
            width: '100%', padding: '10px 12px', borderRadius: 8,
            border: '1px solid #d1d5db', fontSize: 14, boxSizing: 'border-box',
          }}
        />
      )}
    </div>
  );
}

// ──────────── 辅助：关系 emoji 映射 ─────────────────────────────────
function relationEmoji(name: string): string {
  const map: Record<string, string> = {
    '本人': '🙂', '爸爸': '👨', '妈妈': '👩',
    '老公': '🤵', '老婆': '👰', '儿子': '👦', '女儿': '👧',
    '哥哥': '🧑', '弟弟': '👨', '姐姐': '👩', '妹妹': '👧',
    '爷爷': '👴', '奶奶': '👵', '外公': '👴', '外婆': '👵',
    '其他': '🧑',
  };
  return map[name] || '🧑';
}

function calcAge(birthday: string): number | null {
  try {
    const b = new Date(birthday);
    if (Number.isNaN(b.getTime())) return null;
    const now = new Date();
    let age = now.getFullYear() - b.getFullYear();
    const m = now.getMonth() - b.getMonth();
    if (m < 0 || (m === 0 && now.getDate() < b.getDate())) age--;
    return age;
  } catch {
    return null;
  }
}

// [PRD-MED-PLAN-ENTRY-V1 2026-05-17] 外层 Suspense 包裹，配合内部 useSearchParams 通过 Next.js 静态预渲染检查
export default function HealthProfileV2Page() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>加载中…</div>}>
      <HealthProfileV2PageInner />
    </Suspense>
  );
}
