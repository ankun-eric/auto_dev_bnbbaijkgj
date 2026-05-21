'use client';

// [PRD-MED-PLAN-ENTRY-V1 2026-05-17] 标记为强制动态渲染，跳过静态预渲染；并在 default export 外层补 Suspense 兜底，配合内部 useSearchParams。
export const dynamic = 'force-dynamic';
export const dynamicParams = true;

/**
 * [PRD-健康档案路径统一 2026-05-16] 健康档案 v2 设计搬迁回主路径 /health-profile
 *
 * [PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18] 健康档案页面优化 V1
 *   F1 顶部双层吸顶（标题栏 + 咨询人切换条）
 *   F2 切换咨询人时全页数据一刀切随切换（含用药接口加 consultant_id）
 *   F3 头像右上角"被守护"角标
 *   F4 Hero 卡重构：关系标签放姓名后；移除既往病史/过敏史/家族遗传字段；
 *       第 4 格"在用药品"改为"今日用药 · N ›"主入口
 *   F5 Hero 卡下方新增「共管/守护」区域，三态切换：
 *       本人 = 已守护 N 人 ›  /  非本人未守护 = + 邀请共管  /  非本人已守护 = 管理
 *   F6 漏打卡提醒区域简化为单一入口「打卡提醒设置 ›」
 *   F8 移除顶部右上角设备 Logo
 *   F9 非本人态完全不出现设备入口；TA 的设备走家庭守护列表
 */

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import NewFamilyMemberModal from '@/components/health-profile-v5/NewFamilyMemberModal';
import MemberBadge from '@/components/family/MemberBadge';
import { formatGender } from '@/utils/format';
// [PRD-HEALTH-OPT-V1 2026-05-14 R2] 中部「我的设备」卡片已移除，由顶部右上角设备图标替代
// import DeviceListBlock from '@/components/health-profile-v5/DeviceListBlock';
import HealthInfoBlock from '@/components/health-profile-v5/HealthInfoBlock';
import CareReminderBlock from '@/components/health-profile-v5/CareReminderBlock';
import HealthEventsBlock from '@/components/health-profile-v5/HealthEventsBlock';
import { BH_TOKENS } from '@/lib/health-tokens';
import { parseServerTime } from '@/lib/datetime';

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
  // [BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 顶部成员 Tab 新样式所需字段
  avatar_color_index?: number | null;
  relation_badge_char?: string | null;
  guard_status?: string | null;
}

// [BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 5 色循环底色表（PRD §2.3）
const BADGE_COLOR_PALETTE: { bg: string; fg: string }[] = [
  { bg: '#FFE8D6', fg: '#E66A1F' }, // 0 橙
  { bg: '#E0EFFF', fg: '#1F6FE6' }, // 1 蓝
  { bg: '#E8F7EE', fg: '#1FA168' }, // 2 绿
  { bg: '#EFE4FF', fg: '#7E3FE6' }, // 3 紫
  { bg: '#FFE4EE', fg: '#E63F86' }, // 4 粉
];

// [BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19] 关系字徽前端兜底映射（防后端字段缺失）
const FRONTEND_BADGE_FALLBACK: Record<string, string> = {
  本人: '我', 自己: '我', 我: '我',
  爸爸: '爸', 父亲: '爸', 爸: '爸',
  妈妈: '妈', 母亲: '妈', 妈: '妈',
  儿子: '儿', 女儿: '女',
  老公: '爱', 老婆: '爱', 丈夫: '爱', 妻子: '爱', 伴侣: '爱', 爱人: '爱',
  哥哥: '哥', 弟弟: '弟', 姐姐: '姐', 妹妹: '妹',
  爷爷: '爷', 奶奶: '奶', 外公: '外', 外婆: '外',
};

function resolveBadgeChar(m: FamilyMember): string {
  if (m.relation_badge_char) return m.relation_badge_char;
  const rel = m.is_self
    ? '本人'
    : (m.relationship_type || m.relation_type_name || '');
  if (rel && FRONTEND_BADGE_FALLBACK[rel]) return FRONTEND_BADGE_FALLBACK[rel];
  if (rel) return rel.charAt(0);
  return (m.nickname || '?').charAt(0);
}

function resolveRelationLabel(m: FamilyMember): string {
  if (m.is_self) return '本人';
  return m.relation_type_name || m.relationship_type || '家人';
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
  // [PRD-HEALTH-ARCHIVE-OPTIM-V1] 被守护角标映射 + 已守护 N 人摘要 + 当前选中成员的 managed_user_id
  const [guardedFlags, setGuardedFlags] = useState<Map<number, { guarded: boolean; managed_user_id: number | null }>>(new Map());
  const [guardianSummary, setGuardianSummary] = useState<{ managed_count: number }>({ managed_count: 0 });
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

  // [PRD-HEALTH-ARCHIVE-OPTIM-V1] 把当前选中成员翻译为 consultant_id：本人=0；其它=member.id
  const consultantIdParam = useMemo(() => {
    const m = members.find((x) => x.id === selectedMemberId);
    if (!m) return -1; // 未选中：不过滤
    return m.is_self ? 0 : m.id;
  }, [members, selectedMemberId]);

  // [PRD-MED-PLAN-ENTRY-V1] Hero 第 4 格文案；[PRD-HEALTH-ARCHIVE-OPTIM-V1] 加 consultant_id 联动
  const fetchMedHero = useCallback(async (consultantId: number) => {
    try {
      const res: any = await api.get(`/api/medication-plans/hero-count?consultant_id=${consultantId}`);
      const data = res.data || res;
      setMedHero({ display_text: data.display_text, status: data.status, remaining_today: data.remaining_today });
    } catch {
      setMedHero(null);
    }
  }, []);

  // [PRD-MED-PLAN-ENTRY-V1] 摘要卡：仅服药中；[PRD-HEALTH-ARCHIVE-OPTIM-V1] 加 consultant_id 联动
  const fetchMedSummary = useCallback(async (consultantId: number) => {
    try {
      const res: any = await api.get(`/api/medication-plans/summary?consultant_id=${consultantId}`);
      const data = res.data || res;
      setMedSummary(Array.isArray(data.items) ? data.items : []);
    } catch {
      setMedSummary([]);
    }
  }, []);

  // [PRD-HEALTH-ARCHIVE-OPTIM-V1 F3] 被守护标记
  const fetchGuardedFlags = useCallback(async () => {
    try {
      const res: any = await api.get('/api/health-archive/family-members/guarded-flags');
      const data = res.data || res;
      const map = new Map<number, { guarded: boolean; managed_user_id: number | null }>();
      (data.items || []).forEach((it: any) => {
        map.set(it.member_id, { guarded: !!it.guarded, managed_user_id: it.managed_user_id ?? null });
      });
      setGuardedFlags(map);
    } catch {
      setGuardedFlags(new Map());
    }
  }, []);

  // [PRD-HEALTH-ARCHIVE-OPTIM-V1 F5] 已守护 N 人
  const fetchGuardianSummary = useCallback(async () => {
    try {
      const res: any = await api.get('/api/health-archive/guardian/summary');
      const data = res.data || res;
      setGuardianSummary({ managed_count: data.managed_count || 0 });
    } catch {
      setGuardianSummary({ managed_count: 0 });
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
  useEffect(() => { fetchGuardedFlags(); fetchGuardianSummary(); }, [fetchGuardedFlags, fetchGuardianSummary]);

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
    // [PRD-HEALTH-ARCHIVE-OPTIM-V1 F2] 切换咨询人后，先清空旧数据，避免出现「上一个人数据残影」
    setMedHero(null);
    setMedSummary([]);
    setTodayMetrics(null);
    setMedications([]);
    setHeroMetrics([]);
    // 切换后滚动到顶部
    try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch {}
    const m = members.find((x) => x.id === selectedMemberId);
    const cid = m ? (m.is_self ? 0 : m.id) : -1;
    (async () => {
      const profileId = await fetchProfile(selectedMemberId);
      if (profileId != null) {
        await Promise.all([
          fetchTodayMetrics(profileId),
          fetchMedication(profileId),
          fetchLinkStatus(selectedMemberId),
          fetchHeroSummary(profileId),
          fetchMedHero(cid),
          fetchMedSummary(cid),
        ]);
      }
    })();
  }, [selectedMemberId, members, fetchProfile, fetchTodayMetrics, fetchMedication, fetchLinkStatus, fetchHeroSummary, fetchMedHero, fetchMedSummary]);

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

  // ─── 成员条 V2（按"健康档案页 · 顶部成员 Tab V2" Bug 修复方案 §2.4 重写）──────
  // [BUGFIX-HEALTH-ARCHIVE-MEMBER-TAB-V2 2026-05-19]
  // 1) 选中态：橙底 #FF8A3D + 白字；未选中：浅蓝灰 #EAF2FF 整块底 + 深字
  // 2) 圆形字徽：底色按 avatar_color_index 取 5 色之一，字按 relation_badge_char
  // 3) 两行文字：上=称呼/关系，下=姓名（超长省略号）
  // 4) 末尾灰底深灰加号 + 按钮，点击调起 NewFamilyMemberModal
  const renderMemberBar = () => (
    <div
      data-testid="prd469-member-bar"
      style={{
        background: '#FFFFFF',
        padding: '10px 16px 12px',
        display: 'flex',
        gap: 12,
        overflowX: 'auto',
        alignItems: 'center',
      }}
    >
      {members.map((m, idx) => {
        const active = m.id === selectedMemberId;
        const flag = guardedFlags.get(m.id);
        const guarded = !!flag?.guarded;
        const badgeChar = resolveBadgeChar(m);
        const colorIdx = ((m.avatar_color_index ?? idx) % 5 + 5) % 5;
        const palette = BADGE_COLOR_PALETTE[colorIdx];
        const relationLabel = resolveRelationLabel(m);
        const displayName = m.nickname || (m.is_self ? '本人' : relationLabel);
        return (
          <div
            key={m.id}
            data-testid={`bh-member-tab-${m.id}`}
            onClick={() => setSelectedMemberId(m.id)}
            style={{
              flex: '0 0 auto',
              width: 76,
              height: 96,
              borderRadius: 12,
              background: active ? '#FF8A3D' : '#EAF2FF',
              boxShadow: active ? '0 4px 12px rgba(255,138,61,0.25)' : 'none',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'flex-start',
              padding: '8px 4px 6px',
              cursor: 'pointer',
              position: 'relative',
              transition: 'background 0.18s ease',
            }}
          >
            <div
              style={{
                position: 'relative',
                width: 36,
                height: 36,
                borderRadius: '50%',
                background: palette.bg,
                color: palette.fg,
                fontSize: 18,
                fontWeight: 700,
                lineHeight: '36px',
                textAlign: 'center',
                border: active ? '2px solid #FFFFFF' : 'none',
                boxSizing: 'border-box',
              }}
            >
              {badgeChar}
              {guarded && (
                <span
                  data-testid={`bh-guarded-badge-${m.id}`}
                  style={{
                    position: 'absolute',
                    top: -6,
                    right: -10,
                    background: '#0EA5E9',
                    color: '#fff',
                    fontSize: 9,
                    fontWeight: 600,
                    padding: '1px 5px',
                    borderRadius: 8,
                    boxShadow: '0 1px 4px rgba(0,0,0,0.15)',
                    border: '1px solid #fff',
                    whiteSpace: 'nowrap',
                    lineHeight: 1.2,
                  }}
                >被守护</span>
              )}
            </div>
            <div
              style={{
                marginTop: 6,
                fontSize: 12,
                lineHeight: '16px',
                color: active ? '#FFFFFF' : '#1F2937',
                fontWeight: active ? 600 : 500,
                width: '100%',
                textAlign: 'center',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                padding: '0 4px',
              }}
            >
              {relationLabel}
            </div>
            <div
              style={{
                fontSize: 11,
                lineHeight: '16px',
                color: active ? 'rgba(255,255,255,0.92)' : '#6B7280',
                width: '100%',
                textAlign: 'center',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                padding: '0 4px',
              }}
            >
              {displayName}
            </div>
          </div>
        );
      })}
      <div
        onClick={() => setShowAddMember(true)}
        data-testid="prd469-add-member-btn"
        style={{
          flex: '0 0 auto',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          width: 76,
          height: 96,
          cursor: 'pointer',
        }}
      >
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: '50%',
            background: '#F3F4F6',
            color: '#6B7280',
            fontSize: 24,
            lineHeight: '40px',
            textAlign: 'center',
            fontWeight: 400,
          }}
        >+</div>
        <span style={{ fontSize: 12, color: '#6B7280', marginTop: 6 }}>添加成员</span>
      </div>
    </div>
  );

  // ─── Hero（[PRD-HEALTH-ARCHIVE-OPTIM-V1 F4] 重构：关系标签放姓名后 + 移除三类病史 + 今日用药主入口） ─
  const renderHero = () => {
    if (!profile) return null;
    const age = profile.birthday ? calcAge(profile.birthday) : null;
    const baseLine = [
      profile.gender ? formatGender(profile.gender) : '',
      age != null ? `${age} 岁` : '',
      profile.height ? `${profile.height} cm` : '',
      profile.weight ? `${profile.weight} kg` : '',
      profile.blood_type ? `${profile.blood_type}型` : '',
    ].filter(Boolean).join(' · ') || '未填基础信息';

    const relLabel = selectedMember?.is_self ? '本人' : (selectedMember?.relation_type_name || '家庭成员');
    const memberGuarded = selectedMember ? !!guardedFlags.get(selectedMember.id)?.guarded : false;
    const medText = medHero?.display_text || '今日用药 · 0';

    return (
      <div style={{ padding: '12px 16px' }}>
        <div
          data-testid="prd469-hero-card"
          style={{
            background: T.gradient, color: '#fff', borderRadius: 16, padding: 20,
            boxShadow: T.shadow, position: 'relative',
          }}
        >
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
                position: 'relative',
                width: 64, height: 64, borderRadius: '50%',
                background: 'rgba(255,255,255,0.18)',
                padding: 4,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              {/* [PRD-FAMILY-MEMBER-V2 2026-05-18] Hero 大头像改为字徽方案 */}
              <MemberBadge
                relationName={selectedMember?.relation_type_name || selectedMember?.relationship_type || ''}
                name={selectedMember?.nickname || profile.name}
                isSelf={!!selectedMember?.is_self}
                size={56}
                fontSize={22}
                showPlaceholderTag={false}
              />
              {/* [PRD-HEALTH-ARCHIVE-OPTIM-V1 F3] Hero 大头像也同步显示「被守护」角标 */}
              {memberGuarded && (
                <span
                  data-testid="bh-hero-guarded-badge"
                  style={{
                    position: 'absolute', top: -4, right: -16,
                    background: '#0EA5E9', color: '#fff',
                    fontSize: 11, fontWeight: 600,
                    padding: '2px 8px', borderRadius: 10,
                    boxShadow: '0 1px 4px rgba(0,0,0,0.15)',
                    border: '1px solid #fff',
                  }}
                >被守护</span>
              )}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              {/* [PRD-HEALTH-ARCHIVE-OPTIM-V1 F4-1] 姓名 + 关系标签同行（关系字号约 65%） */}
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 22, fontWeight: 700 }}>{profile.name || '未填'}</span>
                <span
                  data-testid="bh-hero-relation-label"
                  style={{
                    fontSize: 14, fontWeight: 500,
                    padding: '2px 10px', borderRadius: 10,
                    background: 'rgba(255,255,255,0.28)',
                  }}
                >{relLabel}</span>
              </div>
              <div style={{ fontSize: 12, opacity: 0.85 }}>{baseLine}</div>
            </div>
          </div>

          {/* [PRD-HEALTH-ARCHIVE-OPTIM-V1 F4-3] 今日用药入口（替换原四格摘要中的「在用药物」字段，
              既往病史 / 过敏史 / 家族遗传三项不在 Hero 卡上展示） */}
          <div
            data-testid="bh-hero-today-medication"
            onClick={() => router.push('/ai-home/medication-reminder')}
            style={{
              marginTop: 16,
              padding: '12px 16px',
              background: 'rgba(255,255,255,0.18)',
              borderRadius: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              cursor: 'pointer',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 20 }}>💊</span>
              <span style={{ fontSize: 16, fontWeight: 700 }}>{medText}</span>
            </div>
            <span style={{ fontSize: 22, fontWeight: 400 }}>›</span>
          </div>
        </div>
      </div>
    );
  };

  // ─── [PRD-HEALTH-ARCHIVE-OPTIM-V1 F5] 共管区域（Hero 卡正下方，三态切换） ───
  const renderGuardianSection = () => {
    if (!selectedMember) return null;
    const isSelf = !!selectedMember.is_self;
    const flag = guardedFlags.get(selectedMember.id);
    const guarded = !!flag?.guarded;
    const managedUserId = flag?.managed_user_id ?? null;

    // 场景 A：本人 → 已守护 N 人
    if (isSelf) {
      const count = guardianSummary.managed_count || 0;
      return (
        <div style={{ padding: '0 16px 8px' }}>
          <div
            data-testid="bh-guardian-area-self"
            onClick={() => router.push('/family-guardian-list')}
            style={{
              background: '#fff', borderRadius: 12, padding: '14px 16px',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              boxShadow: '0 1px 4px rgba(0,0,0,0.04)', cursor: 'pointer',
              borderLeft: `3px solid ${T.brand500}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 20 }}>👨‍👩‍👧</span>
              <span style={{ fontSize: 15, fontWeight: 600, color: T.brand800 }}>
                {count > 0 ? `已守护 ${count} 人` : '暂未守护任何人，去邀请家人'}
              </span>
            </div>
            <span style={{ fontSize: 18, color: '#9ca3af' }}>›</span>
          </div>
        </div>
      );
    }

    // 场景 B：非本人 + 未守护
    if (!guarded) {
      return (
        <div style={{ padding: '0 16px 8px' }}>
          <button
            data-testid="bh-guardian-area-invite"
            onClick={() => router.push(`/family-invite?member_id=${selectedMember.id}`)}
            style={{
              width: '100%', padding: '12px 16px',
              background: '#0EA5E9', color: '#fff',
              border: 'none', borderRadius: 12,
              fontSize: 15, fontWeight: 600, cursor: 'pointer',
              boxShadow: '0 2px 8px rgba(14,165,233,0.25)',
            }}
          >+ 邀请共管</button>
        </div>
      );
    }

    // 场景 C：非本人 + 已守护
    return (
      <div style={{ padding: '0 16px 8px' }}>
        <button
          data-testid="bh-guardian-area-manage"
          onClick={() => {
            const url = managedUserId
              ? `/family-guardian-list/${managedUserId}`
              : '/family-guardian-list';
            router.push(url);
          }}
          style={{
            width: '100%', padding: '12px 16px',
            background: '#fff', color: T.brand700,
            border: `1px solid ${T.brand400}`, borderRadius: 12,
            fontSize: 15, fontWeight: 600, cursor: 'pointer',
          }}
        >🔧 管理</button>
      </div>
    );
  };

  // ─── [PRD-HEALTH-ARCHIVE-OPTIM-V1 F6] 打卡提醒设置入口（替代原漏打卡区域） ───
  const renderReminderEntry = () => {
    if (!selectedMember) return null;
    const isSelf = !!selectedMember.is_self;
    const flag = guardedFlags.get(selectedMember.id);
    const guarded = !!flag?.guarded;
    const managedUserId = flag?.managed_user_id ?? null;

    // 非本人 + 未守护 → 隐藏入口
    if (!isSelf && !guarded) return null;

    const href = isSelf
      ? '/family-guardian-list?reminder=self'
      : (managedUserId != null ? `/family-guardian-list/${managedUserId}` : '/family-guardian-list');

    return (
      <div style={{ padding: '0 16px 12px' }}>
        <div
          data-testid="bh-reminder-entry"
          onClick={() => router.push(href)}
          style={{
            background: '#fff', borderRadius: 12, padding: '12px 16px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)', cursor: 'pointer',
          }}
        >
          <span style={{ fontSize: 14, color: T.brand800 }}>🔔 打卡提醒设置</span>
          <span style={{ fontSize: 18, color: '#9ca3af' }}>›</span>
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

  // [PRD-HEALTH-ARCHIVE-OPTIM-V1 F8] 顶部右上角设备 Logo 已下线，函数保留为 no-op 仅作占位防止外部引用。
  const renderTopDeviceEntry = () => null;

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
      {/* [PRD-HEALTH-ARCHIVE-OPTIM-V1 F1] 顶部标题栏 + 咨询人切换条整体吸顶 */}
      <div
        data-testid="bh-sticky-top"
        style={{
          position: 'sticky', top: 0, zIndex: 60,
          background: T.brand50,
          boxShadow: '0 1px 6px rgba(0,0,0,0.05)',
        }}
      >
        <GreenNavBar>健康档案</GreenNavBar>
        {renderMemberBar()}
      </div>

      {renderHero()}
      {/* [PRD-HEALTH-ARCHIVE-V5-20260521] 预警横幅 + 4 卡片 + 就医资料 */}
      <HealthArchiveV5Inject
        memberId={selectedMemberId}
        consultantId={consultantIdParam}
        isSelf={!!selectedMember?.is_self}
        router={router}
      />
      {/* {renderGuardianSection()} —— [PRD-HEALTH-ARCHIVE-V5 F06/F07] 区域已移除 */}

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

      {/* [PRD-HEALTH-ARCHIVE-V5-20260521 F08] 「打开提醒设置」入口移除：统一在「家庭成员→提醒设置」管理 */}
      {/* {renderReminderEntry()} */}

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
    const b = parseServerTime(birthday);
    if (!b) return null;
    const now = new Date();
    let age = now.getFullYear() - b.getFullYear();
    const m = now.getMonth() - b.getMonth();
    if (m < 0 || (m === 0 && now.getDate() < b.getDate())) age--;
    return age;
  } catch {
    return null;
  }
}

// [PRD-HEALTH-ARCHIVE-OPTIM-V2 2026-05-18] Hero 卡底部三入口快捷区
function HeroQuickEntriesV2({ memberId, router }: { memberId: number | null; router: any }) {
  const [counts, setCounts] = useState<{ medication_today_count: number; device_count: number; family_member_count: number }>({
    medication_today_count: 0,
    device_count: 0,
    family_member_count: 0,
  });
  useEffect(() => {
    (async () => {
      try {
        const url = memberId != null ? `/api/family-archive-v2/hero-counts?member_id=${memberId}` : '/api/family-archive-v2/hero-counts';
        const r: any = await api.get(url);
        const d = r.data || r;
        setCounts({
          medication_today_count: Number(d.medication_today_count || 0),
          device_count: Number(d.device_count || 0),
          family_member_count: Number(d.family_member_count || 0),
        });
      } catch {
        // ignore
      }
    })();
  }, [memberId]);

  const entry = (icon: string, label: string, count: number, onClick: () => void, testid: string) => (
    <div
      data-testid={testid}
      onClick={onClick}
      style={{
        flex: 1,
        background: '#fff',
        borderRadius: 10,
        padding: '12px 8px',
        position: 'relative',
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        textAlign: 'center',
      }}
    >
      <div style={{ fontSize: 22 }}>{icon}</div>
      <div style={{ marginTop: 4, fontSize: 13, color: '#444', fontWeight: 600 }}>{label}</div>
      {count > 0 && (
        <span
          style={{
            position: 'absolute',
            top: 6,
            right: 8,
            background: '#FF6B1F',
            color: '#fff',
            fontSize: 11,
            borderRadius: 9,
            padding: '0 6px',
            minWidth: 18,
            height: 18,
            lineHeight: '18px',
            textAlign: 'center',
            fontWeight: 600,
          }}
        >
          {count}
        </span>
      )}
    </div>
  );

  return (
    <div data-testid="hero-quick-entries-v2" style={{ padding: '0 16px', marginTop: 10 }}>
      <div style={{ display: 'flex', gap: 10 }}>
        {entry('💊', '今日用药', counts.medication_today_count, () => router.push('/medication-plan/today'), 'qe-medication')}
        {entry('🩺', '我的设备', counts.device_count, () => router.push('/devices'), 'qe-devices')}
        {entry('👨‍👩‍👧', '家庭成员', counts.family_member_count, () => router.push('/family'), 'qe-family')}
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────
// [PRD-HEALTH-ARCHIVE-V5-20260521] 4 卡片 + 预警横幅 + 就医资料 注入区
// ────────────────────────────────────────────────────────────
const V5_CARD_COLORS = {
  alerts: '#FF6B35',       // 健康预警 橙红
  medication: '#3B82F6',   // 用药计划 蓝
  family: '#10B981',       // 家庭成员 绿
  devices: '#8B5CF6',      // 我的设备 紫
};

const V5_RECORD_CATS = [
  { key: 'case_note', label: '病例单', emoji: '📋', color: '#3B82F6' },
  { key: 'checkup_report', label: '体检报告', emoji: '🔬', color: '#10B981' },
  { key: 'drug', label: '药物', emoji: '💊', color: '#8B5CF6' },
  { key: 'other', label: '其他', emoji: '📦', color: '#6B7280' },
] as const;

function HealthArchiveV5Inject({
  memberId,
  consultantId,
  isSelf,
  router,
}: {
  memberId: number | null;
  consultantId: number;
  isSelf: boolean;
  router: any;
}) {
  const [overview, setOverview] = useState<{
    alerts_unresolved: number;
    medication_plan_count: number;
    family_member_count: number;
    device_count: number;
    medical_records_by_category: Record<string, number>;
    trash_count: number;
    show_alert_banner: boolean;
    banner_text: string;
  }>({
    alerts_unresolved: 0,
    medication_plan_count: 0,
    family_member_count: 0,
    device_count: 0,
    medical_records_by_category: { case_note: 0, checkup_report: 0, drug: 0, other: 0 },
    trash_count: 0,
    show_alert_banner: false,
    banner_text: '',
  });

  const reload = useCallback(async () => {
    try {
      const mid = consultantId > 0 ? consultantId : (memberId ?? 0);
      const url = mid > 0 ? `/api/health-archive-v5/overview?member_id=${mid}` : '/api/health-archive-v5/overview';
      const res: any = await api.get(url);
      const d = res?.data || res || {};
      setOverview({
        alerts_unresolved: Number(d.alerts_unresolved || 0),
        medication_plan_count: Number(d.medication_plan_count || 0),
        family_member_count: Number(d.family_member_count || 0),
        device_count: Number(d.device_count || 0),
        medical_records_by_category: d.medical_records_by_category || { case_note: 0, checkup_report: 0, drug: 0, other: 0 },
        trash_count: Number(d.trash_count || 0),
        show_alert_banner: !!d.show_alert_banner,
        banner_text: String(d.banner_text || ''),
      });
    } catch {
      // 静默兜底
    }
  }, [consultantId, memberId]);

  useEffect(() => { reload(); }, [reload]);

  const memberQs = memberId && memberId > 0 ? `?member_id=${memberId}` : '';

  const card = (label: string, count: number, color: string, onClick: () => void, locked = false) => (
    <div
      onClick={onClick}
      style={{
        flex: 1, background: '#fff', borderRadius: 12, padding: '14px 8px',
        textAlign: 'center', cursor: 'pointer', position: 'relative',
        borderTop: `3px solid ${color}`,
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
      }}
    >
      {locked && (
        <span style={{ position: 'absolute', top: 4, right: 6, fontSize: 12 }}>🔒</span>
      )}
      <div style={{ color, fontSize: 22, fontWeight: 700, lineHeight: 1.1 }}>{count}</div>
      <div style={{ fontSize: 12, color: '#374151', marginTop: 4 }}>{label}</div>
    </div>
  );

  return (
    <div style={{ padding: '12px 16px 0' }}>
      {/* F11 预警横幅 */}
      {overview.show_alert_banner && (
        <div
          onClick={() => router.push(`/health-alerts${memberQs}`)}
          style={{
            background: 'linear-gradient(90deg, #FF6B35 0%, #F97316 100%)',
            color: '#fff', borderRadius: 10, padding: '10px 14px',
            marginBottom: 12, display: 'flex', alignItems: 'center',
            fontSize: 14, cursor: 'pointer',
          }}
        >
          <span style={{ marginRight: 8, fontSize: 18 }}>⚠️</span>
          <span style={{ flex: 1, fontWeight: 500 }}>{overview.banner_text}</span>
          <span style={{ marginLeft: 8 }}>›</span>
        </div>
      )}

      {/* F04 4 卡片 */}
      <div style={{ display: 'flex', gap: 10 }}>
        {card('健康预警', overview.alerts_unresolved, V5_CARD_COLORS.alerts, () => router.push(`/health-alerts${memberQs}`))}
        {card('用药计划', overview.medication_plan_count, V5_CARD_COLORS.medication, () => router.push('/ai-home/medication-plans'))}
        {card('家庭成员', overview.family_member_count, V5_CARD_COLORS.family, () => router.push('/family'), !isSelf)}
        {card('我的设备', overview.device_count, V5_CARD_COLORS.devices, () => router.push('/devices'), !isSelf)}
      </div>

      {/* F18-F23 就医资料 4 分组 */}
      <div style={{ marginTop: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ fontWeight: 600, color: '#111827', flex: 1 }}>就医资料</span>
          <button
            onClick={() => router.push(`/medical-records${memberQs}`)}
            style={{ background: '#10B981', color: '#fff', border: 'none', borderRadius: 6, padding: '4px 12px', fontSize: 12 }}
          >+ 上传</button>
        </div>
        <div style={{ background: '#fff', borderRadius: 12, padding: 4 }}>
          {V5_RECORD_CATS.map((c) => (
            <div
              key={c.key}
              onClick={() => router.push(`/medical-records${memberQs}`)}
              style={{
                display: 'flex', alignItems: 'center', padding: '12px 12px',
                borderBottom: '1px solid #F3F4F6', cursor: 'pointer',
              }}
            >
              <span style={{ fontSize: 18, marginRight: 8 }}>{c.emoji}</span>
              <span style={{ flex: 1, color: '#374151' }}>{c.label}</span>
              <span style={{ color: c.color, fontWeight: 600, marginRight: 6 }}>
                {overview.medical_records_by_category?.[c.key] || 0}
              </span>
              <span style={{ color: '#9CA3AF' }}>›</span>
            </div>
          ))}
          <div
            onClick={() => router.push(`/medical-records/trash${memberQs}`)}
            style={{ display: 'flex', alignItems: 'center', padding: '12px 12px', cursor: 'pointer' }}
          >
            <span style={{ fontSize: 18, marginRight: 8 }}>🗑️</span>
            <span style={{ flex: 1, color: '#6B7280' }}>回收站</span>
            {overview.trash_count > 0 && (
              <span style={{ color: '#9CA3AF', fontSize: 12, marginRight: 6 }}>
                {overview.trash_count} 项
              </span>
            )}
            <span style={{ color: '#9CA3AF' }}>›</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// [PRD-MED-PLAN-ENTRY-V1 2026-05-17] 外层 Suspense 包裹，配合内部 useSearchParams 通过 Next.js 静态预渲染检查
export default function HealthProfileV2Page() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>加载中…</div>}>
      <HealthProfileV2PageInner />
    </Suspense>
  );
}
