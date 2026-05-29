'use client';

/**
 * [守护人体系 IGUARD-V2 2026-05-28] 「我守护的人」页面优化（10 项 Bug 修复）
 *
 * 主要变更：
 * - Bug 1：卡片人数统计口径修正（已绑定非本人 + 全部未绑定记录）
 * - Bug 2：本人卡片「编辑档案」复用 Hero 编辑抽屉
 * - Bug 3：其他人卡片「查看档案」走 Hero 抽屉（只读）
 * - Bug 4/7：统一公共「新建邀请」抽屉
 * - Bug 5：「代付明细」→「共享额度」抽屉（开关 + 概览 + 明细）
 * - Bug 6：「解除守护」改调 DELETE /api/family/management/{id}
 * - Bug 8：移除 + 智能级联（pending 未过期先取消邀请再移除）
 * - Bug 9：邀请记录弹框 → 抽屉（带关闭按钮）
 * - Bug 10：四级按钮配色规范统一
 */
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Dialog, Tag, Empty, Switch, Modal, Popup, Toast } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { validateNickname, validateRelation } from '@/utils/nicknameValidator';

type Lifecycle =
  | 'never_invited'
  | 'inviting'
  | 'accepted'
  | 'rejected'
  | 'unbound'
  | 'expired';

type BindStatus = 'bound' | 'unbound';

interface FamilyItemV13 {
  management_id?: number;
  manager_user_id: number;
  managed_user_id?: number;
  managed_member_id?: number;
  managed_user_nickname?: string;
  relation_label?: string;
  role_badge: 'primary' | 'normal';
  is_primary_guardian: boolean;
  priority_order: number;
  status: 'active' | 'not_active';
  invite_lifecycle: Lifecycle;
  bind_status?: BindStatus;
  display_substatus_label?: string;
  is_orphan?: boolean;
  occupies_quota?: boolean;
  // 邀请相关
  invitation_id?: number;
  invite_code?: string;
  invite_expires_at?: string;
  invite_remaining_hours?: number;
  proxy_pay_enabled: boolean;
  has_bound_device: boolean;
  has_active_med_plan: boolean;
  can_remove: boolean;
  can_remove_reason?: string;
  created_at?: string;
  // [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 对方已退出（cancelled_by_target）
  target_left?: boolean;
}

interface FamilyListResp {
  items: FamilyItemV13[];
  total: number;
  tab_active_count: number;
  tab_pending_count: number;
  bound_count?: number;
  unbound_count?: number;
  quota_used?: number;
  // [BUGFIX-MY-PROFILE-4ITEMS-20260528 修复 2] X 口径：已绑定非本人
  bound_others_count?: number;
  max_guardians: number;
  used: number;
  can_invite_count: number;
  is_paid_member: boolean;
  is_unlimited?: boolean;
}

// 配色
const SKY_500 = '#0EA5E9';
const SKY_700 = '#0369A1';
const SKY_100 = '#E0F2FE';
const SKY_50 = '#F0F9FF';
const SKY_BORDER = '#BAE6FD';
const SLATE_100 = '#F1F5F9';
const SLATE_50 = '#F8FAFC';
const SLATE_BORDER = '#E2E8F0';
const PAGE_BG = '#F0F9FF';
const GOLD = '#FFB800';
const DANGER = '#EF4444';
const TEXT_PRIMARY = '#0F172A';
const TEXT_SECONDARY = '#64748B';

// [Bug 10] 四级按钮配色规范
const BTN_STYLES = {
  primary: {
    background: '#FFB800',
    color: '#FFFFFF',
    borderRadius: 18,
    border: 'none',
    boxShadow: '0 4px 12px rgba(255,184,0,0.3)',
    padding: '10px 20px',
    fontWeight: 600,
    fontSize: 13,
    cursor: 'pointer',
  } as React.CSSProperties,
  secondary: {
    background: '#FFFFFF',
    color: '#0EA5E9',
    border: '1px solid #0EA5E9',
    borderRadius: 12,
    padding: '8px 16px',
    fontSize: 13,
    cursor: 'pointer',
  } as React.CSSProperties,
  danger: {
    background: 'transparent',
    color: '#EF4444',
    border: 'none',
    padding: '8px 16px',
    fontSize: 13,
    cursor: 'pointer',
  } as React.CSSProperties,
  disabled: {
    background: '#F3F4F6',
    color: '#9CA3AF',
    border: 'none',
    borderRadius: 12,
    padding: '8px 16px',
    fontSize: 13,
    cursor: 'not-allowed',
  } as React.CSSProperties,
};

const DISPLAY_LIFECYCLE_LABEL: Record<Lifecycle, string> = {
  never_invited: '尚未邀请',
  inviting: '邀请中',
  accepted: '建立于',
  rejected: '暂未响应',
  unbound: '已解绑',
  expired: '已过期',
};

// ───────────────────────────────────────────────────────────────
// [Bug 4/7] 公共「新建邀请」抽屉组件（内联，避免新增文件）
// ───────────────────────────────────────────────────────────────
interface InviteDrawerProps {
  open: boolean;
  mode: 'create' | 'reinvite';
  presetMember?: FamilyItemV13 | null;
  onClose: () => void;
  onSuccess?: (inviteCode: string) => void;
}

function InviteGuardianDrawer({ open, mode, presetMember, onClose, onSuccess }: InviteDrawerProps) {
  const [nickname, setNickname] = useState('');
  const [relation, setRelation] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      if (mode === 'reinvite' && presetMember) {
        setNickname(presetMember.managed_user_nickname || '');
        setRelation(presetMember.relation_label || '');
      } else {
        setNickname('');
        setRelation('');
      }
    }
  }, [open, mode, presetMember]);

  const handleSubmit = async () => {
    // [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29] D5/D7 三端字符级一致：
    //   trim 非空 + 长度 1~20 + 不允许纯特殊字符（emoji 允许）
    const nv = validateNickname(nickname);
    if (!nv.ok) {
      showToast(nv.msg, 'fail');
      return;
    }
    const rv = validateRelation(relation);
    if (!rv.ok) {
      showToast(rv.msg, 'fail');
      return;
    }
    setSubmitting(true);
    try {
      const body: any = {
        relation_type: relation.trim(),
        nickname: nickname.trim(),
      };
      if (mode === 'reinvite' && presetMember?.managed_member_id) {
        body.member_id = presetMember.managed_member_id;
      }
      const res: any = await api.post('/api/family/invitation', body);
      const data = res.data || res;
      const code = data.invite_code || data.code;
      showToast('邀请已创建', 'success');
      onSuccess?.(code);
      onClose();
    } catch (e: any) {
      // [PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 解析结构化错误码 WARD_LIMIT_REACHED
      const detail = e?.response?.data?.detail;
      let msg = '邀请创建失败';
      if (detail && typeof detail === 'object') {
        if (detail.code === 'WARD_LIMIT_REACHED') {
          msg = detail.message || `我守护的人已达上限（${detail.x}/${detail.y}），请先升级会员或解绑现有守护对象`;
        } else if (detail.message) {
          msg = String(detail.message);
        }
      } else if (typeof detail === 'string') {
        msg = detail;
      }
      showToast(msg, 'fail');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Popup
      visible={open}
      onMaskClick={onClose}
      position='bottom'
      bodyStyle={{ borderTopLeftRadius: 20, borderTopRightRadius: 20, minHeight: '50vh' }}
    >
      <div data-testid='invite-guardian-drawer' style={{ padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 17, fontWeight: 700, color: TEXT_PRIMARY }}>
            {mode === 'reinvite' ? '再次邀请' : '新建邀请'}
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, color: TEXT_SECONDARY, cursor: 'pointer' }}>
            ×
          </button>
        </div>

        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 13, color: TEXT_SECONDARY, marginBottom: 6 }}>
            姓名 <span style={{ color: DANGER }}>*</span>
          </div>
          <input
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            placeholder='如：张妈妈 / 李叔叔'
            maxLength={20}
            style={{
              width: '100%', padding: '10px 12px', border: '1px solid #E2E8F0',
              borderRadius: 10, fontSize: 14, boxSizing: 'border-box',
            }}
          />
          {!nickname.trim() && (
            <div style={{ fontSize: 12, color: DANGER, marginTop: 4 }}>姓名不能为空</div>
          )}
        </div>
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 13, color: TEXT_SECONDARY, marginBottom: 6 }}>关系 <span style={{ color: DANGER }}>*</span></div>
          <input
            value={relation}
            onChange={(e) => setRelation(e.target.value)}
            placeholder='如：父亲、母亲、配偶'
            style={{
              width: '100%', padding: '10px 12px', border: '1px solid #E2E8F0',
              borderRadius: 10, fontSize: 14, boxSizing: 'border-box',
            }}
          />
        </div>

        <button
          disabled={submitting}
          onClick={handleSubmit}
          data-testid='invite-submit-btn'
          style={{
            ...BTN_STYLES.primary,
            width: '100%',
            opacity: submitting ? 0.7 : 1,
          }}
        >
          {submitting ? '创建中…' : '生成邀请二维码'}
        </button>
      </div>
    </Popup>
  );
}

// ───────────────────────────────────────────────────────────────
// [Bug 5] 共享额度抽屉
// ───────────────────────────────────────────────────────────────
interface SharedQuotaDrawerProps {
  open: boolean;
  card: FamilyItemV13 | null;
  onClose: () => void;
  onRefresh?: () => void;
}

function SharedQuotaDrawer({ open, card, onClose, onRefresh }: SharedQuotaDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any | null>(null);

  const load = useCallback(async () => {
    if (!card?.management_id) return;
    setLoading(true);
    try {
      const res: any = await api.get(`/api/family/management/${card.management_id}/usage-records?limit=20`);
      setData(res.data || res);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '加载失败', 'fail');
    } finally {
      setLoading(false);
    }
  }, [card]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  const handleToggle = async (enabled: boolean) => {
    if (!card?.management_id) return;
    try {
      await api.put(`/api/family/management/${card.management_id}/share-toggle`, { enabled });
      showToast(enabled ? '已开启会员权益共享' : '已关闭会员权益共享', 'success');
      setData((d: any) => d ? { ...d, share_enabled: enabled } : d);
      onRefresh?.();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  return (
    <Popup
      visible={open}
      onMaskClick={onClose}
      position='bottom'
      bodyStyle={{ borderTopLeftRadius: 20, borderTopRightRadius: 20, minHeight: '60vh', maxHeight: '85vh', overflowY: 'auto' }}
    >
      <div data-testid='shared-quota-drawer' style={{ padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 17, fontWeight: 700, color: TEXT_PRIMARY }}>
            共享额度
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, color: TEXT_SECONDARY, cursor: 'pointer' }}>
            ×
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: TEXT_SECONDARY }}>加载中…</div>
        ) : data ? (
          <>
            {/* 额度概览 */}
            <div style={{
              background: `linear-gradient(135deg, ${SKY_100} 0%, ${SKY_50} 100%)`,
              border: `1px solid ${SKY_BORDER}`,
              borderRadius: 14,
              padding: 14,
              marginBottom: 16,
            }}>
              <div style={{ fontSize: 13, color: TEXT_SECONDARY, marginBottom: 6 }}>📊 额度概览</div>
              <div style={{ fontSize: 14, color: TEXT_PRIMARY }}>
                会员权益共享：已使用 <b style={{ color: SKY_700 }}>{data.quota?.used ?? 0}</b> / 共 <b style={{ color: SKY_700 }}>{data.quota?.total ?? 0}</b>
              </div>
              <div style={{ fontSize: 13, color: TEXT_SECONDARY, marginTop: 4 }}>
                剩余 <b style={{ color: SKY_700 }}>{data.quota?.remaining ?? 0}</b> 次
              </div>
            </div>

            {/* 开关 */}
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '14px 14px', background: '#FFF', border: '1px solid #E2E8F0',
              borderRadius: 12, marginBottom: 16,
            }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: TEXT_PRIMARY }}>会员权益共享</div>
                <div style={{ fontSize: 12, color: TEXT_SECONDARY, marginTop: 2 }}>
                  关闭后，TA 将无法继续使用您的会员权益
                </div>
              </div>
              <Switch
                data-testid='share-toggle-switch'
                checked={!!data.share_enabled}
                onChange={handleToggle}
              />
            </div>

            {/* 使用明细 */}
            <div style={{ fontSize: 14, fontWeight: 600, color: TEXT_PRIMARY, marginBottom: 8 }}>使用明细</div>
            <div style={{ maxHeight: 280, overflowY: 'auto' }}>
              {data.items?.length ? data.items.map((r: any) => (
                <div key={r.id} style={{
                  display: 'flex', justifyContent: 'space-between',
                  padding: '10px 0', borderBottom: '1px dashed #E2E8F0', fontSize: 13,
                }}>
                  <span>{r.label}</span>
                  <span style={{ color: TEXT_SECONDARY, fontSize: 12 }}>
                    {r.used_at ? new Date(r.used_at).toLocaleString() : ''}
                  </span>
                </div>
              )) : (
                <div style={{ textAlign: 'center', color: TEXT_SECONDARY, padding: 24, fontSize: 13 }}>
                  暂无使用记录
                </div>
              )}
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: TEXT_SECONDARY }}>暂无数据</div>
        )}
      </div>
    </Popup>
  );
}

// ───────────────────────────────────────────────────────────────
// [Bug 2/3] 档案编辑/查看抽屉（复用 HealthProfileEditor + readOnly）
// ───────────────────────────────────────────────────────────────
interface ProfileDrawerProps {
  open: boolean;
  memberUserId?: number;
  memberId?: number;
  readOnly: boolean;
  onClose: () => void;
}

function ProfileEditDrawer({ open, memberUserId, memberId, readOnly, onClose }: ProfileDrawerProps) {
  const router = useRouter();
  const [profile, setProfile] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setProfile(null);
    setLoading(true);
    (async () => {
      try {
        const params: string[] = [];
        if (memberUserId) params.push(`member_user_id=${memberUserId}`);
        if (memberId) params.push(`member_id=${memberId}`);
        const url = `/api/health-profile${params.length ? '?' + params.join('&') : ''}`;
        const res: any = await api.get(url);
        setProfile(res.data || res);
      } catch (e: any) {
        showToast(e?.response?.data?.detail || '加载档案失败', 'fail');
      } finally {
        setLoading(false);
      }
    })();
  }, [open, memberUserId, memberId]);

  const goToFullEdit = () => {
    onClose();
    const params: string[] = [];
    if (memberUserId) params.push(`member_user_id=${memberUserId}`);
    router.push(`/health-profile${params.length ? '?' + params.join('&') : ''}`);
  };

  const renderRow = (label: string, value: any) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px dashed #E2E8F0', fontSize: 14 }}>
      <span style={{ color: TEXT_SECONDARY }}>{label}</span>
      <span style={{ color: TEXT_PRIMARY, opacity: readOnly ? 0.7 : 1, maxWidth: '60%', textAlign: 'right' }}>
        {value || '—'}
      </span>
    </div>
  );

  return (
    <Popup
      visible={open}
      onMaskClick={onClose}
      position='bottom'
      bodyStyle={{ borderTopLeftRadius: 20, borderTopRightRadius: 20, height: '92vh', overflowY: 'auto' }}
    >
      <div data-testid='profile-edit-drawer' style={{ padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 17, fontWeight: 700, color: TEXT_PRIMARY }}>
            {readOnly ? '查看档案' : '编辑档案'}
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            {/* [Bug 3] 只读时隐藏「编辑」入口 */}
            {!readOnly && (
              <button
                data-testid='profile-edit-action'
                style={{ ...BTN_STYLES.secondary, padding: '4px 12px', fontSize: 12 }}
                onClick={goToFullEdit}
              >
                编辑
              </button>
            )}
            <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, color: TEXT_SECONDARY, cursor: 'pointer' }}>
              ×
            </button>
          </div>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: TEXT_SECONDARY }}>加载中…</div>
        ) : profile ? (
          <div style={{ pointerEvents: readOnly ? 'none' : 'auto' }}>
            {renderRow('昵称', profile.nickname)}
            {renderRow('性别', profile.gender === 'male' ? '男' : profile.gender === 'female' ? '女' : profile.gender)}
            {renderRow('生日', profile.birthday)}
            {renderRow('身高', profile.height ? `${profile.height} cm` : '')}
            {renderRow('体重', profile.weight ? `${profile.weight} kg` : '')}
            {renderRow('血型', profile.blood_type)}
            {renderRow('吸烟史', profile.smoking)}
            {renderRow('饮酒史', profile.drinking)}
            {renderRow('运动习惯', profile.exercise_habit)}
            {renderRow('睡眠习惯', profile.sleep_habit)}
            {renderRow('饮食习惯', profile.diet_habit)}
            {renderRow('慢性病', Array.isArray(profile.chronic_diseases) ? profile.chronic_diseases.map((x: any) => typeof x === 'string' ? x : x?.value).filter(Boolean).join('、') : profile.chronic_diseases)}
            {renderRow('过敏史', Array.isArray(profile.allergies) ? profile.allergies.map((x: any) => typeof x === 'string' ? x : x?.value).filter(Boolean).join('、') : profile.allergies)}
            {renderRow('遗传病', Array.isArray(profile.genetic_diseases) ? profile.genetic_diseases.map((x: any) => typeof x === 'string' ? x : x?.value).filter(Boolean).join('、') : profile.genetic_diseases)}

            {/* [Bug 2/3] 底部保存按钮：只读时隐藏 */}
            {!readOnly && (
              <button
                data-testid='profile-save-btn'
                style={{ ...BTN_STYLES.primary, width: '100%', marginTop: 20 }}
                onClick={goToFullEdit}
              >
                进入完整编辑
              </button>
            )}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: TEXT_SECONDARY }}>暂无档案</div>
        )}
      </div>
    </Popup>
  );
}

// ───────────────────────────────────────────────────────────────
// [Bug 9] 邀请记录抽屉
// ───────────────────────────────────────────────────────────────
interface HistoryDrawerProps {
  open: boolean;
  card: FamilyItemV13 | null;
  onClose: () => void;
}

function InviteHistoryDrawer({ open, card, onClose }: HistoryDrawerProps) {
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!card) return;
    setLoading(true);
    try {
      const params: string[] = [];
      if (card.managed_user_id) params.push(`managed_user_id=${card.managed_user_id}`);
      if (card.managed_member_id) params.push(`managed_member_id=${card.managed_member_id}`);
      if (card.relation_label && params.length === 0) {
        params.push(`relation_type=${encodeURIComponent(card.relation_label)}`);
      }
      const res: any = await api.get(
        `/api/guardian/v13/family/invite-history${params.length ? '?' + params.join('&') : ''}`,
      );
      const d = res.data || res;
      const softItems = (Array.isArray(d.items) ? d.items : []).map((x: any) => ({
        ...x,
        status_label: x?.status_label === '已拒绝' ? '暂未响应' : x?.status_label,
      }));
      setHistory(softItems);
    } catch {
      setHistory([]);
    } finally {
      setLoading(false);
    }
  }, [card]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  return (
    <Popup
      visible={open}
      onMaskClick={onClose}
      position='bottom'
      bodyStyle={{ borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '70vh', overflowY: 'auto' }}
    >
      <div data-testid='invite-history-drawer' style={{ padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 17, fontWeight: 700, color: TEXT_PRIMARY }}>邀请记录</div>
          <button
            data-testid='history-close-btn'
            onClick={onClose}
            style={{ background: 'none', border: 'none', fontSize: 20, color: TEXT_SECONDARY, cursor: 'pointer' }}
          >
            ×
          </button>
        </div>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: TEXT_SECONDARY }}>加载中…</div>
        ) : history.length === 0 ? (
          <Empty description='暂无邀请记录' />
        ) : (
          history.map((h: any) => (
            <div key={h.id} style={{ padding: '10px 0', borderBottom: '1px dashed #E2E8F0', fontSize: 13 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{h.relation_type || '邀请'}</span>
                <Tag color={h.status_color || 'default'}>{h.status_label}</Tag>
              </div>
              <div style={{ fontSize: 11, color: TEXT_SECONDARY, marginTop: 2 }}>
                {h.created_at ? new Date(h.created_at).toLocaleString() : ''}
              </div>
            </div>
          ))
        )}
      </div>
    </Popup>
  );
}

// ───────────────────────────────────────────────────────────────
// 主页面
// ───────────────────────────────────────────────────────────────
export default function IGuardPage() {
  const router = useRouter();
  const [resp, setResp] = useState<FamilyListResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [me, setMe] = useState<{ id: number; nickname?: string }>({ id: 0 });

  // 抽屉状态
  const [inviteDrawer, setInviteDrawer] = useState<{ open: boolean; mode: 'create' | 'reinvite'; preset?: FamilyItemV13 | null }>({ open: false, mode: 'create' });
  const [quotaDrawer, setQuotaDrawer] = useState<{ open: boolean; card: FamilyItemV13 | null }>({ open: false, card: null });
  const [profileDrawer, setProfileDrawer] = useState<{ open: boolean; memberUserId?: number; memberId?: number; readOnly: boolean }>({ open: false, readOnly: false });
  const [historyDrawer, setHistoryDrawer] = useState<{ open: boolean; card: FamilyItemV13 | null }>({ open: false, card: null });

  // 上限提示弹窗
  const [showLimit, setShowLimit] = useState(false);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const meRes: any = await api.get('/api/users/me');
      const meData = meRes.data || meRes;
      setMe({ id: meData.id, nickname: meData.nickname });

      const res: any = await api.get('/api/guardian/v13/family/list');
      const data = (res.data || res) as FamilyListResp;
      setResp(data);
    } catch (e: any) {
      console.error('[iguard-v2] fetchList error', e);
      setResp(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const allItems = resp?.items || [];
  const boundItems = allItems.filter((it) => (it.bind_status || (it.status === 'active' ? 'bound' : 'unbound')) === 'bound');
  const unboundItems = allItems.filter((it) => (it.bind_status || (it.status === 'active' ? 'bound' : 'unbound')) === 'unbound');

  // [BUGFIX-MY-PROFILE-4ITEMS-20260528 修复 2/3] X 口径 = 已绑定非本人（方案 A，不含本人）；
  // 优先使用后端 bound_others_count；兜底前端按 bind_status==bound && managed_user_id != me 计算
  const guardCount = useMemo(() => {
    if (typeof resp?.bound_others_count === 'number') return resp.bound_others_count;
    return boundItems.filter((it) => it.managed_user_id !== me.id).length;
  }, [resp?.bound_others_count, boundItems, me.id]);

  // [BUGFIX-MY-PROFILE-4ITEMS-20260528 修复 3] 直接使用后端 can_invite_count，废弃前端自算；
  // 后端异常时 resp 为 null，canInvite 兜底为 0
  const canInvite = resp?.can_invite_count ?? 0;
  const maxGuard = resp?.max_guardians ?? 0;

  // [Bug 4] 「+发起邀请」打开公共抽屉
  const handleInvite = () => {
    if (canInvite <= 0) {
      setShowLimit(true);
      return;
    }
    setInviteDrawer({ open: true, mode: 'create' });
  };

  const handleCancelInvite = async (it: FamilyItemV13) => {
    if (!it.invite_code) return;
    const ok = await Dialog.confirm({
      title: '取消邀请',
      content: '取消后该邀请将作废，对方扫码会提示无效',
    });
    if (!ok) return;
    try {
      await api.post('/api/guardian/v13/family/invite/cancel', { invite_code: it.invite_code });
      showToast('邀请已取消', 'success');
      fetchList();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  // [Bug 8 + BUGFIX-MY-GUARDIAN-CARD-2-20260528] 移除 + 智能级联 + 幂等处理
  const handleRemove = async (it: FamilyItemV13) => {
    // 场景 1：pending 未过期 → 级联取消 + 移除
    const isPendingActive = it.invite_lifecycle === 'inviting' && !!it.invite_code;
    if (isPendingActive) {
      const ok = await Dialog.confirm({
        title: '该邀请仍在生效中',
        content: '该邀请尚未过期，移除前需要先取消邀请。是否继续？',
        confirmText: '取消邀请并移除',
        cancelText: '再想想',
      });
      if (!ok) return;
      try {
        await api.post('/api/guardian/v13/family/invite/cancel', { invite_code: it.invite_code });
        const resp: any = await api.post('/api/guardian/v13/family/remove', {
          invitation_id: it.invitation_id,
          managed_user_id: it.managed_user_id,
          managed_member_id: it.managed_member_id,
        });
        const d = resp?.data || resp;
        showToast(d?.deleted === false ? '该记录已被移除，列表已刷新' : '已取消邀请并移除', 'success');
        fetchList();
      } catch (e: any) {
        showToast(e?.response?.data?.detail || '操作失败', 'fail');
      }
      return;
    }

    // 场景 2/3：纯邀请记录 / 孤儿档案 / 已过期 / 尚未邀请
    const isInvitationOnly = !it.managed_user_id && !it.management_id;
    const content = isInvitationOnly
      ? '移除后，该邀请记录将从您的列表中消失，已发出的邀请二维码将作废。'
      : '移除后，该档案将从您的列表中消失。若 TA 是您自行添加的家人档案，所有资料将一并删除，此操作不可恢复。';
    const ok = await Dialog.confirm({
      title: '移除',
      content,
      confirmText: '确认移除',
      cancelText: '再想想',
    });
    if (!ok) return;
    try {
      const body: any = {};
      if (it.invitation_id) body.invitation_id = it.invitation_id;
      if (it.managed_user_id) body.managed_user_id = it.managed_user_id;
      if (it.managed_member_id) body.managed_member_id = it.managed_member_id;
      const resp: any = await api.post('/api/guardian/v13/family/remove', body);
      const d = resp?.data || resp;
      // [BUGFIX-2] 幂等返回：deleted=false 表示该记录其实已不存在，给友好提示并刷新
      showToast(d?.deleted === false ? '该记录已被移除，列表已刷新' : '已移除', 'success');
      fetchList();
    } catch (e: any) {
      // 对老前端兼容：若后端仍返回 404，依旧友好提示 + 刷新
      const detail = e?.response?.data?.detail || '操作失败';
      if (e?.response?.status === 404) {
        showToast('该记录已被移除，列表已刷新', 'success');
        fetchList();
      } else {
        showToast(detail, 'fail');
      }
    }
  };

  // [Bug 6] 解除守护：改调 DELETE /api/family/management/{id}
  const handleUnGuard = async (it: FamilyItemV13) => {
    if (!it.management_id) return;
    const ok = await Dialog.confirm({
      title: '解除守护',
      content: `将解除与 ${it.managed_user_nickname || 'TA'} 的守护关系，TA 的健康档案数据将完整保留。解除后您将无法再查看 TA 的档案与代付，且对方会收到解除通知。`,
      confirmText: '确认解除',
      cancelText: '再想想',
    });
    if (!ok) return;
    try {
      await api.delete(`/api/family/management/${it.management_id}`);
      showToast('已解除守护', 'success');
      fetchList();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  // [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 彻底删除（真删除）
  const handleHardDelete = async (it: FamilyItemV13) => {
    if (!it.managed_member_id) {
      showToast('该记录无法彻底删除', 'fail');
      return;
    }
    // 第一步：获取删除预览
    let preview: any = null;
    try {
      const res: any = await api.get(
        `/api/guardian/v13/family/member/${it.managed_member_id}/delete-preview`,
      );
      preview = res.data || res;
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '加载删除预览失败', 'fail');
      return;
    }
    if (!preview) return;

    // 检查闸门
    if (!preview.can_delete) {
      const failed = Object.values(preview.gates || {}).find((g: any) => !g.pass) as any;
      showToast(failed?.message || '请先处理依赖项再删除', 'fail');
      return;
    }

    const impact = preview.impact || {};
    const lines: string[] = [
      `此操作不可恢复，将永久删除以下数据：`,
      `• 健康档案 ${impact.health_profile_count || 0} 份`,
      `• AI 对话历史 ${impact.ai_conversation_count || 0} 条`,
      `• AI 消息 ${impact.ai_message_count || 0} 条`,
      `• 用药提醒 ${impact.medication_reminder_count || 0} 条`,
      `• 紧急联系人引用 ${impact.emergency_contact_ref_count || 0} 处`,
    ];

    const ok = await Dialog.confirm({
      title: `⚠️ 彻底删除「${preview.member_nickname || '该家人'}」`,
      content: lines.join('\n'),
      confirmText: '确定彻底删除',
      cancelText: '取消',
    });
    if (!ok) return;

    try {
      const delRes: any = await api.delete(
        `/api/guardian/v13/family/member/${it.managed_member_id}`,
      );
      const d = delRes.data || delRes;
      showToast(d?.deleted ? '已彻底删除' : '删除完成', 'success');
      fetchList();
    } catch (e: any) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail || '删除失败';
      if (status === 429) {
        showToast(String(detail), 'fail');
      } else {
        showToast(String(detail), 'fail');
      }
    }
  };

  // [Bug 7] 再次邀请：打开公共抽屉，预填
  const handleReinvite = (it: FamilyItemV13) => {
    if (canInvite <= 0) {
      setShowLimit(true);
      return;
    }
    setInviteDrawer({ open: true, mode: 'reinvite', preset: it });
  };

  const handleViewQr = (it: FamilyItemV13) => {
    if (!it.invite_code) return;
    router.push(`/family-auth?code=${it.invite_code}&role=inviter`);
  };

  // [Bug 5] 共享额度抽屉入口（替换原代付明细）
  const openSharedQuota = (it: FamilyItemV13) => {
    if (!it.management_id) {
      showToast('该用户未绑定，无法查看', 'fail');
      return;
    }
    setQuotaDrawer({ open: true, card: it });
  };

  // [Bug 2/3] 档案抽屉入口
  const openProfile = (it: FamilyItemV13, readOnly: boolean) => {
    setProfileDrawer({
      open: true,
      memberUserId: it.managed_user_id,
      memberId: it.managed_member_id,
      readOnly,
    });
  };

  const fmtDate = (s?: string) => {
    if (!s) return '—';
    try { return new Date(s).toISOString().slice(0, 10); } catch { return s; }
  };

  const buildSubStatusText = (it: FamilyItemV13): string => {
    if (it.display_substatus_label) {
      const base = it.display_substatus_label;
      if (it.invite_lifecycle === 'accepted' && it.created_at) return `${base} ${fmtDate(it.created_at)}`;
      if (it.invite_lifecycle === 'inviting' && typeof it.invite_remaining_hours === 'number') return `${base} · 还剩 ${it.invite_remaining_hours} 小时`;
      if (it.invite_lifecycle === 'unbound') return `${base}${it.created_at ? ' · 于 ' + fmtDate(it.created_at) : ''}`;
      if (it.invite_lifecycle === 'expired') return `${base} · 上次邀请已过期`;
      if (it.invite_lifecycle === 'rejected' && it.created_at) return `${base} · 创建于 ${fmtDate(it.created_at)}`;
      return base;
    }
    const lbl = DISPLAY_LIFECYCLE_LABEL[it.invite_lifecycle] || '';
    if (it.invite_lifecycle === 'accepted' && it.created_at) return `${lbl} ${fmtDate(it.created_at)}`;
    if (it.invite_lifecycle === 'inviting' && typeof it.invite_remaining_hours === 'number') return `${lbl} · 还剩 ${it.invite_remaining_hours} 小时`;
    return lbl;
  };

  // [Bug 10] 禁用态长按提示
  const showRemoveDisabledHint = (it: FamilyItemV13) => {
    const reason = it.can_remove_reason
      || (it.status === 'active' ? '请先解除守护'
        : it.has_bound_device ? '请先解绑硬件设备'
        : it.has_active_med_plan ? '存在在途服药计划，请先终止'
        : it.invite_lifecycle === 'inviting' ? '请先取消邀请'
        : '当前状态不允许移除');
    Toast.show({ content: reason });
  };

  // ─── 卡片渲染 ────────────
  const renderCard = (it: FamilyItemV13, idx: number, zone: 'bound' | 'unbound') => {
    const isBound = zone === 'bound';
    // [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 对方已退出 → 整卡置灰
    const isTargetLeft = !!it.target_left;
    const cardBg = isTargetLeft ? '#F3F4F6' : '#FFFFFF';
    const cardBorder = it.is_primary_guardian
      ? `1.5px solid ${GOLD}`
      : isTargetLeft ? '1px solid #D1D5DB'
      : isBound ? `1px solid ${SKY_BORDER}` : `1px solid ${SLATE_BORDER}`;
    const subBadgeBg = isTargetLeft ? '#E5E7EB' : (isBound ? '#E0F2FE' : '#F1F5F9');
    const subBadgeFg = isTargetLeft ? '#6B7280' : (isBound ? SKY_700 : TEXT_SECONDARY);

    return (
      <div
        key={`${zone}-${it.management_id || it.invitation_id || 'inv'}-${idx}`}
        data-testid={`family-card-v131-${zone}-${it.invite_lifecycle}`}
        style={{
          background: cardBg, borderRadius: 16, padding: 14, marginBottom: 10,
          boxShadow: '0 2px 8px rgba(14, 165, 233, 0.06)',
          border: cardBorder, position: 'relative',
        }}
      >
        {it.is_primary_guardian && (
          <div style={{
            position: 'absolute', top: 10, right: 10, background: GOLD, color: '#fff',
            borderRadius: 10, padding: '2px 8px', fontSize: 10, fontWeight: 700,
            boxShadow: '0 2px 6px rgba(255, 184, 0, 0.4)', zIndex: 2,
          }}>👑 主</div>
        )}

        {/* [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] target_left 也显示灰标 */}
        {(!isBound || isTargetLeft) && (
          <div style={{
            position: 'absolute', top: it.is_primary_guardian ? 38 : 10, right: 10,
            background: subBadgeBg, color: subBadgeFg, borderRadius: 8, padding: '2px 8px',
            fontSize: 11, fontWeight: 600, maxWidth: 140, whiteSpace: 'nowrap',
            overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {isTargetLeft ? '对方已退出' : buildSubStatusText(it)}
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <div style={{
            width: 44, height: 44, borderRadius: '50%',
            background: isBound ? SKY_100 : SLATE_100,
            color: isBound ? SKY_700 : TEXT_SECONDARY,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, fontWeight: 700, marginRight: 12,
            border: `1.5px solid ${isBound ? SKY_BORDER : SLATE_BORDER}`,
          }}>
            {(it.managed_user_nickname || it.relation_label || '?').charAt(0)}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: TEXT_PRIMARY, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {it.managed_user_nickname || it.relation_label || '待邀请家人'}
              {it.relation_label && it.managed_user_nickname && (
                <span style={{ fontSize: 12, color: TEXT_SECONDARY, fontWeight: 400, marginLeft: 6 }}>· {it.relation_label}</span>
              )}
            </div>
            <div style={{ fontSize: 12, color: TEXT_SECONDARY, marginTop: 4 }}>
              {isBound && (it.is_orphan ? '由我代为管理' : buildSubStatusText(it))}
              {isBound && it.proxy_pay_enabled && (
                <Tag color='warning' style={{ marginLeft: 6, background: '#FFF7E6', color: GOLD, border: 'none' }}>代付中</Tag>
              )}
            </div>
          </div>
        </div>

        {/* [Bug 10] 按钮区使用统一配色 */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {isBound ? (
            <>
              {/* [Bug 3] 查看档案 → Hero 抽屉只读 */}
              <button
                data-testid='btn-view-profile'
                style={{ ...BTN_STYLES.secondary, flex: 1 }}
                onClick={() => openProfile(it, true)}
              >
                查看档案
              </button>
              {/* [Bug 5] 代付明细 → 共享额度 */}
              {it.is_primary_guardian && it.managed_user_id && (
                <button
                  data-testid='btn-shared-quota'
                  style={{ ...BTN_STYLES.secondary, flex: 1 }}
                  onClick={() => openSharedQuota(it)}
                >
                  共享额度
                </button>
              )}
              {it.is_orphan ? (
                <>
                  <button
                    data-testid='btn-remove'
                    disabled={!it.can_remove}
                    style={{ ...(it.can_remove ? BTN_STYLES.danger : BTN_STYLES.disabled), flex: 1 }}
                    onClick={() => it.can_remove ? handleRemove(it) : showRemoveDisabledHint(it)}
                  >
                    移除
                  </button>
                  {/* [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 孤儿档案可彻底删除 */}
                  {it.managed_member_id && (
                    <button
                      data-testid='btn-hard-delete'
                      style={{ ...BTN_STYLES.danger, flex: 1, background: '#DC2626' }}
                      onClick={() => handleHardDelete(it)}
                    >
                      彻底删除
                    </button>
                  )}
                </>
              ) : it.target_left ? (
                <>
                  {/* [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 对方已退出 → 重新邀请 + 彻底删除 */}
                  <button
                    data-testid='btn-reinvite-target-left'
                    style={{ ...BTN_STYLES.primary, flex: 1 }}
                    onClick={() => handleReinvite(it)}
                  >
                    重新邀请
                  </button>
                  {it.managed_member_id && (
                    <button
                      data-testid='btn-hard-delete'
                      style={{ ...BTN_STYLES.danger, flex: 1, background: '#DC2626' }}
                      onClick={() => handleHardDelete(it)}
                    >
                      彻底删除
                    </button>
                  )}
                </>
              ) : (
                <button
                  data-testid='btn-unguard'
                  style={{ ...BTN_STYLES.danger, flex: 1 }}
                  onClick={() => handleUnGuard(it)}
                >
                  解除守护
                </button>
              )}
            </>
          ) : (
            <>
              {it.invite_lifecycle === 'inviting' && (
                <>
                  <button style={{ ...BTN_STYLES.primary, flex: 1 }} onClick={() => handleViewQr(it)}>
                    查看二维码
                  </button>
                  <button style={{ ...BTN_STYLES.danger, flex: 1 }} onClick={() => handleCancelInvite(it)}>
                    取消邀请
                  </button>
                </>
              )}
              {(it.invite_lifecycle === 'rejected' || it.invite_lifecycle === 'unbound' || it.invite_lifecycle === 'expired') && (
                <>
                  {/* [Bug 7] 再次邀请 → 公共抽屉 */}
                  <button
                    data-testid='btn-reinvite'
                    style={{ ...BTN_STYLES.primary, flex: 1 }}
                    onClick={() => handleReinvite(it)}
                  >
                    再次邀请
                  </button>
                  <button
                    data-testid='btn-remove'
                    disabled={!it.can_remove}
                    style={{ ...(it.can_remove ? BTN_STYLES.danger : BTN_STYLES.disabled), flex: 1 }}
                    onClick={() => it.can_remove ? handleRemove(it) : showRemoveDisabledHint(it)}
                  >
                    移除
                  </button>
                  {/* [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 彻底删除入口 */}
                  {it.managed_member_id && (
                    <button
                      data-testid='btn-hard-delete'
                      style={{ ...BTN_STYLES.danger, flex: 1, background: '#DC2626' }}
                      onClick={() => handleHardDelete(it)}
                    >
                      彻底删除
                    </button>
                  )}
                </>
              )}
              {it.invite_lifecycle === 'never_invited' && (
                <>
                  <button style={{ ...BTN_STYLES.primary, flex: 1 }} onClick={handleInvite}>
                    发起邀请
                  </button>
                  <button
                    data-testid='btn-remove'
                    disabled={!it.can_remove}
                    style={{ ...(it.can_remove ? BTN_STYLES.danger : BTN_STYLES.disabled), flex: 1 }}
                    onClick={() => it.can_remove ? handleRemove(it) : showRemoveDisabledHint(it)}
                  >
                    移除
                  </button>
                  {/* [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 彻底删除入口 */}
                  {it.managed_member_id && (
                    <button
                      data-testid='btn-hard-delete'
                      style={{ ...BTN_STYLES.danger, flex: 1, background: '#DC2626' }}
                      onClick={() => handleHardDelete(it)}
                    >
                      彻底删除
                    </button>
                  )}
                </>
              )}
              <button
                style={{ background: 'transparent', border: 'none', color: SKY_500, fontSize: 12, padding: '8px 12px', cursor: 'pointer' }}
                onClick={() => setHistoryDrawer({ open: true, card: it })}
              >
                邀请记录
              </button>
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div style={{ background: PAGE_BG, minHeight: '100vh', paddingBottom: 32 }}>
      <GreenNavBar>我守护的人</GreenNavBar>

      {/* [BUGFIX-MY-GUARDIAN-CARD-2-20260528] 顶部统计栏：
          - 第 1 点：卡片外面只显示 X/Y（紧凑摘要）
          - 第 2 点：本人卡片"上方"统计文案改为「守护人：X 人，还可邀请 Y 位，共 M 位」+「本人不占名额」小字
            （为减少冗余，仅保留一处统计区，文案合并展示） */}
      <div
        data-testid='guardian-v131-summary-bar'
        style={{
          margin: '8px 16px 0', padding: '12px 14px',
          background: `linear-gradient(135deg, ${SKY_100} 0%, ${SKY_50} 100%)`,
          borderRadius: 12, border: `1px solid ${SKY_BORDER}`,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
          <div style={{ fontSize: 16, color: SKY_700, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 4 }}>
            <span>💙</span>
            <span>我守护的人</span>
          </div>
          {/* 第 1 点：紧凑 X/Y */}
          <div data-testid='guard-xy' style={{ fontSize: 15, color: SKY_700, fontWeight: 700 }}>
            {resp ? (
              <>守护人 <b style={{ fontSize: 17 }}>{guardCount}</b>/<b style={{ fontSize: 17 }}>{maxGuard}</b></>
            ) : (
              <>加载中…</>
            )}
          </div>
        </div>
        {/* 第 2 点：本人卡片"上方"完整统计文案 */}
        <div data-testid='guard-stats-text' style={{ fontSize: 13, color: SKY_700, fontWeight: 500, marginTop: 6 }}>
          {resp ? (
            <>
              守护人：<b style={{ color: SKY_700 }}>{guardCount}</b> 人，还可邀请{' '}
              <b style={{ color: SKY_700 }}>{Math.max(0, canInvite)}</b> 位，共{' '}
              <b style={{ color: SKY_700 }}>{maxGuard}</b> 位
            </>
          ) : null}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
          <span style={{ fontSize: 11, color: TEXT_SECONDARY }}>本人不占名额</span>
          {/* [Bug 4/10] 右上角 + 发起邀请，使用主操作按钮配色 */}
          <button
            data-testid='top-invite-btn'
            style={{ ...BTN_STYLES.primary, padding: '6px 14px', fontSize: 12 }}
            onClick={handleInvite}
          >
            + 发起邀请
          </button>
        </div>
      </div>

      <div style={{ padding: '12px 16px' }}>
        {/* 本人卡片 */}
        <div
          data-testid='guardian-v131-self-card'
          style={{
            background: '#fff', borderRadius: 16, padding: 14, marginBottom: 14,
            boxShadow: '0 2px 8px rgba(14, 165, 233, 0.08)', border: `1.5px solid ${SKY_BORDER}`,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
            <div style={{
              width: 44, height: 44, borderRadius: '50%',
              background: `linear-gradient(135deg, ${SKY_500} 0%, ${SKY_700} 100%)`,
              color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 16, fontWeight: 700, marginRight: 12,
            }}>我</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: TEXT_PRIMARY }}>
                {me.nickname || '本人'}（本人）
              </div>
              <div style={{ fontSize: 12, color: TEXT_SECONDARY, marginTop: 2 }}>
                我的健康档案与额度
              </div>
            </div>
          </div>
          {/* [BUGFIX-MY-PROFILE-4ITEMS-20260528 修复 4] 本人卡片 3 个按钮高度统一为 28px：
              padding 仅控水平间距，lineHeight=1，box-sizing border-box，避免 primary/secondary
              因不同 padding 导致高度不齐 */}
          <div style={{ display: 'flex', gap: 8 }}>
            {/* [Bug 2] 本人编辑档案 → Hero 抽屉可编辑 */}
            <button
              data-testid='btn-self-edit'
              style={{
                ...BTN_STYLES.secondary,
                flex: 1,
                height: 28,
                lineHeight: '1',
                padding: '0 14px',
                fontSize: 12,
                boxSizing: 'border-box',
              }}
              onClick={() => setProfileDrawer({ open: true, memberUserId: me.id, readOnly: false })}
            >
              编辑档案
            </button>
            <button
              style={{
                ...BTN_STYLES.secondary,
                flex: 1,
                height: 28,
                lineHeight: '1',
                padding: '0 14px',
                fontSize: 12,
                boxSizing: 'border-box',
              }}
              onClick={() => setHistoryDrawer({ open: true, card: { manager_user_id: me.id } as any })}
            >
              邀请记录
            </button>
            <button
              style={{
                ...BTN_STYLES.primary,
                flex: 1,
                height: 28,
                lineHeight: '1',
                padding: '0 14px',
                fontSize: 12,
                boxSizing: 'border-box',
              }}
              onClick={() => router.push('/member-center#quota')}
            >
              AI 外呼额度
            </button>
          </div>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: TEXT_SECONDARY }}>加载中…</div>
        ) : (
          <>
            {/* 已绑定区 */}
            <div
              data-testid='guardian-v131-bound-zone'
              style={{
                background: `linear-gradient(135deg, ${SKY_100} 0%, ${SKY_50} 100%)`,
                border: `1px solid ${SKY_BORDER}`, borderRadius: 16, padding: 12, marginBottom: 14,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: SKY_700, padding: '4px 4px 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>💙</span><span>已绑定</span>
                <span style={{ background: SKY_500, color: '#fff', borderRadius: 10, padding: '1px 8px', fontSize: 11 }}>{boundItems.length}</span>
                <span style={{ fontSize: 11, fontWeight: 400, color: TEXT_SECONDARY, marginLeft: 4 }}>位</span>
              </div>
              {boundItems.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '20px 0', color: TEXT_SECONDARY, fontSize: 13 }}>
                  暂无已绑定的家人，邀请家人开始守护吧
                </div>
              ) : (
                boundItems.map((it, idx) => renderCard(it, idx, 'bound'))
              )}
            </div>

            {/* 未绑定区 */}
            <div
              data-testid='guardian-v131-unbound-zone'
              style={{
                background: `linear-gradient(135deg, ${SLATE_100} 0%, ${SLATE_50} 100%)`,
                border: `1px solid ${SLATE_BORDER}`, borderRadius: 16, padding: 12,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: TEXT_PRIMARY, padding: '4px 4px 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>📋</span><span>未绑定</span>
                <span style={{ background: TEXT_SECONDARY, color: '#fff', borderRadius: 10, padding: '1px 8px', fontSize: 11 }}>{unboundItems.length}</span>
                <span style={{ fontSize: 11, fontWeight: 400, color: TEXT_SECONDARY, marginLeft: 4 }}>位</span>
              </div>
              {unboundItems.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '20px 0', color: TEXT_SECONDARY, fontSize: 13 }}>
                  暂无未绑定的家人档案
                </div>
              ) : (
                unboundItems.map((it, idx) => renderCard(it, idx, 'unbound'))
              )}
            </div>
          </>
        )}
      </div>

      {/* 上限弹窗 */}
      <Modal
        visible={showLimit}
        title='💝 温馨提示'
        content={
          <div style={{ padding: '8px 0' }}>
            您当前守护人数已满（{resp?.used || 0}/{resp?.max_guardians || 0} 位）。
            <br />
            如需守护更多家人，可升级会员套餐，最高可守护更多位。
          </div>
        }
        actions={[
          [
            { key: 'cancel', text: '再想想' },
            { key: 'upgrade', text: '升级会员', primary: true, onClick: () => { setShowLimit(false); router.push('/member-center#plans'); } },
          ],
        ]}
        onClose={() => setShowLimit(false)}
      />

      {/* [Bug 4/7] 公共邀请抽屉 */}
      <InviteGuardianDrawer
        open={inviteDrawer.open}
        mode={inviteDrawer.mode}
        presetMember={inviteDrawer.preset}
        onClose={() => setInviteDrawer({ open: false, mode: 'create' })}
        onSuccess={() => { fetchList(); }}
      />

      {/* [Bug 5] 共享额度抽屉 */}
      <SharedQuotaDrawer
        open={quotaDrawer.open}
        card={quotaDrawer.card}
        onClose={() => setQuotaDrawer({ open: false, card: null })}
        onRefresh={fetchList}
      />

      {/* [Bug 2/3] 档案抽屉 */}
      <ProfileEditDrawer
        open={profileDrawer.open}
        memberUserId={profileDrawer.memberUserId}
        memberId={profileDrawer.memberId}
        readOnly={profileDrawer.readOnly}
        onClose={() => setProfileDrawer({ open: false, readOnly: false })}
      />

      {/* [Bug 9] 邀请记录抽屉 */}
      <InviteHistoryDrawer
        open={historyDrawer.open}
        card={historyDrawer.card}
        onClose={() => setHistoryDrawer({ open: false, card: null })}
      />
    </div>
  );
}
