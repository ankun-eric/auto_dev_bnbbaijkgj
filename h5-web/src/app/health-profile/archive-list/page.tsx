'use client';

/**
 * [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29] 健康档案 - 档案列表（v2 状态机版）
 *
 * 核心特性：
 * - 7 种状态卡片渲染（S0~S7），统一标签颜色 + 主按钮 + 次操作
 * - 入口收口：废弃顶部「去邀请」大按钮；新建档案后弹「立即去邀请」抽屉
 * - 统一删除接口：DELETE /api/family/member/{member_id}，返回结构化 reason_code
 * - 配额展示：「已管理 {X} 人 / 上限 {Y} 人，还可添加 {Y-X} 人」
 */

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Popup, Toast } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
// [PRD-INVITE-FAMILY-CARD-V1.1 2026-05-30] 健康档案位接入「邀请家人入口卡片」
import InviteFamilyCard from '@/app/member-center/components/InviteFamilyCard';

// ───────────── 类型 ─────────────

type MemberState = 'S0' | 'S1' | 'S2' | 'S3' | 'S4' | 'S5' | 'S6' | 'S7';

interface MemberStateItem {
  member_id: number;
  state: MemberState;
  state_label: string;
  state_color: string;
  primary_action: 'view_profile' | 'invite' | 'view_invite_code' | 'reinvite';
  nickname?: string;
  relationship_type?: string;
  is_self: boolean;
  avatar_color_index: number;
  invite_code?: string;
  invite_expires_at?: string;
  invite_remaining_hours?: number;
  can_delete: boolean;
  delete_block_reason?: string;
  can_unbind: boolean;
  invitation_count: number;
  created_at?: string;
}

interface StateListResp {
  items: MemberStateItem[];
  total: number;
  quota_used: number;
  quota_max: number;
  quota_remaining: number;
  guarded_count: number;
  state_counts: Record<MemberState, number>;
}

// ───────────── 配色 ─────────────

const STATE_COLOR_MAP: Record<string, { bg: string; border: string; text: string }> = {
  blue: { bg: '#E0F2FE', border: '#7DD3FC', text: '#0369A1' },
  green: { bg: '#DCFCE7', border: '#86EFAC', text: '#15803D' },
  gray: { bg: '#F1F5F9', border: '#CBD5E1', text: '#64748B' },
  orange: { bg: '#FFEDD5', border: '#FDBA74', text: '#C2410C' },
  red: { bg: '#FEE2E2', border: '#FCA5A5', text: '#B91C1C' },
  lightgray: { bg: '#F5F5F5', border: '#E5E7EB', text: '#94A3B8' },
};

// [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #4 #5]
// - 主色 PRIMARY_COLOR 由 #0EA5E9（青蓝）统一为 #1677FF（产品蓝），用于所有平铺胶囊按钮
// - 页面背景由 #F0F9FF 改为 #F5F7FA 浅灰，与白色卡片形成清晰层次
const PRIMARY_COLOR = '#1677FF';
const ACCENT_COLOR = '#FFB800';
const TEXT_PRIMARY = '#0F172A';
const TEXT_SECONDARY = '#64748B';
const PAGE_BG = '#F5F7FA';
const DANGER = '#EF4444';

const AVATAR_COLORS = ['#0EA5E9', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];

// ───────────── 按钮文案规范 ─────────────

const PRIMARY_ACTION_LABEL: Record<string, string> = {
  view_profile: '查看档案',
  invite: '去邀请',
  view_invite_code: '查看邀请码',
  reinvite: '重新邀请',
};

// ───────────── 新建档案 + 立即邀请抽屉 ─────────────

interface NewMemberDrawerProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (newMemberId: number, action: 'invite_now' | 'skip') => void;
}

function NewMemberDrawer({ open, onClose, onSuccess }: NewMemberDrawerProps) {
  const [nickname, setNickname] = useState('');
  const [relation, setRelation] = useState('');
  const [phone, setPhone] = useState('');
  const [gender, setGender] = useState<'male' | 'female' | ''>('');
  const [step, setStep] = useState<'form' | 'invite_choice'>('form');
  const [newMemberId, setNewMemberId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setNickname('');
      setRelation('');
      setPhone('');
      setGender('');
      setStep('form');
      setNewMemberId(null);
    }
  }, [open]);

  const handleCreate = async () => {
    const n = nickname.trim();
    if (!n) {
      showToast('请输入姓名', 'fail');
      return;
    }
    if (!relation.trim()) {
      showToast('请输入关系', 'fail');
      return;
    }
    if (!phone.trim()) {
      showToast('请输入手机号', 'fail');
      return;
    }
    if (!gender) {
      showToast('请选择性别', 'fail');
      return;
    }
    setSubmitting(true);
    try {
      const body: any = {
        nickname: n,
        relationship_type: relation.trim(),
        gender,
      };
      const res: any = await api.post('/api/family/members', body);
      const data = res.data || res;
      setNewMemberId(data.id);
      setStep('invite_choice');
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      let msg = '新建档案失败';
      if (typeof detail === 'string') msg = detail;
      else if (detail?.message) msg = detail.message;
      showToast(msg, 'fail');
    } finally {
      setSubmitting(false);
    }
  };

  const handleChoice = (choice: 'invite_now' | 'skip') => {
    if (newMemberId) {
      onSuccess(newMemberId, choice);
    }
    onClose();
  };

  return (
    <Popup
      visible={open}
      onMaskClick={onClose}
      position='bottom'
      bodyStyle={{ borderTopLeftRadius: 20, borderTopRightRadius: 20, minHeight: '50vh' }}
    >
      <div data-testid='new-member-drawer' style={{ padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 17, fontWeight: 700, color: TEXT_PRIMARY }}>
            {step === 'form' ? '新建档案' : '立即去邀请？'}
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, color: TEXT_SECONDARY, cursor: 'pointer' }}>
            ×
          </button>
        </div>

        {step === 'form' && (
          <>
            <div style={{ marginBottom: 14 }}>
              <Label text='姓名' required />
              <Input value={nickname} onChange={setNickname} placeholder='如：张妈妈 / 李叔叔' maxLength={20} />
            </div>
            <div style={{ marginBottom: 14 }}>
              <Label text='与本人关系' required />
              <Input value={relation} onChange={setRelation} placeholder='如：父亲 / 母亲 / 配偶 / 子女' />
            </div>
            <div style={{ marginBottom: 14 }}>
              <Label text='手机号' required />
              <Input value={phone} onChange={setPhone} placeholder='11 位手机号' maxLength={11} />
            </div>
            <div style={{ marginBottom: 20 }}>
              <Label text='性别' required />
              <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
                {(['male', 'female'] as const).map((g) => (
                  <button
                    key={g}
                    onClick={() => setGender(g)}
                    style={{
                      flex: 1,
                      padding: '10px',
                      borderRadius: 10,
                      border: `1px solid ${gender === g ? PRIMARY_COLOR : '#E2E8F0'}`,
                      background: gender === g ? '#E0F2FE' : '#FFF',
                      color: gender === g ? PRIMARY_COLOR : TEXT_PRIMARY,
                      fontSize: 14,
                      cursor: 'pointer',
                    }}
                  >
                    {g === 'male' ? '男' : '女'}
                  </button>
                ))}
              </div>
            </div>
            <button
              disabled={submitting}
              onClick={handleCreate}
              data-testid='new-member-submit-btn'
              style={primaryBtnStyle(submitting)}
            >
              {submitting ? '保存中…' : '保存档案'}
            </button>
          </>
        )}

        {step === 'invite_choice' && (
          <>
            <div style={{
              padding: '20px 16px',
              background: '#F0F9FF',
              borderRadius: 12,
              marginBottom: 20,
              fontSize: 14,
              color: TEXT_PRIMARY,
              lineHeight: 1.6,
            }}>
              档案「{nickname}」已创建成功。
              <br />
              是否立即邀请 TA 接受守护邀请？
              <br />
              （您也可以稍后在档案列表中重新邀请）
            </div>
            <button
              onClick={() => handleChoice('invite_now')}
              data-testid='choice-invite-now'
              style={primaryBtnStyle(false)}
            >
              立即邀请
            </button>
            <button
              onClick={() => handleChoice('skip')}
              data-testid='choice-skip'
              style={{
                ...secondaryBtnStyle(),
                width: '100%',
                marginTop: 10,
              }}
            >
              暂不邀请
            </button>
          </>
        )}
      </div>
    </Popup>
  );
}

// ───────────── 邀请码展示抽屉 ─────────────

interface InviteCodeDrawerProps {
  open: boolean;
  inviteCode?: string;
  expiresAt?: string;
  remainingHours?: number;
  memberName?: string;
  onClose: () => void;
}

function InviteCodeDrawer({ open, inviteCode, expiresAt, remainingHours, memberName, onClose }: InviteCodeDrawerProps) {
  const qrUrl = inviteCode
    ? `https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-auth?code=${inviteCode}`
    : '';
  return (
    <Popup
      visible={open}
      onMaskClick={onClose}
      position='bottom'
      bodyStyle={{ borderTopLeftRadius: 20, borderTopRightRadius: 20, minHeight: '50vh' }}
    >
      <div style={{ padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 17, fontWeight: 700, color: TEXT_PRIMARY }}>邀请码</div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, color: TEXT_SECONDARY, cursor: 'pointer' }}>×</button>
        </div>
        {memberName && (
          <div style={{ marginBottom: 16, fontSize: 14, color: TEXT_SECONDARY }}>
            发送给：<span style={{ color: TEXT_PRIMARY, fontWeight: 600 }}>{memberName}</span>
          </div>
        )}
        <div style={{ padding: '16px', background: '#F1F5F9', borderRadius: 10, marginBottom: 12, wordBreak: 'break-all' }}>
          <div style={{ fontSize: 12, color: TEXT_SECONDARY, marginBottom: 6 }}>邀请码</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: TEXT_PRIMARY, fontFamily: 'monospace' }}>{inviteCode}</div>
        </div>
        <div style={{ padding: '16px', background: '#F1F5F9', borderRadius: 10, marginBottom: 12, wordBreak: 'break-all' }}>
          <div style={{ fontSize: 12, color: TEXT_SECONDARY, marginBottom: 6 }}>分享链接</div>
          <div style={{ fontSize: 12, color: PRIMARY_COLOR, fontFamily: 'monospace' }}>{qrUrl}</div>
        </div>
        {remainingHours !== undefined && remainingHours !== null && (
          <div style={{ fontSize: 12, color: TEXT_SECONDARY, marginBottom: 16 }}>
            剩余 {remainingHours} 小时过期
          </div>
        )}
        <button
          onClick={() => {
            if (navigator.clipboard && qrUrl) {
              navigator.clipboard.writeText(qrUrl);
              showToast('链接已复制', 'success');
            }
          }}
          style={primaryBtnStyle(false)}
        >
          复制邀请链接
        </button>
      </div>
    </Popup>
  );
}

// ───────────── 删除确认抽屉 ─────────────

interface DeleteConfirmProps {
  open: boolean;
  member: MemberStateItem | null;
  onClose: () => void;
  onConfirm: () => void;
}

function DeleteConfirmDrawer({ open, member, onClose, onConfirm }: DeleteConfirmProps) {
  if (!member) return null;
  return (
    <Popup visible={open} onMaskClick={onClose} position='bottom' bodyStyle={{ borderTopLeftRadius: 20, borderTopRightRadius: 20 }}>
      <div style={{ padding: 20 }}>
        <div style={{ fontSize: 17, fontWeight: 700, color: TEXT_PRIMARY, marginBottom: 12 }}>删除档案</div>
        <div style={{ fontSize: 14, color: TEXT_SECONDARY, lineHeight: 1.6, marginBottom: 20 }}>
          确认删除「{member.nickname}」的档案吗？
          <br />
          删除后将清空该档案下的所有健康数据，无法恢复。
        </div>
        <button onClick={onConfirm} style={{ ...primaryBtnStyle(false), background: DANGER, boxShadow: '0 4px 12px rgba(239,68,68,0.3)' }}>
          确认删除
        </button>
        <button onClick={onClose} style={{ ...secondaryBtnStyle(), width: '100%', marginTop: 10 }}>取消</button>
      </div>
    </Popup>
  );
}

// ───────────── 更多操作菜单 ─────────────

interface MoreMenuProps {
  open: boolean;
  member: MemberStateItem | null;
  onClose: () => void;
  onAction: (action: 'delete' | 'unbind' | 'cancel_invite' | 'invitation_history') => void;
}

function MoreMenu({ open, member, onClose, onAction }: MoreMenuProps) {
  if (!member) return null;

  const items: { key: 'delete' | 'unbind' | 'cancel_invite' | 'invitation_history'; label: string; color?: string; show: boolean }[] = [
    {
      key: 'delete',
      label: '删除',
      color: DANGER,
      show: !['S0', 'S1', 'S3'].includes(member.state),
    },
    {
      key: 'unbind',
      label: '解除守护',
      color: DANGER,
      show: member.state === 'S1',
    },
    {
      key: 'cancel_invite',
      label: '取消邀请',
      color: DANGER,
      show: member.state === 'S3',
    },
    {
      key: 'invitation_history',
      label: '邀请记录',
      show: member.invitation_count > 0,
    },
  ].filter((x) => x.show);

  return (
    <Popup visible={open} onMaskClick={onClose} position='bottom' bodyStyle={{ borderTopLeftRadius: 20, borderTopRightRadius: 20 }}>
      <div style={{ padding: '16px 0' }}>
        <div style={{ padding: '0 20px 12px', fontSize: 16, fontWeight: 600, color: TEXT_PRIMARY }}>
          {member.nickname} · 更多操作
        </div>
        {items.map((it) => (
          <button
            key={it.key}
            onClick={() => {
              onAction(it.key);
              onClose();
            }}
            style={{
              width: '100%',
              padding: '14px 20px',
              border: 'none',
              borderTop: '1px solid #F1F5F9',
              background: 'transparent',
              fontSize: 15,
              color: it.color || TEXT_PRIMARY,
              textAlign: 'left',
              cursor: 'pointer',
            }}
          >
            {it.label}
          </button>
        ))}
        {items.length === 0 && (
          <div style={{ padding: '20px', textAlign: 'center', color: TEXT_SECONDARY, fontSize: 13 }}>
            该状态下暂无可用操作
          </div>
        )}
        <button
          onClick={onClose}
          style={{
            width: '100%',
            padding: '14px 20px',
            border: 'none',
            borderTop: '8px solid #F8FAFC',
            background: 'transparent',
            fontSize: 15,
            color: TEXT_SECONDARY,
            cursor: 'pointer',
          }}
        >
          取消
        </button>
      </div>
    </Popup>
  );
}

// ───────────── 主页面 ─────────────

export default function ArchiveListPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [list, setList] = useState<StateListResp | null>(null);
  const [newMemberOpen, setNewMemberOpen] = useState(false);
  const [moreMenuMember, setMoreMenuMember] = useState<MemberStateItem | null>(null);
  const [deleteMember, setDeleteMember] = useState<MemberStateItem | null>(null);
  const [inviteCodeView, setInviteCodeView] = useState<MemberStateItem | null>(null);
  // [PRD-INVITE-FAMILY-CARD-V1.1 2026-05-30 §3] 健康档案位「邀请家人入口卡片」所需套餐名
  // 来源 /api/member/center -> current.plan_name；接口失败时兜底为空（卡片内部走 '会员套餐' 兜底文案）
  const [planName, setPlanName] = useState<string>('');
  useEffect(() => {
    let aborted = false;
    (async () => {
      try {
        const res: any = await api.get('/api/member/center');
        if (aborted) return;
        const data = res?.data || res;
        const name = data?.current?.plan_name || data?.current_plan?.name || data?.plan_name || '';
        if (typeof name === 'string') setPlanName(name);
      } catch {
        // 失败兜底为空，卡片会显示「会员套餐 · 可管理 N 位家人」
      }
    })();
    return () => { aborted = true; };
  }, []);

  // [BUGFIX archive-list 404 2026-05-30] 兜底优化：
  // - 接口 404 时不再裸露英文 "Not Found"，统一中文友好提示
  // - 网络错误 / 5xx 等给出统一的中文提示
  // - 失败时清空 list，让页面进入「暂无档案」空态而非停留 loading
  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/family/member/state/list');
      const raw: StateListResp | null = (res.data || res) as StateListResp;
      // [BUG_FIX-FAMILY-NICKNAME-NOTNULL-20260530 H5 兜底]
      // 即使后端历史脏数据漏过，前端也强制过滤掉「姓名为空 / NULL / 纯空格」的档案，
      // 双保险，避免用户看到无名档案。
      if (raw && Array.isArray(raw.items)) {
        const filtered = raw.items.filter(
          (m) => m && typeof m.nickname === 'string' && m.nickname.trim().length > 0,
        );
        const removed = raw.items.length - filtered.length;
        setList({
          ...raw,
          items: filtered,
          total: typeof raw.total === 'number' ? Math.max(0, raw.total - removed) : filtered.length,
        });
      } else {
        setList(raw);
      }
    } catch (e: any) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
      let msg = '加载失败，请稍后重试';
      if (status === 404) {
        msg = '档案数据接口暂不可用，请稍后重试';
      } else if (status === 401 || status === 403) {
        msg = '登录已过期，请重新登录';
      } else if (typeof detail === 'string' && detail && !/not\s*found/i.test(detail)) {
        msg = detail;
      } else if (typeof detail === 'object' && detail?.message) {
        msg = String(detail.message);
      }
      showToast(msg, 'fail');
      setList(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // 处理新建档案后选择
  const handleNewMemberSuccess = async (memberId: number, choice: 'invite_now' | 'skip') => {
    await fetchList();
    if (choice === 'invite_now') {
      try {
        const res: any = await api.post(`/api/family/member/${memberId}/invite`, {});
        const data = res.data || res;
        await fetchList();
        // 找到新邀请并展示
        const updated = await api.get('/api/family/member/state/list');
        const u: any = updated.data || updated;
        const newMember = u.items.find((x: MemberStateItem) => x.member_id === memberId);
        if (newMember) {
          setInviteCodeView(newMember);
        }
      } catch (e: any) {
        showToast('邀请创建失败', 'fail');
      }
    }
  };

  // 卡片主按钮点击
  const handlePrimaryAction = async (m: MemberStateItem) => {
    if (m.primary_action === 'view_profile') {
      // 跳转档案详情（如有）
      router.push(`/health-profile?member_id=${m.member_id}`);
      return;
    }
    if (m.primary_action === 'invite') {
      // S2 → 调发邀请接口
      try {
        await api.post(`/api/family/member/${m.member_id}/invite`, {});
        await fetchList();
        showToast('邀请已创建', 'success');
        // 重新拉取并展示邀请码
        const updated: any = await api.get('/api/family/member/state/list');
        const u = updated.data || updated;
        const newMember = u.items.find((x: MemberStateItem) => x.member_id === m.member_id);
        if (newMember) setInviteCodeView(newMember);
      } catch (e: any) {
        showToast(e?.response?.data?.detail || '邀请失败', 'fail');
      }
      return;
    }
    if (m.primary_action === 'view_invite_code') {
      setInviteCodeView(m);
      return;
    }
    if (m.primary_action === 'reinvite') {
      try {
        const res: any = await api.post(`/api/family/member/${m.member_id}/invite`, {});
        await fetchList();
        showToast('已重新发起邀请', 'success');
        const updated: any = await api.get('/api/family/member/state/list');
        const u = updated.data || updated;
        const newMember = u.items.find((x: MemberStateItem) => x.member_id === m.member_id);
        if (newMember) setInviteCodeView(newMember);
      } catch (e: any) {
        showToast(e?.response?.data?.detail || '重新邀请失败', 'fail');
      }
      return;
    }
  };

  // 删除操作
  const handleDelete = async (m: MemberStateItem) => {
    try {
      const res: any = await api.delete(`/api/family/member/${m.member_id}`);
      const data = res.data || res;
      showToast('已删除', 'success');
      setDeleteMember(null);
      await fetchList();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      let msg = '删除失败';
      if (typeof detail === 'object' && detail?.message) msg = detail.message;
      else if (typeof detail === 'string') msg = detail;
      showToast(msg, 'fail');
    }
  };

  // 解除守护
  const handleUnbind = async (m: MemberStateItem) => {
    try {
      await api.post(`/api/family/member/${m.member_id}/unbind`, {});
      showToast('已解除守护', 'success');
      await fetchList();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      let msg = '解除失败';
      if (typeof detail === 'string') msg = detail;
      else if (detail?.message) msg = detail.message;
      showToast(msg, 'fail');
    }
  };

  // 取消邀请
  const handleCancelInvite = async (m: MemberStateItem) => {
    if (!m.invite_code) return;
    try {
      await api.post('/api/guardian/v13/family/invite/cancel', { invite_code: m.invite_code });
      showToast('已取消邀请', 'success');
      await fetchList();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '取消失败', 'fail');
    }
  };

  // [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29 排版修复]
  // 邀请记录跳转——改为本页内抽屉，避免依赖已下线的 i-guard 页面
  const [invitationHistoryMember, setInvitationHistoryMember] = useState<MemberStateItem | null>(null);
  const handleViewInvitationHistory = (m: MemberStateItem) => {
    setInvitationHistoryMember(m);
  };

  // [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29 PRD §3.1 验收 8.1#5]
  // 本人卡 S0 的「AI 外呼额度」抽屉入口
  const [aiQuotaOpen, setAiQuotaOpen] = useState(false);

  return (
    <div style={{ minHeight: '100vh', background: PAGE_BG, paddingBottom: 100 }}>
      <GreenNavBar title='档案列表' onBack={() => router.back()} />

      {/* [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #2]
          删除「本套餐可管理 X 人」横条 —— 顶部入口卡片已展示「已管理 X/Y」，此处冗余。
          DOM 节点一并移除，避免留白。 */}

      {/* [PRD-INVITE-FAMILY-CARD-V1.1 2026-05-30 §3.1] 健康档案位概览块完整替换为「邀请家人入口卡片」
          删除清单（橙圈 ①~⑤）：
            ① 📋 档案列表标题；② "已管理 X / 上限 Y"大字；③ "还可添加 X 人"小字；
            ④ 右侧黄色「+ 新增」按钮；⑤ 外层白色概览卡片容器
          主按钮"邀请家人"点击动作 = 拉起「新增家人档案」抽屉（沿用线上原"+ 新增"抽屉，BR-10）
          达上限态时按钮禁用、抽屉不弹出（BR-14）；「升级套餐」跳回会员中心套餐档位区 */}
      {list && (
        <InviteFamilyCard
          planName={planName}
          quotaMax={list.quota_max}
          quotaUsed={list.quota_used}
          cardLocation='profile_list_top'
          onInvite={() => {
            // 与原"+ 新增"按钮的行为对齐：满额时不弹抽屉（按钮禁用层已拦截，此处为二重保险）
            const unlimited = list.quota_max === -1 || list.quota_max >= 9999;
            if (!unlimited && list.quota_remaining <= 0) return;
            setNewMemberOpen(true);
          }}
          onUpgrade={() => {
            // BR-14 §3.3：升级套餐链接跳回会员中心套餐档位区
            router.push('/member-center');
          }}
        />
      )}

      {/* 注意：不再有「去邀请」大按钮（入口 B 已删除） */}

      {/* 卡片列表 */}
      {/* [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #4]
          顶部蓝色会员卡片与下方本人/成员卡之间额外保留 16px 纵向间距（paddingTop:16），
          配合页面浅灰底色 #F5F7FA + 卡片白色背景，形成清晰层次，告别"挤成一团"。 */}
      <div style={{ padding: '16px 12px 0' }}>
        {loading && <div style={{ padding: 40, textAlign: 'center', color: TEXT_SECONDARY }}>加载中…</div>}
        {!loading && list?.items.map((m) => (
          <MemberCard
            key={m.member_id}
            member={m}
            onPrimaryAction={() => handlePrimaryAction(m)}
            // [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #5]
            // 平铺次要按钮直接派发动作，不再走 MoreMenu 折叠抽屉。
            onMoreMenu={(action) => {
              if (action === 'delete') {
                setDeleteMember(m);
              } else if (action === 'unbind') {
                handleUnbind(m);
              } else if (action === 'cancel_invite') {
                handleCancelInvite(m);
              } else if (action === 'invitation_history') {
                handleViewInvitationHistory(m);
              }
            }}
            onAiQuota={m.is_self && m.state === 'S0' ? () => setAiQuotaOpen(true) : undefined}
          />
        ))}
        {!loading && (!list || list.items.length === 0) && (
          <div style={{ padding: 60, textAlign: 'center', color: TEXT_SECONDARY }}>
            暂无档案，点击右上角「+ 新增」开始建档
          </div>
        )}
      </div>

      {/* 新建档案抽屉 */}
      <NewMemberDrawer
        open={newMemberOpen}
        onClose={() => setNewMemberOpen(false)}
        onSuccess={handleNewMemberSuccess}
      />

      {/* [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #5]
          原 MoreMenu 折叠菜单已下线，操作平铺在各成员卡片底部，不再渲染。
          组件定义保留供历史代码引用与潜在回滚，但不再使用。 */}

      {/* 删除确认 */}
      <DeleteConfirmDrawer
        open={!!deleteMember}
        member={deleteMember}
        onClose={() => setDeleteMember(null)}
        onConfirm={() => deleteMember && handleDelete(deleteMember)}
      />

      {/* 邀请码展示 */}
      <InviteCodeDrawer
        open={!!inviteCodeView}
        inviteCode={inviteCodeView?.invite_code}
        expiresAt={inviteCodeView?.invite_expires_at}
        remainingHours={inviteCodeView?.invite_remaining_hours}
        memberName={inviteCodeView?.nickname}
        onClose={() => setInviteCodeView(null)}
      />

      {/* [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29 §3.1 验收 8.1#5] AI 外呼额度抽屉 */}
      <AiQuotaDrawer
        open={aiQuotaOpen}
        onClose={() => setAiQuotaOpen(false)}
        onUpgrade={() => {
          setAiQuotaOpen(false);
          router.push('/member-center');
        }}
      />

      {/* [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29 排版修复] 邀请记录抽屉 */}
      <InvitationHistoryDrawer
        member={invitationHistoryMember}
        onClose={() => setInvitationHistoryMember(null)}
      />
    </div>
  );
}

// ───────────── AI 外呼额度抽屉 ─────────────

interface AiQuotaDrawerProps {
  open: boolean;
  onClose: () => void;
  onUpgrade: () => void;
}

function AiQuotaDrawer({ open, onClose, onUpgrade }: AiQuotaDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [quota, setQuota] = useState<{
    plan_name?: string;
    ai_outbound_used?: number;
    ai_outbound_total?: number;
    ai_outbound_remaining?: number;
    emergency_used?: number;
    emergency_total?: number;
    emergency_remaining?: number;
    is_unlimited?: boolean;
  } | null>(null);

  useEffect(() => {
    if (!open) return;
    let aborted = false;
    (async () => {
      setLoading(true);
      // 优先调用专用配额接口；若不存在则降级到会员中心摘要接口
      const endpoints = [
        '/api/member/quota/ai-outbound',
        '/api/user/membership/summary',
        '/api/membership/current',
      ];
      for (const ep of endpoints) {
        try {
          const res: any = await api.get(ep);
          if (aborted) return;
          const data = res?.data || res;
          if (data) {
            setQuota({
              plan_name: data.plan_name || data.current_plan_name || data.name,
              ai_outbound_used: data.ai_outbound_used ?? data.ai_outbound_call_used,
              ai_outbound_total: data.ai_outbound_total ?? data.ai_outbound_call_count,
              ai_outbound_remaining: data.ai_outbound_remaining ?? data.ai_outbound_call_remaining,
              emergency_used: data.emergency_used ?? data.emergency_ai_call_used,
              emergency_total: data.emergency_total ?? data.emergency_ai_call_count,
              emergency_remaining: data.emergency_remaining ?? data.emergency_ai_call_remaining,
              is_unlimited: data.is_unlimited === true,
            });
            setLoading(false);
            return;
          }
        } catch {
          // 尝试下一个
        }
      }
      if (!aborted) {
        setQuota({});
        setLoading(false);
      }
    })();
    return () => { aborted = true; };
  }, [open]);

  const fmt = (v?: number | null) => {
    if (v === undefined || v === null) return '-';
    if (v === -1) return '不限';
    return String(v);
  };

  return (
    <Popup
      visible={open}
      onMaskClick={onClose}
      position='bottom'
      bodyStyle={{ borderTopLeftRadius: 20, borderTopRightRadius: 20, minHeight: '40vh' }}
    >
      <div data-testid='ai-quota-drawer' style={{ padding: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 17, fontWeight: 700, color: TEXT_PRIMARY }}>
            📞 AI 外呼额度
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, color: TEXT_SECONDARY, cursor: 'pointer' }}>×</button>
        </div>

        {loading && (
          <div style={{ padding: 24, textAlign: 'center', color: TEXT_SECONDARY }}>加载中…</div>
        )}

        {!loading && (
          <>
            {quota?.plan_name && (
              <div style={{ marginBottom: 12, fontSize: 13, color: TEXT_SECONDARY }}>
                当前套餐：<span style={{ color: TEXT_PRIMARY, fontWeight: 600 }}>{quota.plan_name}</span>
              </div>
            )}

            <div style={{ background: '#F0F9FF', borderRadius: 12, padding: 16, marginBottom: 12 }}>
              <div style={{ fontSize: 13, color: TEXT_SECONDARY, marginBottom: 6 }}>常规 AI 外呼</div>
              <div style={{ fontSize: 15, color: TEXT_PRIMARY, fontWeight: 600 }}>
                已用 {fmt(quota?.ai_outbound_used ?? 0)} / 总额 {fmt(quota?.ai_outbound_total)}
                {quota?.ai_outbound_remaining !== undefined && (
                  <span style={{ marginLeft: 8, fontSize: 12, color: ACCENT_COLOR, fontWeight: 500 }}>
                    剩余 {fmt(quota.ai_outbound_remaining)}
                  </span>
                )}
              </div>
            </div>

            <div style={{ background: '#FEF2F2', borderRadius: 12, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 13, color: TEXT_SECONDARY, marginBottom: 6 }}>紧急 AI 呼叫</div>
              <div style={{ fontSize: 15, color: TEXT_PRIMARY, fontWeight: 600 }}>
                已用 {fmt(quota?.emergency_used ?? 0)} / 总额 {fmt(quota?.emergency_total)}
                {quota?.emergency_remaining !== undefined && (
                  <span style={{ marginLeft: 8, fontSize: 12, color: DANGER, fontWeight: 500 }}>
                    剩余 {fmt(quota.emergency_remaining)}
                  </span>
                )}
              </div>
            </div>

            <div style={{ fontSize: 12, color: TEXT_SECONDARY, lineHeight: 1.6, marginBottom: 16 }}>
              提示：AI 外呼额度按月重置，可在「会员中心」升级套餐获得更多额度。
            </div>

            <button
              onClick={onUpgrade}
              data-testid='ai-quota-upgrade-btn'
              style={primaryBtnStyle(false)}
            >
              前往会员中心
            </button>
          </>
        )}
      </div>
    </Popup>
  );
}

// ───────────── 邀请记录抽屉 ─────────────

interface InvitationHistoryItem {
  id?: number;
  invitation_id?: number;
  invite_code?: string;
  status?: string;
  status_label?: string;
  created_at?: string;
  expires_at?: string;
  accepted_at?: string;
  cancelled_at?: string;
}

function InvitationHistoryDrawer({
  member,
  onClose,
}: {
  member: MemberStateItem | null;
  onClose: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<InvitationHistoryItem[]>([]);
  const open = !!member;

  useEffect(() => {
    if (!member) return;
    let aborted = false;
    (async () => {
      setLoading(true);
      // 兼容多个可能的后端接口路径
      const endpoints = [
        `/api/family/member/${member.member_id}/invitations`,
        `/api/family/invitations?member_id=${member.member_id}`,
        `/api/guardian/v13/family/invitations?member_id=${member.member_id}`,
      ];
      for (const ep of endpoints) {
        try {
          const res: any = await api.get(ep);
          if (aborted) return;
          const data = res?.data || res;
          const list: InvitationHistoryItem[] = Array.isArray(data?.items)
            ? data.items
            : Array.isArray(data) ? data : [];
          setItems(list);
          setLoading(false);
          return;
        } catch {
          // 尝试下一个
        }
      }
      if (!aborted) {
        setItems([]);
        setLoading(false);
      }
    })();
    return () => { aborted = true; };
  }, [member]);

  const fmtTime = (s?: string) => {
    if (!s) return '-';
    try { return new Date(s).toLocaleString('zh-CN'); } catch { return s; }
  };

  return (
    <Popup
      visible={open}
      onMaskClick={onClose}
      position='bottom'
      bodyStyle={{ borderTopLeftRadius: 20, borderTopRightRadius: 20, minHeight: '40vh', maxHeight: '80vh', overflow: 'auto' }}
    >
      <div data-testid='invitation-history-drawer' style={{ padding: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 17, fontWeight: 700, color: TEXT_PRIMARY }}>
            邀请记录{member?.nickname ? ` · ${member.nickname}` : ''}
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, color: TEXT_SECONDARY, cursor: 'pointer' }}>×</button>
        </div>

        {loading && (
          <div style={{ padding: 24, textAlign: 'center', color: TEXT_SECONDARY }}>加载中…</div>
        )}

        {!loading && items.length === 0 && (
          <div style={{ padding: 36, textAlign: 'center', color: TEXT_SECONDARY }}>
            暂无邀请记录
          </div>
        )}

        {!loading && items.map((it, idx) => (
          <div
            key={it.id || it.invitation_id || idx}
            data-testid='invitation-history-item'
            style={{
              padding: 14,
              border: '1px solid #E2E8F0',
              borderRadius: 12,
              marginBottom: 10,
              background: '#FFF',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ fontSize: 13, color: TEXT_PRIMARY, fontWeight: 600 }}>
                {it.invite_code || `#${it.id || it.invitation_id || idx + 1}`}
              </span>
              <span style={{ fontSize: 12, color: PRIMARY_COLOR }}>
                {it.status_label || it.status || '-'}
              </span>
            </div>
            <div style={{ fontSize: 12, color: TEXT_SECONDARY, lineHeight: 1.6 }}>
              发起：{fmtTime(it.created_at)}
              {it.expires_at && <> · 过期：{fmtTime(it.expires_at)}</>}
              {it.accepted_at && <> · 接受：{fmtTime(it.accepted_at)}</>}
              {it.cancelled_at && <> · 取消：{fmtTime(it.cancelled_at)}</>}
            </div>
          </div>
        ))}
      </div>
    </Popup>
  );
}

// ───────────── 子组件：成员卡片 ─────────────

interface MemberCardProps {
  member: MemberStateItem;
  onPrimaryAction: () => void;
  // [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #5]
  // 由原"⋯ 折叠菜单"演变为「点击具体次要操作时回调」。
  // 保留参数名 onMoreMenu 以最小化扩散改动，签名升级为带 action 参数。
  onMoreMenu: (action: 'delete' | 'unbind' | 'cancel_invite' | 'invitation_history') => void;
  onAiQuota?: () => void;
}

// [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #5] 蓝色胶囊按钮样式（统一规范）
// - 主操作（实心）：背景 #1677FF / 白字 / 无边框 / 圆角胶囊
// - 次要操作（描边）：透明背景 / 1px #1677FF 边框 / 蓝字 / 圆角胶囊
// - 高度 30px，水平内边距 14px，字号 13px，圆角 999px
const PILL_HEIGHT = 30;
const PILL_PADDING_H = 14;
const PILL_FONT_SIZE = 13;
const PILL_RADIUS = 999;

function pillPrimary(): React.CSSProperties {
  return {
    height: PILL_HEIGHT,
    padding: `0 ${PILL_PADDING_H}px`,
    borderRadius: PILL_RADIUS,
    border: 'none',
    background: PRIMARY_COLOR,
    color: '#FFFFFF',
    fontSize: PILL_FONT_SIZE,
    fontWeight: 600,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    lineHeight: `${PILL_HEIGHT}px`,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  };
}

function pillSecondary(danger: boolean = false): React.CSSProperties {
  const c = danger ? DANGER : PRIMARY_COLOR;
  return {
    height: PILL_HEIGHT,
    padding: `0 ${PILL_PADDING_H}px`,
    borderRadius: PILL_RADIUS,
    border: `1px solid ${c}`,
    background: 'transparent',
    color: c,
    fontSize: PILL_FONT_SIZE,
    fontWeight: 500,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    lineHeight: `${PILL_HEIGHT - 2}px`,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  };
}

function MemberCard({ member, onPrimaryAction, onMoreMenu, onAiQuota }: MemberCardProps) {
  const color = STATE_COLOR_MAP[member.state_color] || STATE_COLOR_MAP.gray;
  const avatarBg = AVATAR_COLORS[member.avatar_color_index || 0];
  const primaryLabel = PRIMARY_ACTION_LABEL[member.primary_action] || '查看';
  // [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29 §3.1 验收 8.1#5]
  // 本人 S0 卡片追加「AI 外呼额度」次按钮（点击弹抽屉）
  const showAiQuotaBtn = !!member.is_self && member.state === 'S0' && !!onAiQuota;

  // [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #5]
  // 将原 MoreMenu 折叠操作平铺为独立次要按钮：
  // - 删除（非 S0/S1/S3 可见）
  // - 解除守护（S1 可见）
  // - 取消邀请（S3 可见）
  // - 邀请记录（invitation_count > 0 可见）
  const secondaryItems: { key: 'delete' | 'unbind' | 'cancel_invite' | 'invitation_history'; label: string; danger?: boolean; show: boolean }[] = [
    { key: 'unbind', label: '解除守护', danger: true, show: member.state === 'S1' && !member.is_self },
    { key: 'cancel_invite', label: '取消邀请', danger: true, show: member.state === 'S3' && !member.is_self },
    { key: 'invitation_history', label: '邀请记录', show: (member.invitation_count || 0) > 0 && !member.is_self },
    { key: 'delete', label: '删除', danger: true, show: !['S0', 'S1', 'S3'].includes(member.state) && !member.is_self },
  ].filter((x) => x.show);

  // [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #6]
  // 本人卡片：仅在姓名旁保留灰色「本人」标签（来自后端 state_label）；
  // 不再在头像下方或其他位置重复展示「本人」文字。
  // 本人 S0 的状态徽章统一改为灰色（背景 #F1F5F9 / 文字 #64748B / 边框 #E2E8F0），与"灰色本人标签"需求一致。
  const isSelfTag = !!member.is_self && member.state === 'S0';
  const tagBg = isSelfTag ? '#F1F5F9' : color.bg;
  const tagText = isSelfTag ? '#64748B' : color.text;
  const tagBorder = isSelfTag ? '#E2E8F0' : color.border;

  return (
    <div
      data-testid={`member-card-${member.member_id}`}
      data-state={member.state}
      style={{
        background: '#FFFFFF',
        // [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 §四 视觉规范] 卡片圆角统一 12px
        borderRadius: 12,
        padding: 14,
        // [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #4]
        // 卡片间距统一 12px，避免局部紧凑/局部松散
        marginBottom: 12,
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        // 由原状态色边框（如 S0 蓝色）改为统一中性边框，避免与浅灰背景叠色
        border: '1px solid #EEF0F3',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          style={{
            width: 46,
            height: 46,
            borderRadius: '50%',
            background: avatarBg,
            color: '#FFF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 18,
            fontWeight: 600,
            flexShrink: 0,
          }}
        >
          {(member.nickname || '?').slice(0, 1)}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: TEXT_PRIMARY, overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {member.nickname || '未命名'}
            </div>
            <span
              data-testid={`state-tag-${member.state}`}
              style={{
                padding: '2px 8px',
                borderRadius: 6,
                fontSize: 11,
                background: tagBg,
                color: tagText,
                border: `1px solid ${tagBorder}`,
                flexShrink: 0,
              }}
            >
              {member.state_label}
            </span>
          </div>
          <div style={{ fontSize: 12, color: TEXT_SECONDARY }}>
            {member.relationship_type || '-'}
            {/* [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29 排版修复]
                「剩余 Xh」仅在邀请进行中（S3 待接受 / 含有效邀请码）时展示 */}
            {member.state === 'S3'
              && !!member.invite_code
              && member.invite_remaining_hours !== undefined
              && member.invite_remaining_hours !== null
              && member.invite_remaining_hours > 0 && (
              <span style={{ marginLeft: 8 }}>· 剩余 {member.invite_remaining_hours}h</span>
            )}
          </div>
        </div>
      </div>

      {/* [BUG-FIX-ARCHIVE-LIST-UI-OPTIM 2026-05-30 #5]
          操作区：所有可用操作平铺为独立胶囊按钮，一行放不下时自动换行。
          - 主操作：实心蓝色胶囊（#1677FF / 白字）
          - 次要操作：蓝色描边胶囊；删除/解除/取消邀请类用红色描边以保留危险提示 */}
      <div
        data-testid={`member-card-actions-${member.member_id}`}
        style={{
          display: 'flex',
          gap: 8,
          marginTop: 12,
          justifyContent: 'flex-end',
          alignItems: 'center',
          flexWrap: 'wrap',
          rowGap: 8,
        }}
      >
        {showAiQuotaBtn && (
          <button
            onClick={onAiQuota}
            data-testid={`ai-quota-btn-${member.member_id}`}
            style={pillSecondary(false)}
          >
            AI 外呼额度
          </button>
        )}
        {secondaryItems.map((it) => (
          <button
            key={it.key}
            onClick={() => onMoreMenu(it.key)}
            data-testid={`secondary-action-${it.key}-${member.member_id}`}
            style={pillSecondary(!!it.danger)}
          >
            {it.label}
          </button>
        ))}
        <button
          onClick={onPrimaryAction}
          data-testid={`primary-action-${member.member_id}`}
          style={pillPrimary()}
        >
          {primaryLabel}
        </button>
      </div>
    </div>
  );
}

// ───────────── 通用 UI 工具 ─────────────

function Label({ text, required }: { text: string; required?: boolean }) {
  return (
    <div style={{ fontSize: 13, color: TEXT_SECONDARY, marginBottom: 6 }}>
      {text} {required && <span style={{ color: DANGER }}>*</span>}
    </div>
  );
}

function Input({ value, onChange, placeholder, maxLength }: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  maxLength?: number;
}) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      maxLength={maxLength}
      style={{
        width: '100%',
        padding: '10px 12px',
        border: '1px solid #E2E8F0',
        borderRadius: 10,
        fontSize: 14,
        boxSizing: 'border-box',
      }}
    />
  );
}

// [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29 排版修复]
// 主按钮支持「全宽（抽屉/底部主操作）」与「自适应（卡片右下角）」两种宽度模式
// 默认 fullWidth=true 兼容历史调用；卡片内主按钮显式传 false 以避免与「⋯」按钮挤压错乱
function primaryBtnStyle(disabled: boolean, fullWidth: boolean = true): React.CSSProperties {
  return {
    background: ACCENT_COLOR,
    color: '#FFF',
    borderRadius: 18,
    border: 'none',
    boxShadow: '0 4px 12px rgba(255,184,0,0.3)',
    padding: '10px 20px',
    fontWeight: 600,
    fontSize: 13,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.7 : 1,
    width: fullWidth ? '100%' : 'auto',
    whiteSpace: 'nowrap',
  };
}

function secondaryBtnStyle(): React.CSSProperties {
  return {
    background: '#FFFFFF',
    color: PRIMARY_COLOR,
    border: `1px solid ${PRIMARY_COLOR}`,
    borderRadius: 12,
    padding: '10px 16px',
    fontSize: 13,
    cursor: 'pointer',
  };
}
