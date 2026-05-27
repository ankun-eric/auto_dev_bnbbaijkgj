'use client';

/**
 * [守护人体系 PRD v1.3.1 2026-05-27] 健康档案统一列表与已绑定/未绑定重构
 *
 * v1.3.1 关键变更（在 v1.3 基础上做结构性修订）：
 * - 取消两 Tab（守护中 / 待守护），整页一个大列表 + 两区色块卡组（已绑定 / 未绑定）
 * - 系统天蓝色 #0EA5E9 作为主色
 * - 已绑定卡组浅天蓝色背景（#E0F2FE → #F0F9FF），未绑定卡组浅灰背景（#F1F5F9 → #F8FAFC）
 * - 用户可见层术语清理：禁用「共管 / 代管 / 已拒绝」，柔化为「建立于 / 由我代为管理 / 暂未响应」
 * - 顶部一行式统计：「守护 X 位家人 · 还可邀请 Y 位 / 共 Z 位」+ 「本人不占名额」
 * - 排序：两区都按 created_at ASC 正序（老朋友先）
 * - 配额公式动态读取后端（不再写死 10）
 */
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Dialog, Tag, Button, Empty, Switch, Modal } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

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
  // v1.3.1 新增
  bind_status?: BindStatus;
  display_substatus_label?: string;
  is_orphan?: boolean;
  occupies_quota?: boolean;

  invite_code?: string;
  invite_expires_at?: string;
  invite_remaining_hours?: number;
  proxy_pay_enabled: boolean;
  has_bound_device: boolean;
  has_active_med_plan: boolean;
  can_remove: boolean;
  created_at?: string;
}

interface FamilyListResp {
  items: FamilyItemV13[];
  total: number;
  // v1.3 兼容
  tab_active_count: number;
  tab_pending_count: number;
  // v1.3.1 新增
  bound_count?: number;
  unbound_count?: number;
  quota_used?: number;
  // 配额
  max_guardians: number;
  used: number;
  can_invite_count: number;
  is_paid_member: boolean;
}

// [PRD-V1.3.1 §3.1] 系统天蓝色配色（与 health-profile 主页一致）
const SKY_500 = '#0EA5E9';   // 主色
const SKY_700 = '#0369A1';   // 主色深
const SKY_100 = '#E0F2FE';   // 已绑定卡组背景渐变起
const SKY_50 = '#F0F9FF';    // 已绑定卡组背景渐变止
const SKY_BORDER = '#BAE6FD'; // 已绑定描边
const SLATE_100 = '#F1F5F9'; // 未绑定卡组背景渐变起
const SLATE_50 = '#F8FAFC';  // 未绑定卡组背景渐变止
const SLATE_BORDER = '#E2E8F0'; // 未绑定描边
const PAGE_BG = '#F0F9FF';   // 整页背景：浅天蓝色
const GOLD = '#FFB800';      // 主守护人徽章金色（保留 v1.3）
const DANGER = '#FF4D4F';
const TEXT_PRIMARY = '#0F172A';
const TEXT_SECONDARY = '#64748B';

// [PRD-V1.3.1 §1.3] 用户可见层术语映射（柔化）
const DISPLAY_LIFECYCLE_LABEL: Record<Lifecycle, string> = {
  never_invited: '尚未邀请',
  inviting: '邀请中',
  accepted: '建立于',  // 禁用「共管」
  rejected: '暂未响应', // 禁用「已拒绝」
  unbound: '已解绑',
  expired: '已过期',
};

export default function IGuardPage() {
  const router = useRouter();
  const [resp, setResp] = useState<FamilyListResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [me, setMe] = useState<{ id: number; nickname?: string }>({ id: 0 });

  // 代付明细弹窗
  const [payDetailModal, setPayDetailModal] = useState<FamilyItemV13 | null>(null);
  const [payDetail, setPayDetail] = useState<any | null>(null);

  // 邀请记录弹窗
  const [historyModal, setHistoryModal] = useState<FamilyItemV13 | null>(null);
  const [history, setHistory] = useState<any[]>([]);

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
      console.error('[v131] fetchList error', e);
      setResp(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // [PRD-V1.3.1 §1.1] 整页一个大列表，无 Tab，按 bind_status 分两区
  const allItems = resp?.items || [];
  const boundItems = allItems.filter((it) => (it.bind_status || (it.status === 'active' ? 'bound' : 'unbound')) === 'bound');
  const unboundItems = allItems.filter((it) => (it.bind_status || (it.status === 'active' ? 'bound' : 'unbound')) === 'unbound');

  // [PRD-V1.3.1 §2.3] 顶部统计公式
  const guardingCount = (resp?.bound_count ?? boundItems.length) + (resp?.unbound_count ?? unboundItems.length)
    - allItems.filter((it) => !(it.occupies_quota ?? (it.status === 'active' || it.invite_lifecycle === 'inviting' || it.invite_lifecycle === 'never_invited'))).length;
  const canInvite = resp?.can_invite_count ?? 0;
  const maxGuard = resp?.max_guardians ?? 0;

  const handleInvite = () => {
    if (canInvite <= 0) {
      setShowLimit(true);
      return;
    }
    router.push('/health-profile?action=invite');
  };

  const handleCancelInvite = async (it: FamilyItemV13) => {
    if (!it.invite_code) return;
    const ok = await Dialog.confirm({
      title: '取消邀请',
      content: '取消后该邀请将作废，对方扫码会提示无效',
    });
    if (!ok) return;
    try {
      await api.post('/api/guardian/v13/family/invite/cancel', {
        invite_code: it.invite_code,
      });
      showToast('邀请已取消', 'success');
      fetchList();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const handleRemove = async (it: FamilyItemV13) => {
    const ok = await Dialog.confirm({
      title: '移除',
      content:
        '移除后，该档案将从您的列表中消失。若 TA 是您自行添加的家人档案，所有资料将一并删除，此操作不可恢复。',
    });
    if (!ok) return;
    try {
      const body: any = {};
      if (it.managed_user_id) body.managed_user_id = it.managed_user_id;
      if (it.managed_member_id) body.managed_member_id = it.managed_member_id;
      if (!body.managed_user_id && !body.managed_member_id && it.invite_code) {
        showToast('请先取消邀请', 'fail');
        return;
      }
      await api.post('/api/guardian/v13/family/remove', body);
      showToast('已移除', 'success');
      fetchList();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  // [PRD-V1.3.1 §1.3] 「解除守护」按钮文案，弹窗内不出现「共管」
  const handleUnGuard = async (it: FamilyItemV13) => {
    const ok = await Dialog.confirm({
      title: '解除守护',
      content: `将解除与 ${it.managed_user_nickname || 'TA'} 的守护关系，TA 的档案数据完整保留`,
    });
    if (!ok) return;
    try {
      if (it.management_id) {
        await api.post('/api/reverse-guardian/remove', {
          management_id: it.management_id,
        });
      }
      showToast('已解除守护', 'success');
      fetchList();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const handleReinvite = async (_it: FamilyItemV13) => {
    router.push('/health-profile?action=invite');
  };

  const handleViewQr = (it: FamilyItemV13) => {
    if (!it.invite_code) return;
    router.push(`/family-auth?code=${it.invite_code}&role=inviter`);
  };

  const openPayDetail = async (it: FamilyItemV13) => {
    setPayDetailModal(it);
    setPayDetail(null);
    try {
      const res: any = await api.get(
        `/api/guardian/v13/family/proxy-pay/detail?managed_user_id=${it.managed_user_id}`,
      );
      setPayDetail(res.data || res);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '加载失败', 'fail');
    }
  };

  const togglePay = async (it: FamilyItemV13, enabled: boolean) => {
    try {
      await api.post('/api/guardian/v13/family/proxy-pay/toggle', {
        managed_user_id: it.managed_user_id,
        enabled,
      });
      showToast(enabled ? '已开启代付' : '已关闭代付', 'success');
      if (payDetail) setPayDetail({ ...payDetail, enabled });
      fetchList();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const openHistory = async (it: FamilyItemV13) => {
    setHistoryModal(it);
    setHistory([]);
    try {
      const params: string[] = [];
      if (it.managed_user_id) params.push(`managed_user_id=${it.managed_user_id}`);
      if (it.managed_member_id) params.push(`managed_member_id=${it.managed_member_id}`);
      if (it.relation_label && params.length === 0) params.push(`relation_type=${encodeURIComponent(it.relation_label)}`);
      const res: any = await api.get(
        `/api/guardian/v13/family/invite-history${params.length ? '?' + params.join('&') : ''}`,
      );
      const d = res.data || res;
      // 客户端兜底术语柔化（防后端未升级）
      const softItems = (Array.isArray(d.items) ? d.items : []).map((x: any) => ({
        ...x,
        status_label: x?.status_label === '已拒绝' ? '暂未响应' : x?.status_label,
      }));
      setHistory(softItems);
    } catch {
      setHistory([]);
    }
  };

  const fmtDate = (s?: string) => {
    if (!s) return '—';
    try {
      return new Date(s).toISOString().slice(0, 10);
    } catch {
      return s;
    }
  };

  // [PRD-V1.3.1 §1.3] 子状态文案构建（确保不出现「共管 / 代管 / 已拒绝」）
  const buildSubStatusText = (it: FamilyItemV13): string => {
    if (it.display_substatus_label) {
      // 后端已经柔化过的文案，直接使用
      const base = it.display_substatus_label;
      if (it.invite_lifecycle === 'accepted' && it.created_at) {
        return `${base} ${fmtDate(it.created_at)}`;
      }
      if (it.invite_lifecycle === 'inviting' && typeof it.invite_remaining_hours === 'number') {
        return `${base} · 还剩 ${it.invite_remaining_hours} 小时`;
      }
      if (it.invite_lifecycle === 'unbound') {
        return `${base}${it.created_at ? ' · 于 ' + fmtDate(it.created_at) : ''}`;
      }
      if (it.invite_lifecycle === 'expired') {
        return `${base} · 上次邀请已过期`;
      }
      if (it.invite_lifecycle === 'rejected' && it.created_at) {
        return `${base} · 创建于 ${fmtDate(it.created_at)}`;
      }
      return base;
    }
    // 兜底：自己根据 lifecycle 推导
    const lbl = DISPLAY_LIFECYCLE_LABEL[it.invite_lifecycle] || '';
    if (it.invite_lifecycle === 'accepted' && it.created_at) {
      return `${lbl} ${fmtDate(it.created_at)}`;
    }
    if (it.invite_lifecycle === 'inviting' && typeof it.invite_remaining_hours === 'number') {
      return `${lbl} · 还剩 ${it.invite_remaining_hours} 小时`;
    }
    return lbl;
  };

  // ─── 卡片渲染（v1.3.1：天蓝色 + 已绑定/未绑定子徽标 + 术语清理） ────────────
  const renderCard = (it: FamilyItemV13, idx: number, zone: 'bound' | 'unbound') => {
    const isBound = zone === 'bound';
    const cardBg = '#FFFFFF';
    const cardBorder = it.is_primary_guardian
      ? `1.5px solid ${GOLD}`
      : isBound
        ? `1px solid ${SKY_BORDER}`
        : `1px solid ${SLATE_BORDER}`;
    // 未绑定卡片右上角子状态徽标
    const subBadgeBg = isBound ? '#E0F2FE' : '#F1F5F9';
    const subBadgeFg = isBound ? SKY_700 : TEXT_SECONDARY;

    return (
      <div
        key={`${zone}-${it.management_id || 'inv'}-${idx}`}
        data-testid={`family-card-v131-${zone}-${it.invite_lifecycle}`}
        style={{
          background: cardBg,
          borderRadius: 16,
          padding: 14,
          marginBottom: 10,
          boxShadow: '0 2px 8px rgba(14, 165, 233, 0.06)',
          border: cardBorder,
          position: 'relative',
        }}
      >
        {/* 主守护人金色徽章（右上角） */}
        {it.is_primary_guardian && (
          <div
            style={{
              position: 'absolute',
              top: 10,
              right: 10,
              background: GOLD,
              color: '#fff',
              borderRadius: 10,
              padding: '2px 8px',
              fontSize: 10,
              fontWeight: 700,
              boxShadow: '0 2px 6px rgba(255, 184, 0, 0.4)',
              zIndex: 2,
            }}
          >
            👑 主
          </div>
        )}

        {/* 未绑定卡片右下角子状态徽标 */}
        {!isBound && (
          <div
            style={{
              position: 'absolute',
              top: it.is_primary_guardian ? 38 : 10,
              right: 10,
              background: subBadgeBg,
              color: subBadgeFg,
              borderRadius: 8,
              padding: '2px 8px',
              fontSize: 11,
              fontWeight: 600,
              maxWidth: 140,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {buildSubStatusText(it)}
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: '50%',
              background: isBound ? SKY_100 : SLATE_100,
              color: isBound ? SKY_700 : TEXT_SECONDARY,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 16,
              fontWeight: 700,
              marginRight: 12,
              border: `1.5px solid ${isBound ? SKY_BORDER : SLATE_BORDER}`,
            }}
          >
            {(it.managed_user_nickname || it.relation_label || '?').charAt(0)}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: TEXT_PRIMARY, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {it.managed_user_nickname || it.relation_label || '待邀请家人'}
              {it.relation_label && it.managed_user_nickname && (
                <span style={{ fontSize: 12, color: TEXT_SECONDARY, fontWeight: 400, marginLeft: 6 }}>
                  · {it.relation_label}
                </span>
              )}
            </div>
            <div style={{ fontSize: 12, color: TEXT_SECONDARY, marginTop: 4 }}>
              {/* 已绑定卡片在左下角显示「建立于 yyyy-mm-dd」或「由我代为管理」 */}
              {isBound && (it.is_orphan ? '由我代为管理' : buildSubStatusText(it))}
              {isBound && it.proxy_pay_enabled && (
                <Tag color='warning' style={{ marginLeft: 6, background: '#FFF7E6', color: GOLD, border: 'none' }}>
                  代付中
                </Tag>
              )}
            </div>
          </div>
        </div>

        {/* 按钮区：根据 lifecycle 动态显示 */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {isBound ? (
            <>
              <Button
                size='mini'
                fill='outline'
                style={{ flex: 1, borderRadius: 18, borderColor: SKY_500, color: SKY_500 }}
                onClick={() =>
                  router.push(`/health-profile?member_user_id=${it.managed_user_id}`)
                }
              >
                查看档案
              </Button>
              {it.is_primary_guardian && it.managed_user_id && (
                <Button
                  size='mini'
                  fill='outline'
                  style={{ flex: 1, borderRadius: 18, borderColor: GOLD, color: GOLD }}
                  onClick={() => openPayDetail(it)}
                >
                  代付明细
                </Button>
              )}
              {it.is_orphan ? (
                it.can_remove && (
                  <Button
                    size='mini'
                    fill='outline'
                    style={{ flex: 1, borderRadius: 18, borderColor: DANGER, color: DANGER }}
                    onClick={() => handleRemove(it)}
                  >
                    移除
                  </Button>
                )
              ) : (
                <Button
                  size='mini'
                  fill='outline'
                  style={{ flex: 1, borderRadius: 18, borderColor: DANGER, color: DANGER }}
                  onClick={() => handleUnGuard(it)}
                >
                  解除守护
                </Button>
              )}
            </>
          ) : (
            <>
              {it.invite_lifecycle === 'inviting' && (
                <>
                  <Button
                    size='mini'
                    fill='solid'
                    style={{ flex: 1, borderRadius: 18, background: SKY_500 }}
                    onClick={() => handleViewQr(it)}
                  >
                    查看二维码
                  </Button>
                  <Button
                    size='mini'
                    fill='outline'
                    style={{ flex: 1, borderRadius: 18, borderColor: DANGER, color: DANGER }}
                    onClick={() => handleCancelInvite(it)}
                  >
                    取消邀请
                  </Button>
                </>
              )}
              {(it.invite_lifecycle === 'rejected' ||
                it.invite_lifecycle === 'unbound' ||
                it.invite_lifecycle === 'expired') && (
                <>
                  <Button
                    size='mini'
                    fill='solid'
                    style={{ flex: 1, borderRadius: 18, background: SKY_500 }}
                    onClick={() => handleReinvite(it)}
                  >
                    再次邀请
                  </Button>
                  {it.can_remove && (
                    <Button
                      size='mini'
                      fill='outline'
                      style={{ flex: 1, borderRadius: 18, borderColor: DANGER, color: DANGER }}
                      onClick={() => handleRemove(it)}
                    >
                      移除
                    </Button>
                  )}
                </>
              )}
              {it.invite_lifecycle === 'never_invited' && (
                <>
                  <Button
                    size='mini'
                    fill='solid'
                    style={{ flex: 1, borderRadius: 18, background: SKY_500 }}
                    onClick={handleInvite}
                  >
                    发起邀请
                  </Button>
                  {it.can_remove && (
                    <Button
                      size='mini'
                      fill='outline'
                      style={{ flex: 1, borderRadius: 18, borderColor: DANGER, color: DANGER }}
                      onClick={() => handleRemove(it)}
                    >
                      移除
                    </Button>
                  )}
                </>
              )}
              <Button
                size='mini'
                fill='none'
                style={{ borderRadius: 18, color: SKY_500, fontSize: 12 }}
                onClick={() => openHistory(it)}
              >
                邀请记录
              </Button>
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div style={{ background: PAGE_BG, minHeight: '100vh', paddingBottom: 32 }}>
      <GreenNavBar>我守护的人</GreenNavBar>

      {/* [PRD-V1.3.1 §1.1] 顶部统计栏（一行式） */}
      <div
        data-testid='guardian-v131-summary-bar'
        style={{
          margin: '8px 16px 0',
          padding: '12px 14px',
          background: `linear-gradient(135deg, ${SKY_100} 0%, ${SKY_50} 100%)`,
          borderRadius: 12,
          border: `1px solid ${SKY_BORDER}`,
        }}
      >
        <div style={{ fontSize: 14, color: SKY_700, fontWeight: 600, marginBottom: 4 }}>
          {resp ? (
            <>
              守护 <b style={{ color: SKY_700, fontSize: 16 }}>{Math.max(0, guardingCount)}</b> 位家人
              <span style={{ margin: '0 6px', color: TEXT_SECONDARY }}>·</span>
              还可邀请 <b style={{ color: SKY_700, fontSize: 16 }}>{canInvite}</b> 位
              <span style={{ margin: '0 6px', color: TEXT_SECONDARY }}>/</span>
              共 <b style={{ color: SKY_700, fontSize: 16 }}>{maxGuard}</b> 位
            </>
          ) : (
            <>加载中…</>
          )}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: TEXT_SECONDARY }}>本人不占名额</span>
          <Button
            size='mini'
            fill='solid'
            style={{ background: SKY_500, borderRadius: 14, fontSize: 12 }}
            onClick={handleInvite}
          >
            + 发起邀请
          </Button>
        </div>
      </div>

      <div style={{ padding: '12px 16px' }}>
        {/* [PRD-V1.3.1 §1.1] 第 1 行：本人档案（固定首位，永远显示） */}
        <div
          data-testid='guardian-v131-self-card'
          style={{
            background: '#fff',
            borderRadius: 16,
            padding: 14,
            marginBottom: 14,
            boxShadow: '0 2px 8px rgba(14, 165, 233, 0.08)',
            border: `1.5px solid ${SKY_BORDER}`,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: '50%',
                background: `linear-gradient(135deg, ${SKY_500} 0%, ${SKY_700} 100%)`,
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 16,
                fontWeight: 700,
                marginRight: 12,
              }}
            >
              我
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: TEXT_PRIMARY }}>
                {me.nickname || '本人'}（本人）
              </div>
              <div style={{ fontSize: 12, color: TEXT_SECONDARY, marginTop: 2 }}>
                我的健康档案与额度
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button
              size='mini'
              fill='outline'
              style={{ flex: 1, borderRadius: 18, borderColor: SKY_500, color: SKY_500 }}
              onClick={() => router.push('/health-profile')}
            >
              编辑档案
            </Button>
            <Button
              size='mini'
              fill='outline'
              style={{ flex: 1, borderRadius: 18, borderColor: SKY_500, color: SKY_500 }}
              onClick={() => openHistory({ manager_user_id: me.id } as any)}
            >
              邀请记录
            </Button>
            <Button
              size='mini'
              fill='solid'
              style={{ flex: 1, borderRadius: 18, background: SKY_500 }}
              onClick={() => router.push('/member-center#quota')}
            >
              AI 外呼额度
            </Button>
          </div>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: TEXT_SECONDARY }}>加载中…</div>
        ) : (
          <>
            {/* [PRD-V1.3.1 §1.1] 区域 1：已绑定（X 位） — 浅天蓝色卡组 */}
            <div
              data-testid='guardian-v131-bound-zone'
              style={{
                background: `linear-gradient(135deg, ${SKY_100} 0%, ${SKY_50} 100%)`,
                border: `1px solid ${SKY_BORDER}`,
                borderRadius: 16,
                padding: 12,
                marginBottom: 14,
              }}
            >
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: SKY_700,
                  padding: '4px 4px 8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <span>💙</span>
                <span>已绑定</span>
                <span style={{ background: SKY_500, color: '#fff', borderRadius: 10, padding: '1px 8px', fontSize: 11 }}>
                  {boundItems.length}
                </span>
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

            {/* [PRD-V1.3.1 §1.1] 区域 2：未绑定（Y 位） — 浅灰色卡组 */}
            <div
              data-testid='guardian-v131-unbound-zone'
              style={{
                background: `linear-gradient(135deg, ${SLATE_100} 0%, ${SLATE_50} 100%)`,
                border: `1px solid ${SLATE_BORDER}`,
                borderRadius: 16,
                padding: 12,
              }}
            >
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: TEXT_PRIMARY,
                  padding: '4px 4px 8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <span>📋</span>
                <span>未绑定</span>
                <span style={{ background: TEXT_SECONDARY, color: '#fff', borderRadius: 10, padding: '1px 8px', fontSize: 11 }}>
                  {unboundItems.length}
                </span>
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

      {/* [PRD-V1.3.1 §2.4] 上限弹窗：温馨提示（动态文案） */}
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
            {
              key: 'upgrade',
              text: '升级会员',
              primary: true,
              onClick: () => {
                setShowLimit(false);
                router.push('/member-center#plans');
              },
            },
          ],
        ]}
        onClose={() => setShowLimit(false)}
      />

      {/* 代付明细弹窗 */}
      <Modal
        visible={payDetailModal !== null}
        title={`${payDetailModal?.managed_user_nickname || ''} · 代付明细`}
        content={
          payDetail ? (
            <div style={{ padding: '8px 0' }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: 12,
                  padding: 12,
                  background: '#FFF7E6',
                  borderRadius: 8,
                }}
              >
                <span style={{ fontSize: 13 }}>代付开关</span>
                <Switch
                  checked={payDetail.enabled}
                  onChange={(v) =>
                    payDetailModal && togglePay(payDetailModal, v)
                  }
                />
              </div>
              <div style={{ marginBottom: 8, fontSize: 13 }}>
                今日已代付：<b style={{ color: GOLD }}>{payDetail.today_count}</b> 次 · 本月：<b style={{ color: GOLD }}>{payDetail.month_count}</b> 次
              </div>
              <div style={{ maxHeight: 240, overflowY: 'auto' }}>
                {payDetail.items?.length ? (
                  payDetail.items.map((r: any) => (
                    <div
                      key={r.id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        padding: '6px 0',
                        borderBottom: '1px dashed #eee',
                        fontSize: 12,
                      }}
                    >
                      <span>{r.call_type_label}</span>
                      <span style={{ color: TEXT_SECONDARY }}>{fmtDate(r.used_at)}</span>
                    </div>
                  ))
                ) : (
                  <div style={{ textAlign: 'center', color: TEXT_SECONDARY, padding: 12 }}>本月暂无代付记录</div>
                )}
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: 20 }}>加载中…</div>
          )
        }
        actions={[[{ key: 'close', text: '关闭' }]]}
        onClose={() => {
          setPayDetailModal(null);
          setPayDetail(null);
        }}
      />

      {/* 邀请记录弹窗 */}
      <Modal
        visible={historyModal !== null}
        title='邀请记录'
        content={
          <div style={{ padding: '8px 0', maxHeight: 320, overflowY: 'auto' }}>
            {history.length === 0 ? (
              <Empty description='暂无邀请记录' />
            ) : (
              history.map((h: any) => (
                <div
                  key={h.id}
                  style={{
                    padding: '8px 0',
                    borderBottom: '1px dashed #eee',
                    fontSize: 13,
                  }}
                >
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
        }
        actions={[[{ key: 'close', text: '关闭' }]]}
        onClose={() => {
          setHistoryModal(null);
          setHistory([]);
        }}
      />
    </div>
  );
}
