'use client';

/**
 * [PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29] 健康档案 - 档案列表（v2 状态机版）
 *
 * 核心特性：
 * - 7 种状态卡片渲染（S0~S7），统一标签颜色 + 主按钮 + 次操作
 * - 入口收口：废弃顶部「去邀请」大按钮；新建档案后弹「立即去邀请」抽屉
 * - 统一删除接口：DELETE /api/family/member/{member_id}，返回结构化 reason_code
 * - 配额展示：「{X} 人 / 上限 {Y} 人」（不含本人）
 */

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Popup, Toast } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

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

const PRIMARY_COLOR = '#0EA5E9';
const ACCENT_COLOR = '#FFB800';
const TEXT_PRIMARY = '#0F172A';
const TEXT_SECONDARY = '#64748B';
const PAGE_BG = '#F0F9FF';
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

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/family/member/state/list');
      setList(res.data || res);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '加载失败', 'fail');
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

  // 邀请记录跳转
  const handleViewInvitationHistory = (m: MemberStateItem) => {
    router.push(`/health-profile/i-guard?invite_history=${m.member_id}`);
  };

  return (
    <div style={{ minHeight: '100vh', background: PAGE_BG, paddingBottom: 100 }}>
      <GreenNavBar title='档案列表' onBack={() => router.back()} />

      {/* 顶部统计：「已管理 X 人，还可添加 Y-X 人」 */}
      {list && (
        <div style={{
          margin: '12px',
          padding: '16px',
          background: '#FFF',
          borderRadius: 12,
          boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 13, color: TEXT_SECONDARY, marginBottom: 4 }}>📋 档案列表</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: TEXT_PRIMARY }}>
                已管理 <span style={{ color: PRIMARY_COLOR }}>{list.quota_used}</span> 人
                <span style={{ fontSize: 13, color: TEXT_SECONDARY, fontWeight: 400, marginLeft: 8 }}>
                  / 上限 {list.quota_max} 人
                </span>
              </div>
              <div style={{ fontSize: 12, color: TEXT_SECONDARY, marginTop: 4 }}>
                还可添加 <span style={{ color: ACCENT_COLOR, fontWeight: 600 }}>{list.quota_remaining}</span> 人
                {list.guarded_count > 0 && (
                  <span style={{ marginLeft: 12 }}>
                    · 守护中 <span style={{ color: '#10B981', fontWeight: 600 }}>{list.guarded_count}</span> 人
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={() => {
                if (list.quota_remaining <= 0) {
                  showToast('档案配额已满，请先删除现有档案', 'fail');
                  return;
                }
                setNewMemberOpen(true);
              }}
              data-testid='new-member-btn'
              style={{
                ...primaryBtnStyle(false),
                padding: '10px 18px',
                fontSize: 14,
              }}
            >
              + 新增
            </button>
          </div>
        </div>
      )}

      {/* 注意：不再有「去邀请」大按钮（入口 B 已删除） */}

      {/* 卡片列表 */}
      <div style={{ padding: '0 12px' }}>
        {loading && <div style={{ padding: 40, textAlign: 'center', color: TEXT_SECONDARY }}>加载中…</div>}
        {!loading && list?.items.map((m) => (
          <MemberCard
            key={m.member_id}
            member={m}
            onPrimaryAction={() => handlePrimaryAction(m)}
            onMoreMenu={() => setMoreMenuMember(m)}
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

      {/* 更多操作菜单 */}
      <MoreMenu
        open={!!moreMenuMember}
        member={moreMenuMember}
        onClose={() => setMoreMenuMember(null)}
        onAction={(action) => {
          if (!moreMenuMember) return;
          if (action === 'delete') {
            setDeleteMember(moreMenuMember);
          } else if (action === 'unbind') {
            handleUnbind(moreMenuMember);
          } else if (action === 'cancel_invite') {
            handleCancelInvite(moreMenuMember);
          } else if (action === 'invitation_history') {
            handleViewInvitationHistory(moreMenuMember);
          }
        }}
      />

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
    </div>
  );
}

// ───────────── 子组件：成员卡片 ─────────────

interface MemberCardProps {
  member: MemberStateItem;
  onPrimaryAction: () => void;
  onMoreMenu: () => void;
}

function MemberCard({ member, onPrimaryAction, onMoreMenu }: MemberCardProps) {
  const color = STATE_COLOR_MAP[member.state_color] || STATE_COLOR_MAP.gray;
  const avatarBg = AVATAR_COLORS[member.avatar_color_index || 0];
  const primaryLabel = PRIMARY_ACTION_LABEL[member.primary_action] || '查看';

  return (
    <div
      data-testid={`member-card-${member.member_id}`}
      data-state={member.state}
      style={{
        background: '#FFF',
        borderRadius: 14,
        padding: 14,
        marginBottom: 10,
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        border: `1px solid ${color.border}`,
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
                background: color.bg,
                color: color.text,
                border: `1px solid ${color.border}`,
                flexShrink: 0,
              }}
            >
              {member.state_label}
            </span>
          </div>
          <div style={{ fontSize: 12, color: TEXT_SECONDARY }}>
            {member.relationship_type || '-'}
            {member.invite_remaining_hours !== undefined && member.invite_remaining_hours !== null && (
              <span style={{ marginLeft: 8 }}>· 剩余 {member.invite_remaining_hours}h</span>
            )}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'flex-end', alignItems: 'center' }}>
        <button
          onClick={onPrimaryAction}
          data-testid={`primary-action-${member.member_id}`}
          style={primaryBtnStyle(false)}
        >
          {primaryLabel}
        </button>
        {!member.is_self && (
          <button
            onClick={onMoreMenu}
            data-testid={`more-menu-${member.member_id}`}
            style={{
              padding: '8px 14px',
              borderRadius: 12,
              border: '1px solid #E2E8F0',
              background: '#FFF',
              color: TEXT_SECONDARY,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            ⋯
          </button>
        )}
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

function primaryBtnStyle(disabled: boolean): React.CSSProperties {
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
    width: '100%',
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
