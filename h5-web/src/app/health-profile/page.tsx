'use client';

export const dynamic = 'force-dynamic';
export const dynamicParams = true;

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import NewFamilyMemberModal from '@/components/health-profile-v5/NewFamilyMemberModal';
// [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 本人资料完善弹窗 + 抽屉
import CompleteSelfProfileDrawer from '@/components/health-profile-v5/CompleteSelfProfileDrawer';

// [BUG_FIX 2026-05-29] 会话级 / 24h 软抑制 keys —— 替代 useRef 实现"本会话只弹一次 + 24h snooze"
const SELF_COMPLETE_DIALOG_SHOWN_KEY = 'self_complete_dialog_shown_v1';
const SELF_COMPLETE_DIALOG_SNOOZE_UNTIL_KEY = 'self_complete_dialog_snooze_until';
import MemberBadge from '@/components/family/MemberBadge';
import { formatGender } from '@/utils/format';
import { BH_TOKENS } from '@/lib/health-tokens';
import { RELATION_DEFS } from '@/lib/family-relation';
import { parseServerTime } from '@/lib/datetime';

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

// ─── Interfaces ───────────────────────────────────────────────────

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
  avatar_color_index?: number | null;
  relation_badge_char?: string | null;
  guard_status?: string | null;
  // [BUG-FIX-INVITE-NULL-MEMBER 2026-05-25] 后端注入：该成员若已有 pending 邀请则返回此对象
  pending_invitation?: {
    invite_code: string;
    expires_at: string;
    remaining_hours: number;
  } | null;
}

const BADGE_COLOR_PALETTE: { bg: string; fg: string }[] = [
  { bg: '#FFE8D6', fg: '#E66A1F' },
  { bg: '#E0EFFF', fg: '#1F6FE6' },
  { bg: '#E8F7EE', fg: '#1FA168' },
  { bg: '#EFE4FF', fg: '#7E3FE6' },
  { bg: '#FFE4EE', fg: '#E63F86' },
];

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

interface HealthInfo {
  chronic_diseases: Array<{ name: string; year?: string }>;
  surgery_history: Array<{ name: string; time?: string; note?: string }>;
  drug_allergies: string[];
  food_allergies: string[];
  other_allergies: string[];
  family_history: Array<{ relation: string; disease: string; note?: string }>;
  habit_smoking?: string;
  habit_drinking?: string;
  habit_exercise?: string;
  habit_diet?: string;
}

// ─── Shared Components ────────────────────────────────────────────

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

function CircleProgress({ percent, size = 48 }: { percent: number; size?: number }) {
  const r = (size - 6) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - percent / 100);
  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth={5} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#fff" strokeWidth={5}
        strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" />
    </svg>
  );
}

const CHRONIC_PRESETS = ['高血压', '糖尿病', '高血脂', '冠心病', '脑卒中', '慢阻肺', '哮喘', '慢性肾病', '甲状腺', '痛风'];
const FAMILY_RELATIONS = ['爸爸', '妈妈', '爷爷', '奶奶', '外公', '外婆', '兄弟', '姐妹', '其他'];

const V5_RECORD_CATS = [
  { key: 'case_note', label: '病例单', emoji: '📋', color: '#3B82F6' },
  { key: 'checkup_report', label: '体检报告', emoji: '🔬', color: '#10B981' },
  { key: 'drug', label: '药物', emoji: '💊', color: '#8B5CF6' },
  { key: 'other', label: '其他', emoji: '📦', color: '#6B7280' },
] as const;

// ─── Main Page Inner ──────────────────────────────────────────────

function HealthProfileV2PageInner() {
  const router = useRouter();

  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);
  const [profile, setProfile] = useState<HealthProfileBasic | null>(null);
  const [todayMetrics, setTodayMetrics] = useState<TodayMetricsResponse | null>(null);
  const [medications, setMedications] = useState<MedicationPlanCard[]>([]);
  const [isLinked, setIsLinked] = useState(false);
  const [showAddMember, setShowAddMember] = useState(false);
  const [heroMetrics, setHeroMetrics] = useState<HeroMetric[]>([]);
  const [showHeroEdit, setShowHeroEdit] = useState(false);
  const [heroEditDraft, setHeroEditDraft] = useState<HealthProfileBasic | null>(null);
  const [medHero, setMedHero] = useState<{ display_text: string; status: string; remaining_today: number; next_medication_text?: string | null } | null>(null);
  const [medSummary, setMedSummary] = useState<Array<{ id: number; name: string; dosage: string; frequency_text: string; timing_text: string; status_text: string }>>([]);
  const [guardedFlags, setGuardedFlags] = useState<Map<number, { guarded: boolean; managed_user_id: number | null }>>(new Map());
  // [健康档案优化 PRD v1.0 §3.1] managed_count 改为统计「所有 status」，与 v12/i-guard.total_count 对齐
  // [BUGFIX-MY-GUARDIAN-CARD-20260528] 卡片口径：archive_record_total（档案记录数）+ 动态额度
  const [guardianSummary, setGuardianSummary] = useState<{
    managed_count: number;
    active_count: number;
    archive_record_total: number;
    guarded_count: number;
    bound_others_count: number;
    max_guardians: number;
    can_invite_count: number;
    is_unlimited: boolean;
  }>({ managed_count: 0, active_count: 0, archive_record_total: 0, guarded_count: 0, bound_others_count: 0, max_guardians: 0, can_invite_count: 0, is_unlimited: false });
  // [BUGFIX-HEALTHPROFILE-GUARDIAN-CARDS-20260527] 「守护我的人」拆双数字
  const [reverseGuardianCount, setReverseGuardianCount] = useState<number>(0);
  // [PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 增加 max_guardians_for_me / is_top_level / is_unlimited 等字段
  const [reverseGuardianSummary, setReverseGuardianSummary] = useState<{
    active_count: number;
    pending_count: number;
    total_count: number;
    max_guardians_for_me: number;
    max_guardians_by_me: number;
    bound_others_count: number;
    is_top_level: boolean;
    is_unlimited: boolean;
    member_level: string;
  }>({
    active_count: 0, pending_count: 0, total_count: 0,
    max_guardians_for_me: 3, max_guardians_by_me: 3, bound_others_count: 0,
    is_top_level: false, is_unlimited: false, member_level: 'free',
  });
  // [健康档案优化 PRD v1.0 §3.4] 非本人 Tab「守护 TA 的人」只读详情弹窗
  const [guardianReadonlyList, setGuardianReadonlyList] = useState<any[]>([]);
  const [guardianReadonlyDetail, setGuardianReadonlyDetail] = useState<any | null>(null);
  const [todayDataUpdatedAt, setTodayDataUpdatedAt] = useState<string>('');
  const searchParams = useSearchParams();

  // Health info state (inlined from HealthInfoBlock)
  const [healthInfo, setHealthInfo] = useState<HealthInfo | null>(null);
  const [healthInfoDraft, setHealthInfoDraft] = useState<HealthInfo>({
    chronic_diseases: [], surgery_history: [],
    drug_allergies: [], food_allergies: [], other_allergies: [],
    family_history: [],
  });
  const [showAddFamily, setShowAddFamily] = useState(false);
  const [showAddSurgery, setShowAddSurgery] = useState(false);
  const [familyForm, setFamilyForm] = useState({ relation: '爸爸', disease: '', note: '' });
  const [surgeryForm, setSurgeryForm] = useState({ name: '', time: '', note: '' });
  const [editingFamilyIdx, setEditingFamilyIdx] = useState<number | null>(null);
  const [editingSurgeryIdx, setEditingSurgeryIdx] = useState<number | null>(null);
  const [editRelation, setEditRelation] = useState('');

  // Overview state (from HealthArchiveV5Inject)
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
    alerts_unresolved: 0, medication_plan_count: 0,
    family_member_count: 0, device_count: 0,
    medical_records_by_category: { case_note: 0, checkup_report: 0, drug: 0, other: 0 },
    trash_count: 0, show_alert_banner: false, banner_text: '',
  });

  // [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 本人资料完善弹窗 + 抽屉
  const [selfNeedComplete, setSelfNeedComplete] = useState<boolean>(false);
  const [selfMissingFields, setSelfMissingFields] = useState<string[]>([]);
  const [showSelfCompleteDialog, setShowSelfCompleteDialog] = useState<boolean>(false);
  const [showSelfCompleteDrawer, setShowSelfCompleteDrawer] = useState<boolean>(false);
  const [selfInitialForDrawer, setSelfInitialForDrawer] = useState<any>(null);
  // 本会话已弹过标志位（来回切 Tab 不重复弹）
  const selfDialogShownInSessionRef = useRef<boolean>(false);

  // Collapsible sections
  const [medExpanded, setMedExpanded] = useState(false);
  const [medShowAll, setMedShowAll] = useState(false);
  const [recordsExpanded, setRecordsExpanded] = useState(false);
  const [recordDrawer, setRecordDrawer] = useState<{ key: string; label: string; emoji: string; color: string } | null>(null);
  const [recordDrawerItems, setRecordDrawerItems] = useState<any[]>([]);
  const [recordDrawerLoading, setRecordDrawerLoading] = useState(false);

  // [BUGFIX-HEALTH-PROFILE-CLIENT-CRASH 2026-05-29]
  // selectedMember / memberQs 必须声明在所有 useEffect / useCallback 引用它的地方之前；
  // 否则在 Next.js 生产构建 (terser + chunk 拆分) 下会触发 TDZ（如：ReferenceError: Cannot access 'tn' before initialization）。
  // 开发模式下因 HMR 容错看不出来，但生产 SSR/CSR 一旦执行到这些 hook 就立刻崩溃。
  const selectedMember = useMemo(
    () => members.find((m) => m.id === selectedMemberId) || null,
    [members, selectedMemberId]
  );
  const memberQs = selectedMemberId && selectedMemberId > 0 ? `?member_id=${selectedMemberId}` : '';

  // ─── Fetch functions ────────────────────────────────────────────

  const fetchMembers = useCallback(async () => {
    try {
      const res: any = await api.get('/api/family/members');
      const data = res.data || res;
      const items: FamilyMember[] = Array.isArray(data.items) ? data.items : [];
      setMembers(items);
      if (items.length > 0 && selectedMemberId == null) {
        const urlMemberId = searchParams?.get('member_id');
        const targetMember = urlMemberId
          ? items.find((m) => String(m.id) === urlMemberId)
          : null;
        const fallback = items.find((m) => m.is_self) || items[0];
        setSelectedMemberId(targetMember?.id ?? fallback.id);
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
      const now = new Date();
      setTodayDataUpdatedAt(`${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`);
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

  const consultantIdParam = useMemo(() => {
    const m = members.find((x) => x.id === selectedMemberId);
    if (!m) return -1;
    return m.is_self ? 0 : m.id;
  }, [members, selectedMemberId]);

  const fetchMedHero = useCallback(async (consultantId: number) => {
    try {
      const res: any = await api.get(`/api/medication-plans/hero-count?consultant_id=${consultantId}`);
      const data = res.data || res;
      setMedHero({ display_text: data.display_text, status: data.status, remaining_today: data.remaining_today, next_medication_text: data.next_medication_text });
    } catch {
      setMedHero(null);
    }
  }, []);

  const fetchMedSummary = useCallback(async (consultantId: number) => {
    try {
      const res: any = await api.get(`/api/medication-plans/summary?consultant_id=${consultantId}`);
      const data = res.data || res;
      setMedSummary(Array.isArray(data.items) ? data.items : []);
    } catch {
      setMedSummary([]);
    }
  }, []);

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

  const fetchGuardianSummary = useCallback(async () => {
    // [BUGFIX-MY-GUARDIAN-CARD-20260528] 卡片改用 v13 /family/list：
    // - archive_record_total：所有守护对象（不含本人）的档案记录条数
    // - max_guardians / can_invite_count / is_unlimited：动态额度（按会员等级）
    try {
      const res: any = await api.get('/api/guardian/v13/family/list');
      const data = res.data || res;
      const archiveTotal = Number(data.archive_record_total ?? 0);
      const guardedCount = Number(data.guarded_count ?? data.quota_used ?? 0);
      const maxGuard = Number(data.max_guardians ?? 0);
      const canInv = Number(data.can_invite_count ?? 0);
      const isUnlim = !!data.is_unlimited;
      // [BUGFIX-MY-PROFILE-4ITEMS-20260528 修复 2] X = 已绑定的非本人档案数（不含本人）
      const boundOthersCount = Number(
        data.bound_others_count
        ?? (Array.isArray(data.items)
          ? data.items.filter((it: any) => it.bind_status === 'bound' && !it.is_self).length
          : 0)
      );
      setGuardianSummary({
        managed_count: archiveTotal,        // 兼容：卡片主显示数字 = 档案记录数
        active_count: Number(data.active_count ?? 0),
        archive_record_total: archiveTotal,
        guarded_count: guardedCount,
        bound_others_count: boundOthersCount,
        max_guardians: maxGuard,
        can_invite_count: canInv,
        is_unlimited: isUnlim,
      });
    } catch {
      // 兼容：v13 异常时回退到 v12/i-guard
      try {
        const res2: any = await api.get('/api/guardian/v12/i-guard');
        const data2 = res2.data || res2;
        const total = Number(data2.total_count ?? data2.total ?? 0);
        setGuardianSummary({
          managed_count: total,
          active_count: Number(data2.active_count ?? 0),
          archive_record_total: total,
          guarded_count: total,
          bound_others_count: total,
          max_guardians: 0,
          can_invite_count: 0,
          is_unlimited: false,
        });
      } catch {
        setGuardianSummary({ managed_count: 0, active_count: 0, archive_record_total: 0, guarded_count: 0, bound_others_count: 0, max_guardians: 0, can_invite_count: 0, is_unlimited: false });
      }
    }
  }, []);

  const fetchReverseGuardianCount = useCallback(async () => {
    try {
      const res: any = await api.get('/api/reverse-guardian/guardian-count');
      const data = res.data || res;
      const active = Number(data.active_count ?? data.count ?? 0);
      const pending = Number(data.pending_count ?? 0);
      const total = Number(data.total_count ?? (active + pending) ?? 0);
      setReverseGuardianCount(active);
      setReverseGuardianSummary({
        active_count: active,
        pending_count: pending,
        total_count: total,
        max_guardians_for_me: Number(data.max_guardians_for_me ?? 3),
        max_guardians_by_me: Number(data.max_guardians_by_me ?? 3),
        bound_others_count: Number(data.bound_others_count ?? 0),
        is_top_level: !!data.is_top_level,
        is_unlimited: !!data.is_unlimited,
        member_level: String(data.member_level || 'free'),
      });
    } catch {
      setReverseGuardianCount(0);
      setReverseGuardianSummary({
        active_count: 0, pending_count: 0, total_count: 0,
        max_guardians_for_me: 3, max_guardians_by_me: 3, bound_others_count: 0,
        is_top_level: false, is_unlimited: false, member_level: 'free',
      });
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

  const fetchHealthInfo = useCallback(async (profileId: number) => {
    try {
      const res: any = await api.get(`/api/prd469/health-info/${profileId}`);
      const data = res.data || res;
      const parsed: HealthInfo = {
        chronic_diseases: data.chronic_diseases || [],
        surgery_history: data.surgery_history || [],
        drug_allergies: data.drug_allergies || [],
        food_allergies: data.food_allergies || [],
        other_allergies: data.other_allergies || [],
        family_history: data.family_history || [],
        habit_smoking: data.habit_smoking,
        habit_drinking: data.habit_drinking,
        habit_exercise: data.habit_exercise,
        habit_diet: data.habit_diet,
      };
      setHealthInfo(parsed);
    } catch {
      setHealthInfo(null);
    }
  }, []);

  const fetchOverview = useCallback(async (consultantId: number, memberId: number | null) => {
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
    } catch { /* silent */ }
  }, []);

  // [BUG_FIX 2026-05-29] 重要：本接口只判定"本人"那条档案是否完善，
  // 与其他成员（守护对象）档案完全解耦。请勿在前端基于成员列表二次判定。
  // 后端接口已升级为跨 health_profiles / family_members(is_self) / users 三表取并集，
  // 旧用户的资料无论落在哪一处，只要凑齐三项即视为已完善，不会再被误弹。
  // [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 拉取本人 needComplete 状态
  const fetchSelfNeedComplete = useCallback(async () => {
    try {
      const res: any = await api.get('/api/health-profile/self');
      const data = res?.data?.data || res?.data || res;
      const need = !!data?.needComplete;
      const missing: string[] = Array.isArray(data?.missingFields) ? data.missingFields : [];
      setSelfNeedComplete(need);
      setSelfMissingFields(missing);
      setSelfInitialForDrawer({
        name: data?.name,
        gender: data?.gender,
        birthday: data?.birthday,
        height: data?.height,
        weight: data?.weight,
      });
      return { need, missing };
    } catch {
      setSelfNeedComplete(false);
      setSelfMissingFields([]);
      return { need: false, missing: [] };
    }
  }, []);

  const fetchRecordsByCategory = useCallback(async (categoryKey: string, memberId: number | null) => {
    setRecordDrawerLoading(true);
    try {
      const mid = memberId ?? 0;
      const qs = mid > 0 ? `?category=${categoryKey}&member_id=${mid}` : `?category=${categoryKey}`;
      const res: any = await api.get(`/api/health-archive-v5/medical-records${qs}`);
      const data = res?.data || res || {};
      setRecordDrawerItems(Array.isArray(data.items) ? data.items : []);
    } catch {
      setRecordDrawerItems([]);
    } finally {
      setRecordDrawerLoading(false);
    }
  }, []);

  // ─── Effects ────────────────────────────────────────────────────

  useEffect(() => { fetchMembers(); }, [fetchMembers]);
  useEffect(() => { fetchGuardedFlags(); fetchGuardianSummary(); fetchReverseGuardianCount(); }, [fetchGuardedFlags, fetchGuardianSummary, fetchReverseGuardianCount]);
  // [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 进入页面后拉取 needComplete 状态
  useEffect(() => { fetchSelfNeedComplete(); }, [fetchSelfNeedComplete]);

  // [BUG_FIX 2026-05-29] 会话级防重弹（sessionStorage）+ 24h snooze 软抑制
  // 取代旧的 useRef 实现，避免 Tab 切换 / 路由刷新引起的"每次进入都弹"问题。
  // useRef 在隐私模式 / sessionStorage 不可用时仍作为兜底。
  useEffect(() => {
    if (!selectedMember || !selectedMember.is_self) return;
    if (!selfNeedComplete) return;
    if (selfDialogShownInSessionRef.current) return;
    try {
      if (typeof window !== 'undefined' && window.sessionStorage) {
        if (sessionStorage.getItem(SELF_COMPLETE_DIALOG_SHOWN_KEY) === '1') {
          selfDialogShownInSessionRef.current = true;
          return;
        }
      }
    } catch { /* ignore */ }
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        const snooze = Number(localStorage.getItem(SELF_COMPLETE_DIALOG_SNOOZE_UNTIL_KEY) || 0);
        if (snooze && snooze > Date.now()) {
          selfDialogShownInSessionRef.current = true;
          return;
        }
      }
    } catch { /* ignore */ }
    const timer = setTimeout(() => {
      selfDialogShownInSessionRef.current = true;
      try {
        if (typeof window !== 'undefined' && window.sessionStorage) {
          sessionStorage.setItem(SELF_COMPLETE_DIALOG_SHOWN_KEY, '1');
        }
      } catch { /* ignore */ }
      setShowSelfCompleteDialog(true);
    }, 500);
    return () => clearTimeout(timer);
  }, [selectedMember, selfNeedComplete]);

  useEffect(() => {
    const f = searchParams?.get('focus');
    if (f === 'medication') {
      setTimeout(() => {
        setMedExpanded(true);
        const el = document.getElementById('medication-plan');
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 300);
    }
  }, [searchParams, medSummary.length]);

  useEffect(() => {
    if (selectedMemberId == null) return;
    setMedHero(null);
    setMedSummary([]);
    setTodayMetrics(null);
    setMedications([]);
    setHeroMetrics([]);
    setHealthInfo(null);
    setMedExpanded(false);
    setMedShowAll(false);
    setRecordsExpanded(false);
    try {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
      const scrollContainer = document.querySelector('[data-testid="health-profile-page"]');
      if (scrollContainer) scrollContainer.scrollTop = 0;
    } catch {}
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
          fetchHealthInfo(profileId),
          fetchOverview(cid, selectedMemberId),
        ]);
      }
    })();
  }, [selectedMemberId, members, fetchProfile, fetchTodayMetrics, fetchMedication, fetchLinkStatus, fetchHeroSummary, fetchMedHero, fetchMedSummary, fetchHealthInfo, fetchOverview]);

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
    onVisible();
    return () => {
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', onVisible);
    };
  }, [profile?.id, fetchMedication]);

  // [PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 返回首页时强制刷新守护人/守护对象计数
  useEffect(() => {
    const refreshGuardianCards = () => {
      if (document.visibilityState === 'visible') {
        fetchReverseGuardianCount();
        fetchGuardianSummary();
      }
    };
    document.addEventListener('visibilitychange', refreshGuardianCards);
    window.addEventListener('focus', refreshGuardianCards);
    return () => {
      document.removeEventListener('visibilitychange', refreshGuardianCards);
      window.removeEventListener('focus', refreshGuardianCards);
    };
  }, [fetchReverseGuardianCount, fetchGuardianSummary]);

  // [BUGFIX-HEALTH-PROFILE-CLIENT-CRASH 2026-05-29]
  // selectedMember / memberQs 已上移到 useState 区段之后、所有 useEffect 之前，避免生产构建 TDZ。
  // 此处保留兼容性占位（已删除重复声明）。

  // ─── Health info tag helpers ────────────────────────────────────

  const healthInfoTags = useMemo(() => {
    if (!healthInfo) return [];
    const tags: { label: string; bg: string; fg: string }[] = [];
    for (const c of healthInfo.chronic_diseases) {
      tags.push({ label: c.name, bg: 'rgba(239,68,68,0.25)', fg: '#FECACA' });
    }
    for (const d of healthInfo.drug_allergies) {
      tags.push({ label: `${d}过敏`, bg: 'rgba(245,158,11,0.25)', fg: '#FDE68A' });
    }
    for (const f of healthInfo.food_allergies) {
      tags.push({ label: `${f}过敏`, bg: 'rgba(245,158,11,0.25)', fg: '#FDE68A' });
    }
    for (const o of healthInfo.other_allergies) {
      tags.push({ label: `${o}过敏`, bg: 'rgba(245,158,11,0.25)', fg: '#FDE68A' });
    }
    for (const s of healthInfo.surgery_history) {
      tags.push({ label: s.name, bg: 'rgba(139,92,246,0.25)', fg: '#DDD6FE' });
    }
    for (const fh of healthInfo.family_history) {
      tags.push({ label: `${fh.relation}·${fh.disease}`, bg: 'rgba(59,130,246,0.25)', fg: '#BFDBFE' });
    }
    if (healthInfo.habit_smoking === '有') tags.push({ label: '吸烟', bg: 'rgba(107,114,128,0.25)', fg: '#E5E7EB' });
    if (healthInfo.habit_smoking === '无') tags.push({ label: '不吸烟', bg: 'rgba(16,185,129,0.25)', fg: '#A7F3D0' });
    if (healthInfo.habit_drinking === '有') tags.push({ label: '饮酒', bg: 'rgba(107,114,128,0.25)', fg: '#E5E7EB' });
    if (healthInfo.habit_drinking === '无') tags.push({ label: '不饮酒', bg: 'rgba(16,185,129,0.25)', fg: '#A7F3D0' });
    if (healthInfo.habit_exercise) tags.push({ label: `运动·${healthInfo.habit_exercise}`, bg: 'rgba(16,185,129,0.25)', fg: '#A7F3D0' });
    if (healthInfo.habit_diet) tags.push({ label: `饮食·${healthInfo.habit_diet}`, bg: 'rgba(16,185,129,0.25)', fg: '#A7F3D0' });
    return tags;
  }, [healthInfo]);

  // ─── Health info editing helpers (inlined from HealthInfoBlock) ─

  const toggleChronic = (name: string) => {
    setHealthInfoDraft((d) => {
      const exists = d.chronic_diseases.find((c) => c.name === name);
      const next = exists
        ? d.chronic_diseases.filter((c) => c.name !== name)
        : [...d.chronic_diseases, { name }];
      return { ...d, chronic_diseases: next };
    });
  };

  const addFamilyHistory = () => {
    if (!familyForm.disease.trim()) {
      showToast('请输入疾病名称', 'fail');
      return;
    }
    const item = { relation: familyForm.relation, disease: familyForm.disease.trim(), note: familyForm.note.trim() || undefined };
    let newList: any[];
    if (editingFamilyIdx !== null) {
      newList = [...(healthInfoDraft.family_history || [])];
      newList[editingFamilyIdx] = item;
      setEditingFamilyIdx(null);
    } else {
      newList = [...(healthInfoDraft.family_history || []), item];
    }
    setHealthInfoDraft({ ...healthInfoDraft, family_history: newList });
    setFamilyForm({ relation: '爸爸', disease: '', note: '' });
    setShowAddFamily(false);
  };

  const removeFamilyHistory = (idx: number) => {
    const newList = (healthInfoDraft.family_history || []).filter((_, i) => i !== idx);
    setHealthInfoDraft({ ...healthInfoDraft, family_history: newList });
  };

  const editFamilyHistory = (idx: number) => {
    const item = (healthInfoDraft.family_history || [])[idx];
    if (!item) return;
    setFamilyForm({ relation: item.relation || '爸爸', disease: item.disease || '', note: item.note || '' });
    setEditingFamilyIdx(idx);
    setShowAddFamily(true);
  };

  const addSurgeryHistory = () => {
    if (!surgeryForm.name.trim()) {
      showToast('请输入手术名称', 'fail');
      return;
    }
    const item = { name: surgeryForm.name.trim(), time: surgeryForm.time || undefined, note: surgeryForm.note.trim() || undefined };
    let newList: any[];
    if (editingSurgeryIdx !== null) {
      newList = [...(healthInfoDraft.surgery_history || [])];
      newList[editingSurgeryIdx] = item;
      setEditingSurgeryIdx(null);
    } else {
      newList = [...(healthInfoDraft.surgery_history || []), item];
    }
    setHealthInfoDraft({ ...healthInfoDraft, surgery_history: newList });
    setSurgeryForm({ name: '', time: '', note: '' });
    setShowAddSurgery(false);
  };

  const removeSurgeryHistory = (idx: number) => {
    const newList = (healthInfoDraft.surgery_history || []).filter((_, i) => i !== idx);
    setHealthInfoDraft({ ...healthInfoDraft, surgery_history: newList });
  };

  const editSurgeryHistory = (idx: number) => {
    const item = (healthInfoDraft.surgery_history || [])[idx];
    if (!item) return;
    setSurgeryForm({ name: item.name || '', time: item.time || '', note: item.note || '' });
    setEditingSurgeryIdx(idx);
    setShowAddSurgery(true);
  };

  // ─── Member Bar (Capsule/Pill layout) ───────────────────────────

  const renderMemberBar = () => (
    <div
      data-testid="prd469-member-bar"
      style={{
        background: '#FFFFFF',
        padding: '8px 16px 10px',
        display: 'flex',
        gap: 8,
        overflowX: 'auto',
        alignItems: 'center',
        WebkitOverflowScrolling: 'touch',
        msOverflowStyle: 'none',
        scrollbarWidth: 'none',
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
        const capsuleText = m.nickname || m.name || '未命名';
        return (
          <div
            key={m.id}
            data-testid={`bh-member-tab-${m.id}`}
            onClick={() => setSelectedMemberId(m.id)}
            style={{
              flex: '0 0 auto',
              height: 36,
              borderRadius: 18,
              background: active ? '#0EA5E9' : '#F1F5F9',
              display: 'flex',
              alignItems: 'center',
              padding: '0 12px 0 4px',
              cursor: 'pointer',
              position: 'relative',
              transition: 'background-color 200ms ease, color 200ms ease',
              gap: 6,
            }}
          >
            <div
              style={{
                position: 'relative',
                width: 28,
                height: 28,
                borderRadius: '50%',
                background: palette.bg,
                color: palette.fg,
                fontSize: 13,
                fontWeight: 700,
                lineHeight: '28px',
                textAlign: 'center',
                flexShrink: 0,
              }}
            >
              {badgeChar}
              {guarded && (
                <span
                  data-testid={`bh-guarded-badge-${m.id}`}
                  style={{
                    position: 'absolute',
                    top: -5,
                    right: -8,
                    background: '#FFF3E8',
                    color: '#FF7A1A',
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '0px 4px',
                    borderRadius: 8,
                    boxShadow: '0 1px 4px rgba(255,122,26,0.25)',
                    border: '1px solid #fff',
                    whiteSpace: 'nowrap',
                    lineHeight: 1.3,
                  }}
                >已绑定</span>
              )}
            </div>
            <span
              style={{
                fontSize: 13,
                fontWeight: active ? 600 : 500,
                color: active ? '#FFFFFF' : '#64748B',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                maxWidth: 100,
              }}
            >
              {capsuleText}
            </span>
          </div>
        );
      })}
      <div
        onClick={() => setShowAddMember(true)}
        data-testid="prd469-add-member-btn"
        style={{
          flex: '0 0 auto',
          height: 36,
          borderRadius: 18,
          background: '#F1F5F9',
          display: 'flex',
          alignItems: 'center',
          padding: '0 12px',
          cursor: 'pointer',
          gap: 4,
        }}
      >
        <span style={{ fontSize: 18, color: '#6B7280', lineHeight: 1 }}>+</span>
        <span style={{ fontSize: 13, color: '#6B7280', whiteSpace: 'nowrap' }}>添加</span>
      </div>
    </div>
  );

  // ─── F4~F7: Hero Card ───────────────────────────────────────────

  const renderHero = () => {
    if (!profile) return null;
    const age = profile.birthday ? calcAge(profile.birthday) : null;
    const relLabel = selectedMember?.is_self ? '本人' : (selectedMember?.relation_type_name || '家庭成员');
    const genderText = profile.gender ? formatGender(profile.gender) : '';

    return (
      <div style={{ padding: '8px 16px' }}>
        <div
          data-testid="prd469-hero-card"
          style={{
            background: T.gradient, color: '#fff', borderRadius: 14, padding: '14px 16px',
            boxShadow: T.shadow, position: 'relative',
          }}
        >
          <button
            data-testid="prd469-hero-edit-btn"
            onClick={() => {
              setHeroEditDraft(profile);
              setEditRelation(selectedMember?.relation_type_name || selectedMember?.relationship_type || '');
              if (healthInfo) setHealthInfoDraft(healthInfo);
              setShowHeroEdit(true);
            }}
            style={{
              position: 'absolute', top: 10, right: 10,
              padding: '3px 8px', borderRadius: 10,
              background: 'rgba(255,255,255,0.25)', color: '#fff',
              border: '1px solid rgba(255,255,255,0.4)',
              fontSize: 11, fontWeight: 500, cursor: 'pointer',
            }}
          >编辑</button>

          {/* Upper: Avatar + Name + Age + Relation + Gender */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 64, height: 64, borderRadius: '50%',
                background: 'rgba(255,255,255,0.18)',
                padding: 4,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <MemberBadge
                relationName={selectedMember?.relation_type_name || selectedMember?.relationship_type || ''}
                name={selectedMember?.nickname || profile.name}
                isSelf={!!selectedMember?.is_self}
                size={56}
                fontSize={22}
                showPlaceholderTag={false}
              />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 22, fontWeight: 700 }}>{profile.name || '未填'}</span>
                <span
                  data-testid="bh-hero-relation-label"
                  style={{
                    fontSize: 12, fontWeight: 500,
                    padding: '2px 8px', borderRadius: 10,
                    background: 'rgba(255,255,255,0.28)',
                  }}
                >{relLabel}</span>
              </div>
              <div style={{ fontSize: 13, opacity: 0.85, marginTop: 2 }}>
                {[genderText, age != null ? `${age}岁` : '', profile.height ? `${profile.height}cm` : '', profile.weight ? `${profile.weight}kg` : ''].filter(Boolean).join(' · ')}
              </div>
            </div>
          </div>

          {/* Lower: Health info tags */}
          <div style={{ marginTop: 10 }}>
            {healthInfoTags.length === 0 ? (
              <div
                onClick={() => {
                  setHeroEditDraft(profile);
                  setEditRelation(selectedMember?.relation_type_name || selectedMember?.relationship_type || '');
                  if (healthInfo) setHealthInfoDraft(healthInfo);
                  else setHealthInfoDraft({ chronic_diseases: [], surgery_history: [], drug_allergies: [], food_allergies: [], other_allergies: [], family_history: [] });
                  setShowHeroEdit(true);
                }}
                style={{
                  border: '1px dashed rgba(255,255,255,0.5)',
                  borderRadius: 12,
                  padding: '14px 16px',
                  textAlign: 'center',
                  fontSize: 13,
                  color: 'rgba(255,255,255,0.8)',
                  cursor: 'pointer',
                }}
              >
                尚未填写健康信息，点击补充 ›
              </div>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {healthInfoTags.map((tag, i) => (
                  <span
                    key={i}
                    style={{
                      padding: '3px 10px', borderRadius: 12,
                      background: tag.bg,
                      color: '#fff',
                      fontSize: 12, fontWeight: 500,
                    }}
                  >{tag.label}</span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  // ─── Invite Area (restored) ─────────────────────────────────────

  const currentGuardStatus = useMemo(() => {
    if (!selectedMember) return 'self';
    if (selectedMember.is_self) return 'self';
    const flag = guardedFlags.get(selectedMember.id);
    return flag?.guarded ? 'guarded' : 'unguarded';
  }, [selectedMember, guardedFlags]);

  const showInvite = currentGuardStatus === 'unguarded';

  // [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29 路口B1 / §4.1]
  // 健康档案首页的「去邀请 ›」大按钮已按 PRD 删除——所有发起邀请的入口
  // 现在统一收口到「档案列表」（archive-list）。点击入口卡进入档案列表后，
  // 按 7 态状态机在卡片上发起或重新邀请。
  const renderInviteArea = () => {
    // 显式返回 null 以保留对 showInvite/selectedMember 的引用，避免 TS 未使用变量告警
    void showInvite;
    return null;
  };

  // ─── F9: 双卡片（健康档案列表 + 守护我的人） ──────────
  // [PRD-HEALTH-ARCHIVE-MGR-V1 2026-05-29]
  //   资产/配额语境改名：「我守护的人」→「健康档案列表」（左侧入口卡）
  //   关系/邀请语境保留：右侧「守护我的人」/「守护 TA 的人」不变
  // 入口卡片直达 /health-profile/i-guard
  // [健康档案优化 PRD v1.0 2026-05-26 §3.2~3.4]
  // - 「健康档案列表」仅在本人 Tab 显示，直达 /health-profile/i-guard，统计 total_count
  // - 「守护我的人」在本人 Tab 显示；非本人 Tab 改名为「守护 TA 的人」并切换为只读视图

  const openTaGuardianReadonly = async () => {
    if (!selectedMember || selectedMember.is_self) return;
    setGuardianReadonlyDetail(null);
    setGuardianReadonlyList([]);
    try {
      // 取目标用户 ID
      const flag = guardedFlags.get(selectedMember.id);
      const managedUid = flag?.managed_user_id;
      if (!managedUid) {
        setGuardianReadonlyList([]);
        return;
      }
      const res: any = await api.get(`/api/guardian/v12/managed/${managedUid}/all-guardians`);
      const data = res.data || res;
      setGuardianReadonlyList(Array.isArray(data.items) ? data.items : []);
    } catch {
      setGuardianReadonlyList([]);
    }
  };

  // [PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 双卡片副标题统一为：
  //   守护对象/守护者：X 人（上限 Y 人）
  // 五种按钮状态（本人 Tab）：
  //   1. 普通会员未满（X<Y）：黑字 + 蓝色【升级会员】可点
  //   2. 普通会员已满（X=Y）：红字 + 红色【升级会员】可点
  //   3. 顶级会员未满（X<Y）：黑字 + 无按钮
  //   4. 顶级会员已满（X=Y）：红字 + 置灰【达上限】不可点
  //   5. 家人 Tab 只读：黑字 + 无按钮（按钮全部不显示）
  const renderDualCards = () => {
    const isSelfTab = !!selectedMember?.is_self;
    const otherSideTitle = isSelfTab ? '守护我的人' : '守护 TA 的人';
    // [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29 路口C1] 入口卡命名与档案列表页对齐
    // 本人 Tab 入口卡 → 「档案列表」（直达 /health-profile/archive-list）
    // 家人 Tab 关系视图命名保留 → 「TA 守护的人」（关系语境，不改）
    const taTitle = isSelfTab ? '档案列表' : 'TA 守护的人';
    const isTopLevel = !!reverseGuardianSummary.is_top_level;

    // 「健康档案列表」入口卡字段
    const xByMe = guardianSummary.bound_others_count ?? 0;
    const yByMe = guardianSummary.is_unlimited
      ? (guardianSummary.max_guardians || reverseGuardianSummary.max_guardians_by_me || 3)
      : (guardianSummary.max_guardians || reverseGuardianSummary.max_guardians_by_me || 3);
    const isUnlimitedByMe = !!guardianSummary.is_unlimited;
    const isFullByMe = !isUnlimitedByMe && xByMe >= yByMe;

    // 「守护我的人」卡片字段
    const xForMe = reverseGuardianSummary.total_count;
    const yForMe = reverseGuardianSummary.max_guardians_for_me || 3;
    const isUnlimitedForMe = !!reverseGuardianSummary.is_unlimited;
    const isFullForMe = !isUnlimitedForMe && xForMe >= yForMe;

    const renderSubtitleAndButton = (
      x: number,
      y: number,
      isUnlimited: boolean,
      isFull: boolean,
    ) => {
      // 家人 Tab：所有按钮全部不显示，文字黑字
      if (!isSelfTab) {
        return {
          textColor: '#1F2937',
          subtitle: `${x} 人（上限 ${isUnlimited ? '不限' : y} 人）`,
          button: null,
        };
      }
      // 本人 Tab
      const subtitleText = `${x} 人（上限 ${isUnlimited ? '不限' : y} 人）`;
      const textColor = isFull ? '#DC2626' : '#1F2937';

      let button: React.ReactNode = null;
      if (isTopLevel) {
        // 顶级会员
        if (isFull) {
          // 状态 4：置灰【达上限】不可点
          button = (
            <button
              disabled
              data-testid='guardian-card-btn-limit'
              onClick={(e) => e.stopPropagation()}
              style={{
                background: '#E5E7EB', color: '#9CA3AF',
                border: 'none', borderRadius: 14, padding: '4px 12px',
                fontSize: 12, cursor: 'not-allowed', fontWeight: 500,
                whiteSpace: 'nowrap',
              }}
            >达上限</button>
          );
        }
        // 状态 3：未满 → 无按钮
      } else {
        // 普通会员
        const btnBg = isFull ? '#DC2626' : '#1890FF';
        button = (
          <button
            data-testid='guardian-card-btn-upgrade'
            onClick={(e) => {
              e.stopPropagation();
              router.push('/member-center');
            }}
            style={{
              background: btnBg, color: '#fff',
              border: 'none', borderRadius: 14, padding: '4px 12px',
              fontSize: 12, cursor: 'pointer', fontWeight: 500,
              whiteSpace: 'nowrap',
            }}
          >升级会员</button>
        );
      }
      return { textColor, subtitle: subtitleText, button };
    };

    const byMeView = renderSubtitleAndButton(xByMe, yByMe, isUnlimitedByMe, isFullByMe);
    const forMeView = renderSubtitleAndButton(xForMe, yForMe, isUnlimitedForMe, isFullForMe);

    return (
      <div style={{ padding: '0 16px 12px', display: 'flex', gap: 10 }}>
        {/* 「我守护的人」/ 家人 Tab「TA 守护的人」 */}
        <div
          data-testid={isSelfTab ? 'health-profile-i-guard-entry' : 'ta-i-guard-entry'}
          onClick={() => {
            // [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29 路口A1] 旧 i-guard 整体下线，
            // 入口卡跳转改为新的 archive-list（7 态状态机版）
            if (isSelfTab) router.push('/health-profile/archive-list');
          }}
          style={{
            flex: 1, background: '#fff', borderRadius: 12, padding: '12px 12px',
            display: 'flex', flexDirection: 'column', gap: 8,
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            cursor: isSelfTab ? 'pointer' : 'default',
            minHeight: 88,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: '#E3F2FD', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <span style={{ fontSize: 18 }}>👨‍👩‍👧</span>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#1F2937' }}>{taTitle}</div>
            </div>
            {isSelfTab && <span style={{ fontSize: 16, color: '#9CA3AF' }}>›</span>}
          </div>
          {/* 副标题：
              - 本人 Tab（资产/配额）：「健康档案：X 份（含本人，上限 Y 份）」
              - 家人 Tab（关系/只读）：「守护对象：X 人（上限 Y 人）」保留 */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <div
              data-testid='i-guard-subtitle'
              style={{ fontSize: 12, color: byMeView.textColor, lineHeight: 1.4, flex: 1, minWidth: 0 }}
            >
              {/* [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29 验收 8.1#2]
                  本人 Tab：「{X} 人 / 上限 {Y} 人（不含本人）」，统一不再 +1
                  家人 Tab：保留原副标题（关系语境） */}
              {isSelfTab
                ? `${xByMe} 人 / 上限 ${isUnlimitedByMe ? '不限' : yByMe} 人（不含本人）`
                : `守护对象：${byMeView.subtitle}`}
            </div>
            {byMeView.button}
          </div>
        </div>

        {/* 「守护我的人」/ 家人 Tab「守护 TA 的人」 */}
        <div
          data-testid={isSelfTab ? 'my-guardians-entry' : 'ta-guardians-entry'}
          onClick={() => {
            if (isSelfTab) router.push('/health-profile/my-guardians');
            else openTaGuardianReadonly();
          }}
          style={{
            flex: 1, background: '#fff', borderRadius: 12, padding: '12px 12px',
            display: 'flex', flexDirection: 'column', gap: 8,
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)', cursor: 'pointer',
            minHeight: 88,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: '#E8F5E9', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <span style={{ fontSize: 18 }}>💚</span>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#1F2937' }}>{otherSideTitle}</div>
            </div>
            <span style={{ fontSize: 16, color: '#9CA3AF' }}>›</span>
          </div>
          {/* 副标题：守护者：X 人（上限 Y 人） + 按钮 */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <div
              data-testid='my-guardians-subtitle'
              style={{ fontSize: 12, color: forMeView.textColor, lineHeight: 1.4, flex: 1, minWidth: 0 }}
            >
              {isSelfTab
                ? `守护者：${forMeView.subtitle}`
                : `守护者：${forMeView.subtitle}`}
            </div>
            {forMeView.button}
          </div>
        </div>
      </div>
    );
  };

  // [健康档案优化 PRD v1.0 §3.4] 「守护 TA 的人」只读详情弹窗（5 字段：头像 / 姓名 / 关系 / 主守护人 / 加入时间）
  const renderTaGuardianReadonlyDrawer = () => {
    if (selectedMember?.is_self) return null;
    const list = guardianReadonlyList;
    const showList = list.length > 0 || guardianReadonlyDetail !== null;
    if (!showList) return null;
    const fmt = (s?: string) => {
      if (!s) return '—';
      try { return new Date(s).toISOString().slice(0, 10); } catch { return s; }
    };
    return (
      <div
        style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 9999,
          display: 'flex', alignItems: 'flex-end',
        }}
        onClick={() => { setGuardianReadonlyList([]); setGuardianReadonlyDetail(null); }}
        data-testid='ta-guardians-drawer'
      >
        <div
          style={{
            background: '#fff', width: '100%', borderTopLeftRadius: 24, borderTopRightRadius: 24,
            padding: '16px 16px 32px', maxHeight: '85vh', overflow: 'auto',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>
            守护 TA 的人 - {selectedMember?.nickname || '家人'}
          </div>
          <div style={{ fontSize: 12, color: '#8C8C8C', marginBottom: 12 }}>仅可查看，不可操作</div>
          {!guardianReadonlyDetail && list.length === 0 && (
            <div style={{ padding: 24, textAlign: 'center', color: '#8C8C8C' }}>暂无守护人</div>
          )}
          {!guardianReadonlyDetail && list.map((g) => (
            <div
              key={g.management_id}
              data-testid='ta-guardian-item'
              onClick={() => setGuardianReadonlyDetail(g)}
              style={{
                padding: 12, border: '1px solid #f0f0f0', borderRadius: 12, marginBottom: 8,
                display: 'flex', alignItems: 'center', cursor: 'pointer',
              }}
            >
              <div style={{
                width: 44, height: 44, borderRadius: '50%', marginRight: 12,
                background: '#E3F2FD', color: '#1890FF',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18, fontWeight: 700,
              }}>{(g.manager_nickname || '?').charAt(0)}</div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontWeight: 600 }}>{g.manager_nickname || '—'}</span>
                  {g.is_primary_guardian && (
                    <span style={{ background: '#FFB800', color: '#fff', borderRadius: 6, padding: '2px 6px', fontSize: 11, fontWeight: 600 }}>👑 主守护人</span>
                  )}
                </div>
                <div style={{ fontSize: 12, color: '#8C8C8C', marginTop: 4 }}>
                  关系：{g.relation_label || '亲友'} · 加入 {fmt(g.created_at)}
                </div>
              </div>
              <span style={{ color: '#9CA3AF' }}>›</span>
            </div>
          ))}
          {guardianReadonlyDetail && (
            <div data-testid='ta-guardian-detail' style={{ padding: 12, border: '1px solid #f0f0f0', borderRadius: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
                <div style={{
                  width: 64, height: 64, borderRadius: '50%', marginRight: 14,
                  background: '#E3F2FD', color: '#1890FF',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 28, fontWeight: 700,
                }}>{(guardianReadonlyDetail.manager_nickname || '?').charAt(0)}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 6 }}>
                    {guardianReadonlyDetail.manager_nickname || '—'}
                    {guardianReadonlyDetail.is_primary_guardian && (
                      <span style={{ marginLeft: 8, background: '#FFB800', color: '#fff', borderRadius: 6, padding: '2px 6px', fontSize: 12, fontWeight: 600 }}>👑 主守护人</span>
                    )}
                  </div>
                  <div style={{ fontSize: 13, color: '#6B7280' }}>关系：{guardianReadonlyDetail.relation_label || '亲友'}</div>
                  <div style={{ fontSize: 13, color: '#6B7280' }}>加入：{fmt(guardianReadonlyDetail.created_at)}</div>
                </div>
              </div>
              <div style={{ fontSize: 12, color: '#8C8C8C' }}>该信息仅供查看，您无权对此守护关系进行修改。</div>
              <div style={{ marginTop: 12, textAlign: 'right' }}>
                <button
                  onClick={() => setGuardianReadonlyDetail(null)}
                  style={{
                    background: '#fff', border: '1px solid #d9d9d9', padding: '6px 16px',
                    borderRadius: 16, cursor: 'pointer', fontSize: 13,
                  }}
                >返回列表</button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderDevicesEntry = () => (
    <div style={{ padding: '0 16px 12px' }}>
      <div
        data-testid="health-devices-entry"
        onClick={() => {
          const mid = selectedMemberId && selectedMemberId > 0 ? selectedMemberId : 0;
          router.push(`/devices?member_id=${mid}`);
        }}
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '14px 16px',
          display: 'flex',
          alignItems: 'center',
          boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
          cursor: 'pointer',
        }}
      >
        <div style={{ width: 40, height: 40, borderRadius: 10, background: '#F3E5F5', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginRight: 10 }}>
          <span style={{ fontSize: 20 }}>🩺</span>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: '#1F2937' }}>我的设备</div>
        </div>
        <span style={{ fontSize: 12, color: '#6B7280', marginRight: 4 }}>{overview.device_count}台</span>
        <span style={{ fontSize: 14, color: '#9CA3AF' }}>›</span>
      </div>
    </div>
  );

  // ─── F10~F11: Alert Banner ──────────────────────────────────────

  const renderAlertBanner = () => {
    if (!overview.show_alert_banner) return null;
    return (
      <div style={{ padding: '0 16px 12px' }}>
        <div
          onClick={() => router.push(`/health-alerts${memberQs}`)}
          style={{
            background: 'linear-gradient(90deg, #FF6B35 0%, #F97316 100%)',
            color: '#fff', borderRadius: 12, padding: '12px 16px',
            display: 'flex', alignItems: 'center',
            fontSize: 14, cursor: 'pointer',
          }}
        >
          <span style={{ marginRight: 8, fontSize: 18 }}>⚠️</span>
          <span style={{ flex: 1, fontWeight: 500 }}>{overview.banner_text}</span>
          <span style={{ marginLeft: 8, fontSize: 16 }}>›</span>
        </div>
      </div>
    );
  };

  // ─── F12~F14: Medication Plan Collapsible ───────────────────────

  const renderMedicationPlan = () => {
    const list = medSummary;
    const totalCount = list.length;
    const displayList = medShowAll ? list : list.slice(0, 5);

    return (
      <div id="medication-plan" data-testid="prd469-medication-plan" style={{ padding: '0 16px 12px' }}>
        <div
          style={{
            background: '#fff', borderRadius: 12, padding: '14px 16px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)', cursor: 'pointer',
          }}
          onClick={() => setMedExpanded(!medExpanded)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#1F2937' }}>用药计划</span>
            {totalCount > 0 && (
              <span style={{
                background: T.brand500, color: '#fff', fontSize: 11, fontWeight: 600,
                padding: '1px 7px', borderRadius: 10, minWidth: 18, textAlign: 'center',
              }}>{totalCount}</span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span onClick={(e) => { e.stopPropagation(); router.push(`/ai-home/medication-plans/new${memberQs}`); }}
              style={{ fontSize: 13, fontWeight: 500, color: T.brand500 }}>+新增</span>
            <span onClick={(e) => { e.stopPropagation(); router.push(`/ai-home/medication-plans${memberQs}`); }}
              style={{ fontSize: 13, fontWeight: 500, color: T.brand500 }}>全部 ›</span>
            <span style={{ fontSize: 13, color: '#9CA3AF' }}>
              {medExpanded ? '▴' : '▾'}
            </span>
          </div>
        </div>

        {medExpanded && (
          <div style={{ marginTop: 10 }}>
            {totalCount === 0 ? (
              <div style={{
                background: '#fff', borderRadius: 12, padding: '24px 0',
                textAlign: 'center', boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
              }}>
                <button
                  data-testid="med-summary-empty-btn"
                  onClick={() => router.push(`/ai-home/medication-plans/new${memberQs}`)}
                  style={{
                    padding: '12px 24px', background: T.brand500, color: '#fff',
                    border: 'none', borderRadius: 24, fontSize: 15, fontWeight: 600, cursor: 'pointer',
                  }}
                >+ 添加第一条用药计划</button>
              </div>
            ) : (
              <>
                <div data-testid="med-summary-list" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {displayList.map((m) => (
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
                {!medShowAll && totalCount > 5 && (
                  <div style={{ textAlign: 'center', marginTop: 10 }}>
                    <button
                      onClick={() => setMedShowAll(true)}
                      style={{
                        padding: '8px 20px', background: '#fff', color: T.brand600,
                        border: `1px solid ${T.brand200}`, borderRadius: 20, fontSize: 13, fontWeight: 500, cursor: 'pointer',
                      }}
                    >查看全部 ({totalCount})</button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    );
  };

  // ─── F15~F17: Medical Records Collapsible ───────────────────────

  const openRecordDrawer = (cat: typeof V5_RECORD_CATS[number]) => {
    setRecordDrawer(cat);
    fetchRecordsByCategory(cat.key, selectedMemberId);
  };

  const renderMedicalRecords = () => {
    const totalRecords = Object.values(overview.medical_records_by_category).reduce((s, v) => s + v, 0);

    return (
      <div style={{ padding: '0 16px 12px' }}>
        <div
          onClick={() => setRecordsExpanded(!recordsExpanded)}
          style={{
            background: '#fff', borderRadius: 12, padding: '14px 16px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)', cursor: 'pointer',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#1F2937' }}>就医资料</span>
            {totalRecords > 0 && (
              <span style={{
                background: '#10B981', color: '#fff', fontSize: 11, fontWeight: 600,
                padding: '1px 7px', borderRadius: 10, minWidth: 18, textAlign: 'center',
              }}>{totalRecords}</span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span onClick={(e) => { e.stopPropagation(); router.push(`/medical-records?action=new${selectedMemberId ? `&member_id=${selectedMemberId}` : ''}`); }}
              style={{ fontSize: 13, fontWeight: 500, color: T.brand500 }}>+新增</span>
            <span onClick={(e) => { e.stopPropagation(); router.push(`/medical-records/all?member_id=${selectedMemberId || ''}`); }}
              style={{ fontSize: 13, fontWeight: 500, color: T.brand500 }}>全部 ›</span>
            <span style={{ fontSize: 13, color: '#9CA3AF' }}>
              {recordsExpanded ? '▴' : '▾'}
            </span>
          </div>
        </div>

        {recordsExpanded && (
          <div style={{
            marginTop: 10, display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10,
          }}>
            {V5_RECORD_CATS.map((cat) => (
              <div
                key={cat.key}
                onClick={() => router.push(`/medical-records/all?tab=${cat.key}&member_id=${selectedMemberId || ''}`)}
                style={{
                  background: '#fff', borderRadius: 12, padding: '14px 14px',
                  display: 'flex', alignItems: 'center', gap: 10,
                  boxShadow: '0 1px 4px rgba(0,0,0,0.04)', cursor: 'pointer',
                  borderLeft: `3px solid ${cat.color}`,
                }}
              >
                <span style={{ fontSize: 20 }}>{cat.emoji}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#1F2937' }}>{cat.label}</div>
                  <div style={{ fontSize: 12, color: '#6B7280' }}>
                    {overview.medical_records_by_category?.[cat.key] || 0} 份
                  </div>
                </div>
                <span style={{ fontSize: 14, color: '#9CA3AF' }}>›</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // ─── Record Drawer ──────────────────────────────────────────────

  const renderRecordDrawer = () => {
    if (!recordDrawer) return null;
    return (
      <div
        style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          zIndex: 100, display: 'flex', alignItems: 'flex-end',
        }}
        onClick={(e) => { if (e.target === e.currentTarget) setRecordDrawer(null); }}
      >
        <div style={{
          background: '#fff', width: '100%', borderTopLeftRadius: 16, borderTopRightRadius: 16,
          maxHeight: '70vh', display: 'flex', flexDirection: 'column',
        }}>
          <div style={{
            padding: '14px 16px', borderBottom: `1px solid ${T.brand100}`,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{ fontSize: 17, fontWeight: 700 }}>
              {recordDrawer.emoji} {recordDrawer.label}
            </span>
            <span onClick={() => setRecordDrawer(null)} style={{ fontSize: 22, color: '#9ca3af', cursor: 'pointer' }}>×</span>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
            {recordDrawerLoading ? (
              <div style={{ textAlign: 'center', padding: '24px 0', color: '#9CA3AF' }}>加载中…</div>
            ) : recordDrawerItems.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px 0', color: '#9CA3AF' }}>暂无资料</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {recordDrawerItems.map((item: any, idx: number) => (
                  <div
                    key={item.id || idx}
                    onClick={() => item.id && router.push(`/medical-records/all?tab=${recordDrawer?.key || 'case_note'}&highlight=${item.id}&member_id=${selectedMemberId || ''}`)}
                    style={{
                      background: '#F9FAFB', borderRadius: 10, padding: '12px 14px',
                      cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 600, color: '#1F2937', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {item.title || item.name || '未命名'}
                      </div>
                      {item.created_at && (
                        <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 2 }}>{item.created_at}</div>
                      )}
                    </div>
                    <span style={{ fontSize: 14, color: '#9CA3AF', marginLeft: 8 }}>›</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div style={{ padding: 16, borderTop: `1px solid ${T.brand100}` }}>
            <button
              onClick={() => { setRecordDrawer(null); router.push(`/medical-records${memberQs}`); }}
              style={{
                width: '100%', padding: '12px 0', borderRadius: 24,
                background: T.brand500, color: '#fff', border: 'none',
                fontSize: 15, fontWeight: 600, cursor: 'pointer',
              }}
            >上传新资料</button>
          </div>
        </div>
      </div>
    );
  };

  // ─── F18~F19: Today Health Data ─────────────────────────────────

  const renderTodayHealthData = () => {
    const tm = todayMetrics;
    const medChecked = tm?.medication?.checked ?? 0;
    const medTotal = tm?.medication?.total ?? 0;
    const medPercent = medTotal > 0 ? Math.round((medChecked / medTotal) * 100) : 0;

    const vitals = [
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
    ];

    return (
      <div data-testid="prd469-today-data" style={{ padding: '0 16px 12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', margin: '0 0 10px' }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: '#1F2937', margin: 0 }}>今日健康数据</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {todayDataUpdatedAt && (
              <span style={{ fontSize: 12, color: '#9CA3AF' }}>更新时间：{todayDataUpdatedAt}</span>
            )}
            <span
              onClick={() => { if (profile?.id) fetchTodayMetrics(profile.id); }}
              style={{ fontSize: 16, cursor: 'pointer', userSelect: 'none' }}
            >🔄</span>
          </div>
        </div>

        {/* Medication reminder card */}
        {(() => {
          const allDone = medHero?.status === 'all_done' || (medTotal > 0 && medChecked >= medTotal);
          const cardBg = allDone
            ? 'linear-gradient(135deg, #10B981 0%, #059669 100%)'
            : 'linear-gradient(135deg, #4A9EE0 0%, #3B82F6 100%)';
          return (
            <div
              onClick={() => router.push(`/ai-home/medication-reminder?consultant_id=${consultantIdParam}${memberQs ? `&${memberQs.slice(1)}` : ''}`)}
              style={{
                background: cardBg,
                borderRadius: 12, padding: '14px 16px',
                cursor: 'pointer', marginBottom: 12, color: '#fff',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: allDone ? 0 : 6 }}>
                <span style={{ fontSize: 15, fontWeight: 700 }}>💊 用药提醒</span>
                <span onClick={(e) => { e.stopPropagation(); router.push(`/ai-home/medication-reminder?consultant_id=${consultantIdParam}${memberQs ? `&${memberQs.slice(1)}` : ''}`); }}
                  style={{ fontSize: 13, opacity: 0.9 }}>全部 ›</span>
              </div>
              {allDone ? (
                <div style={{ fontSize: 14, marginTop: 6, opacity: 0.95 }}>今日用药已全部完成 ✅</div>
              ) : medHero?.remaining_today != null && medHero.remaining_today > 0 ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 13, opacity: 0.9 }}>⏰ 下一次：{medHero.next_medication_text || medHero.display_text}</span>
                  <span style={{ fontSize: 12, opacity: 0.8 }}>
                    {medHero.remaining_today === 1 ? '最后1次' : `还剩${medHero.remaining_today}次`}
                  </span>
                </div>
              ) : (
                <div style={{ fontSize: 13, opacity: 0.9 }}>暂无用药计划</div>
              )}
            </div>
          );
        })()}

        {/* Vitals 2x2 grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
          {vitals.map((c) => (
            <div
              key={c.id}
              data-testid={`prd469-metric-${c.id}`}
              onClick={() => router.push(`/health-metric/${c.id}?profileId=${profile?.id || ''}`)}
              style={{
                background: '#FFFFFF',
                borderLeft: c.abnormal ? '4px solid #F5B544' : '4px solid transparent',
                borderRadius: 16,
                padding: 14,
                boxShadow: '0 2px 12px rgba(14,165,233,0.08)',
                cursor: 'pointer',
                position: 'relative',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <span style={{ fontSize: 13, color: T.textSecondary }}>{c.icon} {c.label}</span>
                {c.abnormal && (
                  <span style={{
                    fontSize: 10, fontWeight: 600, color: '#fff', background: T.yellow,
                    padding: '1px 6px', borderRadius: 6,
                  }}>异常</span>
                )}
              </div>
              <div style={{ marginTop: 6 }}>
                <span style={{ fontSize: 28, fontWeight: 700, color: '#0C4A6E' }}>{c.value}</span>
                <span style={{ fontSize: 12, color: T.textSecondary, marginLeft: 4 }}>{c.unit}</span>
              </div>
              <div style={{ position: 'absolute', top: 12, right: 12, fontSize: 14, color: T.brand500 }}>›</div>
            </div>
          ))}
        </div>

        {/* [PRD-HOME-SAFETY-V1 2026-05-27] 居家安全设备入口 */}
        <div
          data-testid="home-safety-entry"
          onClick={() => router.push('/home-safety')}
          style={{
            marginTop: 12,
            background: 'linear-gradient(135deg,#1F8FE6 0%,#2EC4B6 100%)',
            color: '#fff',
            borderRadius: 12,
            padding: '14px 16px',
            cursor: 'pointer',
            boxShadow: '0 2px 12px rgba(31,143,230,0.16)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ fontSize: 15, fontWeight: 700 }}>🛡️ 居家安全设备</div>
            <div style={{ fontSize: 12, opacity: 0.92, marginTop: 4 }}>
              紧急呼叫器 / 烟雾报警器 / 水位报警器
            </div>
          </div>
          <div style={{ fontSize: 20 }}>›</div>
        </div>
      </div>
    );
  };

  // ─── F8: Hero Edit Modal ────────────────────────────────────────

  const isSmallScreen = typeof window !== 'undefined' && window.innerWidth <= 375;

  const renderHeroEditModal = () => {
    if (!showHeroEdit || !heroEditDraft) return null;

    // [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29 §6] Hero 编辑页三项必填（全局，对老用户同样生效）
    const nameStr = String(heroEditDraft.name || '').trim();
    const nameInvalid = !nameStr || nameStr === '本人' || nameStr.length > 20;
    const genderInvalid = !heroEditDraft.gender;
    const birthdayInvalid = !heroEditDraft.birthday;
    const requiredAllOk = !nameInvalid && !genderInvalid && !birthdayInvalid;

    const saveAll = async () => {
      if (!heroEditDraft || !selectedMemberId || !profile?.id) return;
      if (!requiredAllOk) {
        showToast('请补全姓名、性别、出生日期', 'fail');
        return;
      }
      try {
        await Promise.all([
          api.put(`/api/health/profile/member/${selectedMemberId}`, {
            name: heroEditDraft.name,
            gender: heroEditDraft.gender,
            birthday: heroEditDraft.birthday,
            height: heroEditDraft.height,
            weight: heroEditDraft.weight,
            blood_type: heroEditDraft.blood_type,
            relationship_type: selectedMember?.is_self ? undefined : editRelation,
          }),
          api.put(`/api/prd469/health-info/${profile.id}`, healthInfoDraft),
        ]);
        setProfile(heroEditDraft);
        setHealthInfo(healthInfoDraft);
        setShowHeroEdit(false);
        showToast('已保存');
        if (selectedMemberId) await fetchProfile(selectedMemberId);
        if (profile?.id) await fetchHealthInfo(profile.id);
      } catch {
        showToast('保存失败', 'fail');
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
        <div style={{
          background: '#fff', width: '100%', borderTopLeftRadius: 16, borderTopRightRadius: 16,
          maxHeight: '90vh', display: 'flex', flexDirection: 'column',
        }}>
          <div style={{
            padding: '14px 16px', borderBottom: `1px solid ${T.brand100}`,
            display: 'flex', justifyContent: 'space-between',
          }}>
            <span style={{ fontSize: 17, fontWeight: 700 }}>编辑个人档案</span>
            <span onClick={() => setShowHeroEdit(false)} style={{ fontSize: 22, color: '#9ca3af', cursor: 'pointer' }}>×</span>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: isSmallScreen ? 10 : 16 }}>
            {/* Section 1: Personal Info */}
            <div style={{ marginBottom: isSmallScreen ? 14 : 20 }}>
              <div style={{ fontSize: isSmallScreen ? 14 : 15, fontWeight: 700, color: T.brand700, marginBottom: isSmallScreen ? 8 : 12, paddingBottom: 6, borderBottom: `2px solid ${T.brand100}` }}>
                个人信息
              </div>
              {/* 关系 */}
              <div style={{ display: 'flex', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid #f3f4f6' }}>
                <span style={{ width: 70, fontSize: 14, color: '#6b7280', flexShrink: 0 }}>关系</span>
                <div style={{ flex: 1, textAlign: 'right' }}>
                  {selectedMember?.is_self ? (
                    <span style={{ fontSize: 14, color: '#374151' }}>本人</span>
                  ) : (
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                      {RELATION_DEFS.map((def) => (
                        <button key={def.name} onClick={() => setEditRelation(def.name)}
                          style={{ padding: '5px 12px', borderRadius: 14, background: editRelation === def.name ? T.brand500 : '#f3f4f6', color: editRelation === def.name ? '#fff' : '#374151', border: 'none', fontSize: 13, cursor: 'pointer' }}>{def.name}</button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              {/* 姓名（必填） */}
              <div style={{ padding: '12px 0', borderBottom: '1px solid #f3f4f6' }}>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <span style={{ width: 70, fontSize: 14, color: '#6b7280', flexShrink: 0 }}>
                    <span style={{ color: '#EF4444', marginRight: 2 }}>*</span>姓名
                  </span>
                  <input
                    type="text" value={heroEditDraft.name || ''}
                    onChange={(e) => setHeroEditDraft({ ...heroEditDraft, name: e.target.value })}
                    maxLength={20}
                    data-testid="hero-edit-name"
                    style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: nameInvalid ? '1px solid #EF4444' : '1px solid #d1d5db', fontSize: 14, textAlign: 'right', boxSizing: 'border-box' }}
                  />
                </div>
                {nameInvalid && (
                  <div data-testid="hero-edit-name-err" style={{ fontSize: 11, color: '#EF4444', marginTop: 4, marginLeft: 70 }}>请填写姓名</div>
                )}
              </div>
              {/* 性别（必填） */}
              <div style={{ padding: '12px 0', borderBottom: '1px solid #f3f4f6' }}>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <span style={{ width: 70, fontSize: 14, color: '#6b7280', flexShrink: 0 }}>
                    <span style={{ color: '#EF4444', marginRight: 2 }}>*</span>性别
                  </span>
                  <div style={{ flex: 1, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                    {['男', '女'].map((o) => (
                      <button key={o} onClick={() => setHeroEditDraft({ ...heroEditDraft, gender: o })}
                        data-testid={`hero-edit-gender-${o}`}
                        style={{ padding: '6px 14px', borderRadius: 14, background: heroEditDraft.gender === o ? T.brand500 : '#f3f4f6', color: heroEditDraft.gender === o ? '#fff' : '#374151', border: 'none', fontSize: 13, cursor: 'pointer' }}>{o}</button>
                    ))}
                  </div>
                </div>
                {genderInvalid && (
                  <div data-testid="hero-edit-gender-err" style={{ fontSize: 11, color: '#EF4444', marginTop: 4, marginLeft: 70 }}>请选择性别</div>
                )}
              </div>
              {/* 生日（必填） */}
              <div style={{ padding: '12px 0', borderBottom: '1px solid #f3f4f6' }}>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <span style={{ width: 70, fontSize: 14, color: '#6b7280', flexShrink: 0 }}>
                    <span style={{ color: '#EF4444', marginRight: 2 }}>*</span>生日
                  </span>
                  <input type="date" value={heroEditDraft.birthday || ''}
                    onChange={(e) => setHeroEditDraft({ ...heroEditDraft, birthday: e.target.value })}
                    max={new Date().toISOString().slice(0, 10)}
                    min="1900-01-01"
                    data-testid="hero-edit-birthday"
                    style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: birthdayInvalid ? '1px solid #EF4444' : '1px solid #d1d5db', fontSize: 14, textAlign: 'right', boxSizing: 'border-box' }} />
                </div>
                {birthdayInvalid && (
                  <div data-testid="hero-edit-birthday-err" style={{ fontSize: 11, color: '#EF4444', marginTop: 4, marginLeft: 70 }}>请选择出生日期</div>
                )}
              </div>
              {/* 身高/体重 同行 */}
              <div style={{ display: 'flex', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid #f3f4f6', gap: 12 }}>
                <span style={{ width: 70, fontSize: 14, color: '#6b7280', flexShrink: 0 }}>身高/体重</span>
                <div style={{ flex: 1, display: 'flex', gap: 8 }}>
                  <input type="number" placeholder="身高cm" value={String(heroEditDraft.height ?? '')} onChange={(e) => setHeroEditDraft({ ...heroEditDraft, height: e.target.value ? Number(e.target.value) : null })}
                    style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 14, textAlign: 'right', boxSizing: 'border-box' }} />
                  <input type="number" placeholder="体重kg" value={String(heroEditDraft.weight ?? '')} onChange={(e) => setHeroEditDraft({ ...heroEditDraft, weight: e.target.value ? Number(e.target.value) : null })}
                    style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 14, textAlign: 'right', boxSizing: 'border-box' }} />
                </div>
              </div>
              {/* 血型 */}
              <div style={{ display: 'flex', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid #f3f4f6' }}>
                <span style={{ width: 70, fontSize: 14, color: '#6b7280', flexShrink: 0 }}>血型</span>
                <div style={{ flex: 1, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  {['A', 'B', 'AB', 'O'].map((o) => (
                    <button key={o} onClick={() => setHeroEditDraft({ ...heroEditDraft, blood_type: o })}
                      style={{ padding: '6px 14px', borderRadius: 14, background: heroEditDraft.blood_type === o ? T.brand500 : '#f3f4f6', color: heroEditDraft.blood_type === o ? '#fff' : '#374151', border: 'none', fontSize: 13, cursor: 'pointer' }}>{o}</button>
                  ))}
                </div>
              </div>
            </div>

            {/* Section 2: Health Info */}
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: T.brand700, marginBottom: 12, paddingBottom: 6, borderBottom: `2px solid ${T.brand100}` }}>
                健康信息
              </div>

              <EditSection title="既往病史（慢病）">
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {CHRONIC_PRESETS.map((c) => {
                    const active = healthInfoDraft.chronic_diseases.some((x) => x.name === c);
                    return (
                      <button
                        key={c}
                        onClick={() => toggleChronic(c)}
                        style={{
                          padding: '6px 12px', borderRadius: 14,
                          background: active ? T.brand500 : '#f3f4f6',
                          color: active ? '#fff' : '#374151',
                          border: 'none', fontSize: 13, cursor: 'pointer',
                        }}
                      >{c}</button>
                    );
                  })}
                </div>
              </EditSection>

              <EditSection title="过敏史">
                <TagsInput label="药物过敏" tags={healthInfoDraft.drug_allergies}
                  onChange={(v) => setHealthInfoDraft({ ...healthInfoDraft, drug_allergies: v })} />
                <TagsInput label="食物过敏" tags={healthInfoDraft.food_allergies}
                  onChange={(v) => setHealthInfoDraft({ ...healthInfoDraft, food_allergies: v })} />
                <TagsInput label="其他过敏（花粉/尘螨等）" tags={healthInfoDraft.other_allergies}
                  onChange={(v) => setHealthInfoDraft({ ...healthInfoDraft, other_allergies: v })} />
              </EditSection>

              <EditSection title="手术史">
                {(healthInfoDraft.surgery_history || []).map((s, idx) => (
                  <div key={idx} data-testid={`prd469-surgery-${idx}`}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '8px 0', borderBottom: '1px solid #f3f4f6' }}>
                    <span style={{ fontSize: 13, color: '#374151' }}>
                      🏥 {s.name}{s.time ? ` (${s.time})` : ''}{s.note ? ` — ${s.note}` : ''}
                    </span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button onClick={() => editSurgeryHistory(idx)}
                        style={{ padding: '4px 8px', border: 'none', background: 'none', color: T.brand500, fontSize: 12, cursor: 'pointer' }}>编辑</button>
                      <button onClick={() => removeSurgeryHistory(idx)}
                        style={{ padding: '4px 8px', border: 'none', background: 'none', color: '#ef4444', fontSize: 12, cursor: 'pointer' }}>删除</button>
                    </div>
                  </div>
                ))}
                <button
                  onClick={() => { setSurgeryForm({ name: '', time: '', note: '' }); setEditingSurgeryIdx(null); setShowAddSurgery(true); }}
                  data-testid="prd469-add-surgery-btn"
                  style={{ marginTop: 8, padding: '8px 16px', borderRadius: 16,
                    background: T.brand100, color: T.brand700, border: 'none', fontSize: 13, cursor: 'pointer' }}>
                  + 添加手术史
                </button>
              </EditSection>

              <EditSection title="家族病史">
                {(healthInfoDraft.family_history || []).map((fh, idx) => (
                  <div key={idx} data-testid={`prd469-family-${idx}`}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '8px 0', borderBottom: '1px solid #f3f4f6' }}>
                    <span style={{ fontSize: 13, color: '#374151' }}>
                      👤 {fh.relation}：{fh.disease}{fh.note ? ` (${fh.note})` : ''}
                    </span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button onClick={() => editFamilyHistory(idx)}
                        style={{ padding: '4px 8px', border: 'none', background: 'none', color: T.brand500, fontSize: 12, cursor: 'pointer' }}>编辑</button>
                      <button onClick={() => removeFamilyHistory(idx)}
                        style={{ padding: '4px 8px', border: 'none', background: 'none', color: '#ef4444', fontSize: 12, cursor: 'pointer' }}>删除</button>
                    </div>
                  </div>
                ))}
                <button
                  onClick={() => { setFamilyForm({ relation: '爸爸', disease: '', note: '' }); setEditingFamilyIdx(null); setShowAddFamily(true); }}
                  data-testid="prd469-add-family-btn"
                  style={{ marginTop: 8, padding: '8px 16px', borderRadius: 16,
                    background: T.brand100, color: T.brand700, border: 'none', fontSize: 13, cursor: 'pointer' }}>
                  + 添加家族病史
                </button>
              </EditSection>

              <EditSection title="个人习惯">
                <HabitRow label="抽烟" value={healthInfoDraft.habit_smoking} options={['有', '无']}
                  onChange={(v) => setHealthInfoDraft({ ...healthInfoDraft, habit_smoking: v })} />
                <HabitRow label="饮酒" value={healthInfoDraft.habit_drinking} options={['有', '无']}
                  onChange={(v) => setHealthInfoDraft({ ...healthInfoDraft, habit_drinking: v })} />
                <HabitRow label="运动频率" value={healthInfoDraft.habit_exercise} options={['无', '偶尔', '经常']}
                  onChange={(v) => setHealthInfoDraft({ ...healthInfoDraft, habit_exercise: v })} />
                <HabitRow label="饮食偏好" value={healthInfoDraft.habit_diet} options={['清淡', '重口味', '素食', '其他']}
                  onChange={(v) => setHealthInfoDraft({ ...healthInfoDraft, habit_diet: v })} />
              </EditSection>
            </div>
          </div>

          <div style={{ padding: 16, borderTop: `1px solid ${T.brand100}`, display: 'flex', gap: 12 }}>
            <button onClick={() => setShowHeroEdit(false)}
              style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: '#fff', border: `1px solid ${T.brand200}`, fontSize: 15, fontWeight: 600 }}>取消</button>
            <button
              onClick={saveAll}
              data-testid="prd469-hero-save"
              disabled={!requiredAllOk}
              style={{
                flex: 1, padding: '12px 0', borderRadius: 24,
                background: requiredAllOk ? T.brand500 : '#CBD5E1',
                color: '#fff', border: 'none', fontSize: 15, fontWeight: 600,
                cursor: requiredAllOk ? 'pointer' : 'not-allowed',
              }}
            >保存</button>
          </div>
        </div>
      </div>
    );
  };

  // ─── Sub-modals: Family History + Surgery History ───────────────

  const renderFamilyFormModal = () => {
    if (!showAddFamily) return null;
    return (
      <div
        data-testid="prd469-family-form-modal"
        style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          zIndex: 110, display: 'flex', alignItems: 'flex-end',
        }}
      >
        <div style={{ background: '#fff', width: '100%', borderTopLeftRadius: 16, borderTopRightRadius: 16 }}>
          <div style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${T.brand100}` }}>
            <span style={{ fontSize: 17, fontWeight: 700 }}>{editingFamilyIdx !== null ? '编辑家族病史' : '添加家族病史'}</span>
            <span onClick={() => setShowAddFamily(false)} style={{ fontSize: 22, color: '#9ca3af', cursor: 'pointer' }}>×</span>
          </div>
          <div style={{ padding: 16 }}>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>与您的关系</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {FAMILY_RELATIONS.map((r) => (
                  <button key={r} onClick={() => setFamilyForm({ ...familyForm, relation: r })}
                    style={{ padding: '6px 12px', borderRadius: 14,
                      background: familyForm.relation === r ? T.brand500 : '#f3f4f6',
                      color: familyForm.relation === r ? '#fff' : '#374151',
                      border: 'none', fontSize: 13, cursor: 'pointer' }}>
                    {r}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>疾病名称</div>
              <input type="text" value={familyForm.disease}
                onChange={(e) => setFamilyForm({ ...familyForm, disease: e.target.value })}
                placeholder="如：高血压"
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e5e7eb', fontSize: 14, boxSizing: 'border-box' }} />
            </div>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>备注（可选）</div>
              <input type="text" value={familyForm.note}
                onChange={(e) => setFamilyForm({ ...familyForm, note: e.target.value })}
                placeholder="如：确诊于2020年"
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e5e7eb', fontSize: 14, boxSizing: 'border-box' }} />
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              <button onClick={() => setShowAddFamily(false)}
                style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: '#fff', border: `1px solid ${T.brand200}`, fontSize: 15, fontWeight: 600 }}>取消</button>
              <button onClick={addFamilyHistory} data-testid="prd469-save-family"
                style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: T.brand500, color: '#fff', border: 'none', fontSize: 15, fontWeight: 600 }}>保存</button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderSurgeryFormModal = () => {
    if (!showAddSurgery) return null;
    return (
      <div
        data-testid="prd469-surgery-form-modal"
        style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          zIndex: 110, display: 'flex', alignItems: 'flex-end',
        }}
      >
        <div style={{ background: '#fff', width: '100%', borderTopLeftRadius: 16, borderTopRightRadius: 16 }}>
          <div style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${T.brand100}` }}>
            <span style={{ fontSize: 17, fontWeight: 700 }}>{editingSurgeryIdx !== null ? '编辑手术史' : '添加手术史'}</span>
            <span onClick={() => setShowAddSurgery(false)} style={{ fontSize: 22, color: '#9ca3af', cursor: 'pointer' }}>×</span>
          </div>
          <div style={{ padding: 16 }}>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>手术名称</div>
              <input type="text" value={surgeryForm.name}
                onChange={(e) => setSurgeryForm({ ...surgeryForm, name: e.target.value })}
                placeholder="如：阑尾切除术"
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e5e7eb', fontSize: 14, boxSizing: 'border-box' }} />
            </div>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>手术时间</div>
              <input type="date" value={surgeryForm.time}
                onChange={(e) => setSurgeryForm({ ...surgeryForm, time: e.target.value })}
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e5e7eb', fontSize: 14, boxSizing: 'border-box' }} />
            </div>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>备注（可选）</div>
              <input type="text" value={surgeryForm.note}
                onChange={(e) => setSurgeryForm({ ...surgeryForm, note: e.target.value })}
                placeholder="如：恢复良好"
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e5e7eb', fontSize: 14, boxSizing: 'border-box' }} />
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              <button onClick={() => setShowAddSurgery(false)}
                style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: '#fff', border: `1px solid ${T.brand200}`, fontSize: 15, fontWeight: 600 }}>取消</button>
              <button onClick={addSurgeryHistory} data-testid="prd469-save-surgery"
                style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: T.brand500, color: '#fff', border: 'none', fontSize: 15, fontWeight: 600 }}>保存</button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // ─── Main render ────────────────────────────────────────────────

  return (
    <div data-testid="health-profile-page" style={{ background: BH_TOKENS.bgPage, minHeight: '100vh', paddingBottom: 80, position: 'relative' }}>
      {/* Sticky top: title + member bar */}
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
      {selectedMember && (
        <div style={{ padding: '0 16px 8px' }}>
          <div
            data-testid="health-dashboard-entry"
            onClick={() => router.push(`/health-dashboard?member_id=${selectedMemberId}`)}
            style={{
              background: 'linear-gradient(135deg, #0EA5E9 0%, #38BDF8 100%)',
              color: '#fff',
              fontSize: 15,
              fontWeight: 700,
              height: 42,
              borderRadius: 21,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: '0 4px 12px rgba(14,165,233,0.35)',
            }}
          >
            {selectedMember.is_self ? '查看我的健康看板 →' : `查看 ${selectedMember.nickname || '家人'} 的健康看板 →`}
          </div>
        </div>
      )}
      {renderInviteArea()}
      {renderDualCards()}
      {renderAlertBanner()}
      {/* 提醒管理入口 */}
      <div style={{ padding: '0 16px 12px' }}>
        <div
          data-testid="health-reminders-entry"
          onClick={() => router.push(`/health-reminders?member_id=${selectedMemberId || ''}`)}
          style={{
            background: '#fff',
            borderRadius: 12,
            padding: '14px 16px',
            display: 'flex',
            alignItems: 'center',
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            cursor: 'pointer',
            borderLeft: '4px solid #F59E0B',
          }}
        >
          <span style={{ fontSize: 20, marginRight: 10 }}>🔔</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#1F2937' }}>提醒管理</div>
            <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>复诊·体检·复查提醒</div>
          </div>
          <span style={{ fontSize: 14, color: '#9CA3AF' }}>›</span>
        </div>
      </div>
      {renderDevicesEntry()}
      {renderMedicationPlan()}
      {renderMedicalRecords()}
      {renderTodayHealthData()}

      {/* Modals */}
      {showAddMember && (
        <NewFamilyMemberModal
          onClose={() => setShowAddMember(false)}
          onSuccess={() => {
            setShowAddMember(false);
            fetchMembers();
            showToast('已添加家庭成员');
          }}
        />
      )}

      {renderHeroEditModal()}
      {renderFamilyFormModal()}
      {renderSurgeryFormModal()}
      {renderRecordDrawer()}
      {renderTaGuardianReadonlyDrawer()}

      {/* [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 本人资料完善弹窗 */}
      {showSelfCompleteDialog && (
        <div
          data-testid="self-complete-dialog"
          style={{
            position: 'fixed', inset: 0, zIndex: 3000,
            background: 'rgba(15,23,42,0.55)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 24,
          }}
          onClick={() => {
            // [BUG_FIX 2026-05-29] 点击遮罩关闭：标记本会话已弹过，避免再次进入又弹
            try {
              if (typeof window !== 'undefined' && window.sessionStorage) {
                sessionStorage.setItem(SELF_COMPLETE_DIALOG_SHOWN_KEY, '1');
              }
            } catch { /* ignore */ }
            setShowSelfCompleteDialog(false);
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '100%', maxWidth: 340, background: '#fff',
              borderRadius: 16, padding: '22px 20px 18px',
              boxShadow: '0 12px 40px rgba(2,132,199,0.25)',
              position: 'relative',
            }}
          >
            <span
              data-testid="self-complete-dialog-close"
              onClick={() => {
                try {
                  if (typeof window !== 'undefined' && window.sessionStorage) {
                    sessionStorage.setItem(SELF_COMPLETE_DIALOG_SHOWN_KEY, '1');
                  }
                  if (typeof window !== 'undefined' && window.localStorage) {
                    localStorage.setItem(
                      SELF_COMPLETE_DIALOG_SNOOZE_UNTIL_KEY,
                      String(Date.now() + 24 * 3600 * 1000),
                    );
                  }
                } catch { /* ignore */ }
                setShowSelfCompleteDialog(false);
              }}
              style={{
                position: 'absolute', top: 8, right: 12,
                fontSize: 24, color: '#94A3B8', cursor: 'pointer',
                userSelect: 'none', lineHeight: 1,
              }}
            >×</span>
            <div style={{
              fontSize: 17, fontWeight: 700, color: '#0F172A',
              marginBottom: 10, textAlign: 'center',
            }}>完善健康档案</div>
            <div style={{
              fontSize: 13, color: '#475569', lineHeight: 1.6,
              marginBottom: 18, textAlign: 'center',
            }}>
              为了给您提供更精准的健康服务，请先完善您的基本资料（姓名、性别、出生日期）。
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              <button
                data-testid="self-complete-dialog-later"
                onClick={() => {
                  // [BUG_FIX 2026-05-29] 暂不填写：会话级标记 + 24h 软抑制
                  try {
                    if (typeof window !== 'undefined' && window.sessionStorage) {
                      sessionStorage.setItem(SELF_COMPLETE_DIALOG_SHOWN_KEY, '1');
                    }
                    if (typeof window !== 'undefined' && window.localStorage) {
                      localStorage.setItem(
                        SELF_COMPLETE_DIALOG_SNOOZE_UNTIL_KEY,
                        String(Date.now() + 24 * 3600 * 1000),
                      );
                    }
                  } catch { /* ignore */ }
                  setShowSelfCompleteDialog(false);
                }}
                style={{
                  flex: 1, height: 42, borderRadius: 21,
                  background: '#F1F5F9', color: '#0F172A',
                  border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
                }}
              >稍后</button>
              <button
                data-testid="self-complete-dialog-go"
                onClick={() => {
                  setShowSelfCompleteDialog(false);
                  setShowSelfCompleteDrawer(true);
                }}
                style={{
                  flex: 1, height: 42, borderRadius: 21,
                  background: 'linear-gradient(135deg, #38BDF8, #0284C7)',
                  color: '#fff', border: 'none',
                  fontSize: 14, fontWeight: 700, cursor: 'pointer',
                  boxShadow: '0 4px 12px rgba(2,132,199,0.3)',
                }}
              >去完善</button>
            </div>
          </div>
        </div>
      )}

      {/* [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 完善健康档案抽屉 */}
      {showSelfCompleteDrawer && (
        <CompleteSelfProfileDrawer
          initial={selfInitialForDrawer}
          onClose={() => setShowSelfCompleteDrawer(false)}
          onSuccess={async () => {
            // [BUG_FIX 2026-05-29] 完善成功后：立即关闭弹窗触发条件 + 永久标记本会话已弹
            setShowSelfCompleteDrawer(false);
            setSelfNeedComplete(false);
            setSelfMissingFields([]);
            try {
              if (typeof window !== 'undefined' && window.sessionStorage) {
                sessionStorage.setItem(SELF_COMPLETE_DIALOG_SHOWN_KEY, '1');
              }
              if (typeof window !== 'undefined' && window.localStorage) {
                localStorage.removeItem(SELF_COMPLETE_DIALOG_SNOOZE_UNTIL_KEY);
              }
            } catch { /* ignore */ }
            await fetchMembers();
            if (selectedMemberId) await fetchProfile(selectedMemberId);
            await fetchSelfNeedComplete();
          }}
        />
      )}
    </div>
  );
}

// ─── Helper Components ────────────────────────────────────────────

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

function EditSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: '#15803d', marginBottom: 10 }}>{title}</div>
      {children}
    </div>
  );
}

function HabitRow({ label, value, options, onChange }: {
  label: string; value?: string; options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #f3f4f6' }}>
      <span style={{ width: 80, fontSize: 14, color: '#374151' }}>{label}</span>
      <div style={{ flex: 1, display: 'flex', gap: 8 }}>
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            style={{
              padding: '4px 10px', borderRadius: 10,
              background: value === opt ? T.brand500 : '#f3f4f6',
              color: value === opt ? '#fff' : '#374151',
              border: 'none', fontSize: 13, cursor: 'pointer',
            }}
          >{opt}</button>
        ))}
      </div>
    </div>
  );
}

function TagsInput({ label, tags, onChange }: {
  label: string; tags: string[]; onChange: (v: string[]) => void;
}) {
  const [val, setVal] = useState('');
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>{label}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
        {tags.map((t, i) => (
          <span
            key={i}
            style={{
              padding: '4px 10px', borderRadius: 12,
              background: T.brand100, color: T.brand700, fontSize: 13,
            }}
          >
            {t}
            <span
              onClick={() => onChange(tags.filter((_, j) => j !== i))}
              style={{ marginLeft: 6, cursor: 'pointer', color: '#9ca3af' }}
            >×</span>
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          type="text" value={val} onChange={(e) => setVal(e.target.value)}
          placeholder="输入后点击添加"
          style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: `1px solid ${T.brand200}`, fontSize: 13 }}
        />
        <button
          onClick={() => { if (val.trim()) { onChange([...tags, val.trim()]); setVal(''); } }}
          style={{ padding: '8px 16px', borderRadius: 8, background: T.brand500, color: '#fff', border: 'none', fontSize: 13 }}
        >添加</button>
      </div>
    </div>
  );
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

// ─── Default Export with Suspense ─────────────────────────────────

export default function HealthProfileV2Page() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>加载中…</div>}>
      <HealthProfileV2PageInner />
    </Suspense>
  );
}
