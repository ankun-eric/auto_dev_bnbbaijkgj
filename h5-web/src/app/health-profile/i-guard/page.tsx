'use client';

/**
 * [健康档案优化 PRD v1.0 2026-05-26]
 * 我守护的人 - 直筒列表（按"守护中/待守护"两态分组）
 * - 顶部：待确认转让横幅（接收者同意/拒绝；发起者取消）
 * - 本人行：编辑档案 | 邀请记录 | 我的 AI 外呼额度
 * - 被守护人行：查看档案 | 提醒设置 | 守护管理
 */
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Dialog, Tag, Button, Empty, Switch } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface IGuardItem {
  management_id: number;
  manager_user_id: number;
  managed_user_id: number;
  managed_user_nickname?: string;
  relation_label?: string;
  // [BUGFIX-HEALTHPROFILE-GUARDIAN-CARDS-20260527] 后端可能返回 'self'
  role_badge: 'primary' | 'normal' | 'self';
  is_primary_guardian: boolean;
  proxy_pay_enabled: boolean;
  status: string;
  created_at: string;
  // [BUGFIX-HEALTHPROFILE-GUARDIAN-CARDS-20260527] 后端注入的"本人"虚拟项
  is_self?: boolean;
}

interface PendingTransfer {
  transfer_id: number;
  managed_user_id: number;
  managed_user_nickname?: string;
  from_user_id: number;
  from_user_nickname?: string;
  to_user_id: number;
  to_user_nickname?: string;
  created_at?: string;
  expires_at?: string;
}

interface GuardianInDrawer {
  management_id: number;
  manager_user_id: number;
  manager_nickname?: string;
  manager_phone?: string;
  relation_label?: string;
  role_badge: 'primary' | 'normal';
  is_primary_guardian: boolean;
  is_paid_member: boolean;
  is_self: boolean;
  created_at: string;
}

interface Reminder {
  id: number;
  setter_user_id: number;
  setter_nickname?: string;
  setter_is_me: boolean;
  title: string;
  content?: string;
  reminder_type: string;
  can_edit: boolean;
}

const PRIMARY = '#1890FF';
const PRIMARY_DARK = '#096DD9';
const PRIMARY_BG = '#E6F7FF';
const PAGE_BG = '#F0F8FF';
const WARN = '#FAAD14';
const DANGER = '#FF4D4F';
const SUCCESS = '#52C41A';

export default function IGuardPage() {
  const router = useRouter();
  const [items, setItems] = useState<IGuardItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [activeCount, setActiveCount] = useState<number>(0);
  const [maxManaged, setMaxManaged] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [me, setMe] = useState<{ id: number; nickname?: string }>({ id: 0 });

  // [健康档案优化 PRD v1.0 §3.5] 待确认转让横幅
  const [pendingSent, setPendingSent] = useState<PendingTransfer[]>([]);
  const [pendingReceived, setPendingReceived] = useState<PendingTransfer[]>([]);

  // 守护管理抽屉
  const [drawerManaged, setDrawerManaged] = useState<IGuardItem | null>(null);
  const [drawerGuardians, setDrawerGuardians] = useState<GuardianInDrawer[]>([]);
  const [drawerProxyPay, setDrawerProxyPay] = useState(false);

  // 提醒设置抽屉
  const [remindManaged, setRemindManaged] = useState<IGuardItem | null>(null);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [remindMeta, setRemindMeta] = useState<{
    my_remaining_quota: number;
    my_total_quota: number;
    proxy_pay_payer_nickname?: string;
  } | null>(null);

  // 邀请记录抽屉
  const [showInviteRec, setShowInviteRec] = useState(false);
  const [inviteRecords, setInviteRecords] = useState<any[]>([]);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const meRes: any = await api.get('/api/users/me');
      const meData = meRes.data || meRes;
      setMe({ id: meData.id, nickname: meData.nickname });

      const res: any = await api.get('/api/guardian/v12/i-guard');
      const data = res.data || res;
      setItems(Array.isArray(data.items) ? data.items : []);
      setTotalCount(Number(data.total_count ?? data.total ?? 0));
      setActiveCount(Number(data.active_count ?? 0));
      setMaxManaged(Number(data.max_managed || 0));
    } catch (e: any) {
      console.error(e);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // [健康档案优化 PRD v1.0 §3.5] 拉取待确认转让列表
  const fetchPendingTransfers = useCallback(async () => {
    try {
      const res: any = await api.get('/api/guardian/v12/transfer/pending');
      const data = res.data || res;
      setPendingSent(Array.isArray(data.sent) ? data.sent : []);
      setPendingReceived(Array.isArray(data.received) ? data.received : []);
    } catch {
      setPendingSent([]);
      setPendingReceived([]);
    }
  }, []);

  useEffect(() => {
    fetchList();
    fetchPendingTransfers();
  }, [fetchList, fetchPendingTransfers]);

  const handleApproveTransfer = async (transferId: number) => {
    const ok = await Dialog.confirm({
      title: '同意主守护人转让',
      content: '同意后您将立即成为该被守护人的主守护人',
    });
    if (!ok) return;
    try {
      await api.post(`/api/guardian/v12/transfer/${transferId}/approve`);
      showToast('已同意', 'success');
      fetchList();
      fetchPendingTransfers();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const handleRejectTransfer = async (transferId: number) => {
    const ok = await Dialog.confirm({
      title: '拒绝主守护人转让',
      content: '拒绝后该申请将作废',
    });
    if (!ok) return;
    try {
      await api.post(`/api/guardian/v12/transfer/${transferId}/reject`);
      showToast('已拒绝');
      fetchPendingTransfers();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const handleCancelTransfer = async (transferId: number) => {
    const ok = await Dialog.confirm({
      title: '取消转让申请',
      content: '取消后该转让申请将作废',
    });
    if (!ok) return;
    try {
      await api.post(`/api/guardian/v12/transfer/${transferId}/cancel`);
      showToast('已取消');
      fetchPendingTransfers();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const openGuardianDrawer = async (it: IGuardItem) => {
    setDrawerManaged(it);
    setDrawerProxyPay(it.proxy_pay_enabled);
    try {
      const res: any = await api.get(`/api/guardian/v12/managed/${it.managed_user_id}/all-guardians`);
      const data = res.data || res;
      setDrawerGuardians(Array.isArray(data.items) ? data.items : []);
    } catch {
      setDrawerGuardians([]);
    }
  };

  const handleProxyPayToggle = async (checked: boolean) => {
    if (!drawerManaged) return;
    try {
      await api.post(`/api/guardian/v12/managed/${drawerManaged.managed_user_id}/proxy-pay`, { enabled: checked });
      setDrawerProxyPay(checked);
      showToast(checked ? '已开启代付' : '已关闭代付');
      fetchList();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const handleTransferPrimary = async (targetMid: number) => {
    const ok = await Dialog.confirm({
      title: '转让主守护人',
      content: '接收者同意后立即生效，确定要转让吗？',
    });
    if (!ok) return;
    try {
      await api.post('/api/guardian/v12/transfer/initiate', { target_management_id: targetMid });
      showToast('转让申请已发起，等待接收者确认', 'success');
      setDrawerManaged(null);
      fetchList();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const handleExitGuard = async () => {
    if (!drawerManaged) return;
    const ok = await Dialog.confirm({
      title: '退出守护',
      content: `退出后将无法继续守护 ${drawerManaged.managed_user_nickname || ''}`,
    });
    if (!ok) return;
    try {
      await api.post('/api/reverse-guardian/remove', { management_id: drawerManaged.management_id });
      showToast('已退出守护', 'success');
      setDrawerManaged(null);
      fetchList();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const handleRemoveOther = async (g: GuardianInDrawer) => {
    if (!drawerManaged) return;
    const ok = await Dialog.confirm({
      title: '移除守护人',
      content: `确定要移除 ${g.manager_nickname || '该守护人'} 吗？`,
    });
    if (!ok) return;
    try {
      await api.post('/api/reverse-guardian/remove', { management_id: g.management_id });
      showToast('已移除', 'success');
      // 刷新抽屉
      const res: any = await api.get(`/api/guardian/v12/managed/${drawerManaged.managed_user_id}/all-guardians`);
      setDrawerGuardians((res.data || res).items || []);
      fetchList();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const openRemindersDrawer = async (it: IGuardItem) => {
    setRemindManaged(it);
    try {
      const res: any = await api.get(`/api/guardian/v12/reminders/${it.managed_user_id}`);
      const data = res.data || res;
      setReminders(Array.isArray(data.items) ? data.items : []);
      setRemindMeta({
        my_remaining_quota: data.my_remaining_quota,
        my_total_quota: data.my_total_quota,
        proxy_pay_payer_nickname: data.proxy_pay_payer_nickname,
      });
    } catch {
      setReminders([]);
    }
  };

  const handleDeleteReminder = async (rid: number) => {
    const ok = await Dialog.confirm({ title: '删除提醒', content: '确定要删除这条 AI 外呼提醒吗？' });
    if (!ok) return;
    try {
      await api.delete(`/api/guardian/v12/reminders/${rid}`);
      showToast('已删除');
      if (remindManaged) openRemindersDrawer(remindManaged);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const openInviteRecords = async () => {
    setShowInviteRec(true);
    try {
      const res: any = await api.get('/api/guardian/v12/invitations/records');
      const data = res.data || res;
      setInviteRecords(Array.isArray(data.items) ? data.items : []);
    } catch {
      setInviteRecords([]);
    }
  };

  const fmtDate = (s?: string) => {
    if (!s) return '—';
    try { return new Date(s).toISOString().slice(0, 10); } catch { return s; }
  };

  return (
    <div style={{ background: PAGE_BG, minHeight: '100vh', paddingBottom: 32 }}>
      <GreenNavBar>我守护的人</GreenNavBar>

      {/* [健康档案优化 PRD v1.0 §3.5] 待确认转让横幅 */}
      {pendingReceived.map((tr) => (
        <div
          key={`recv-${tr.transfer_id}`}
          data-testid='transfer-banner-received'
          style={{
            margin: '8px 16px',
            padding: '12px 14px',
            background: 'linear-gradient(135deg, #FFE7BA 0%, #FFD591 100%)',
            color: '#874D00',
            borderRadius: 12,
            border: '1px solid #FFC069',
            boxShadow: '0 4px 12px rgba(250, 173, 20, 0.18)',
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
            🔔 {tr.from_user_nickname || '某守护人'} 申请将{tr.managed_user_nickname ? ` ${tr.managed_user_nickname} 的` : ''}主守护人转让给您
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button
              size='mini'
              color='primary'
              fill='solid'
              style={{ flex: 1, borderRadius: 22 }}
              data-testid='transfer-banner-approve'
              onClick={() => handleApproveTransfer(tr.transfer_id)}
            >同意</Button>
            <Button
              size='mini'
              color='default'
              fill='outline'
              style={{ flex: 1, borderRadius: 22 }}
              data-testid='transfer-banner-reject'
              onClick={() => handleRejectTransfer(tr.transfer_id)}
            >拒绝</Button>
          </div>
        </div>
      ))}
      {pendingSent.map((tr) => (
        <div
          key={`sent-${tr.transfer_id}`}
          data-testid='transfer-banner-sent'
          style={{
            margin: '8px 16px',
            padding: '12px 14px',
            background: PRIMARY_BG,
            color: PRIMARY_DARK,
            borderRadius: 12,
            border: `1px solid ${PRIMARY}`,
          }}
        >
          <div style={{ fontSize: 13, marginBottom: 8 }}>
            ⏳ 您发起的主守护人转让待 {tr.to_user_nickname || '对方'} 确认（{tr.managed_user_nickname ? `被守护人：${tr.managed_user_nickname}` : ''}）
          </div>
          <div>
            <Button
              size='mini'
              color='default'
              fill='outline'
              style={{ borderRadius: 22 }}
              data-testid='transfer-banner-cancel'
              onClick={() => handleCancelTransfer(tr.transfer_id)}
            >取消转让</Button>
          </div>
        </div>
      ))}

      <div style={{ padding: '12px 16px' }}>
        {/* 本人行 */}
        <div style={{
          background: '#fff', borderRadius: 20, padding: 16, marginBottom: 12,
          boxShadow: '0 4px 16px rgba(24, 144, 255, 0.08)',
          border: `1px solid ${PRIMARY_BG}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
            <div style={{
              width: 48, height: 48, borderRadius: '50%',
              background: `linear-gradient(135deg, ${PRIMARY} 0%, ${PRIMARY_DARK} 100%)`,
              color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 18, fontWeight: 700, marginRight: 12,
            }}>我</div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 16, fontWeight: 700, color: '#1a1a1a' }}>
                  {me.nickname || '本人'}
                </span>
                {/* [BUGFIX-HEALTHPROFILE-GUARDIAN-CARDS-20260527] 本人徽章 */}
                <Tag data-testid='i-guard-self-badge' color='primary' fill='solid' style={{ background: PRIMARY }}>本人</Tag>
              </div>
              <div style={{ fontSize: 12, color: '#8C8C8C', marginTop: 2 }}>
                我的健康档案与额度
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button size='mini' color='primary' fill='outline' style={{ flex: 1, borderRadius: 22 }}
              data-testid='i-guard-self-edit'
              onClick={() => router.push('/health-profile?member_id=self')}>编辑档案</Button>
            <Button size='mini' color='primary' fill='outline' style={{ flex: 1, borderRadius: 22 }}
              onClick={openInviteRecords}>邀请记录</Button>
            <Button size='mini' color='primary' fill='solid' style={{ flex: 1, borderRadius: 22 }}
              data-testid='i-guard-self-quota-entry'
              onClick={() => router.push('/member-center#quota')}>我的 AI 外呼额度</Button>
          </div>
        </div>

        {/* [健康档案优化 PRD v1.0 §3.6] 被守护人列表（按守护中 / 待守护分组） */}
        {(() => {
          if (loading) {
            return <div style={{ textAlign: 'center', padding: 40, color: '#8C8C8C' }}>加载中…</div>;
          }
          if (items.length === 0) {
            return <Empty description="还没有守护的人" />;
          }
          // [BUGFIX-HEALTHPROFILE-GUARDIAN-CARDS-20260527] 后端在 items[0] 注入了"本人"虚拟项；
          // 顶部已有独立的"本人行"卡片渲染（含编辑档案/邀请记录/外呼额度），这里需排除避免重复显示。
          const realItems = items.filter((it) => !it.is_self);
          const activeItems = realItems.filter((it) => it.status === 'active');
          const pendingItems = realItems.filter((it) => it.status !== 'active');

          const renderItem = (it: IGuardItem, readOnly: boolean) => (
            <div key={it.management_id} data-testid={`i-guard-item-${it.management_id}`} style={{
              background: '#fff', borderRadius: 20, padding: 16, marginBottom: 12,
              boxShadow: '0 4px 16px rgba(24, 144, 255, 0.08)',
              opacity: readOnly ? 0.7 : 1,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
                <div style={{
                  width: 48, height: 48, borderRadius: '50%',
                  background: PRIMARY_BG, color: PRIMARY,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 18, fontWeight: 700, marginRight: 12,
                }}>{(it.managed_user_nickname || '?').charAt(0)}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 16, fontWeight: 700, color: '#1a1a1a' }}>
                      {it.managed_user_nickname || '—'}
                    </span>
                    {it.role_badge === 'primary' ? (
                      <Tag color='primary' fill='solid' style={{ background: PRIMARY }}>主守护人</Tag>
                    ) : (
                      <Tag color='default'>普通守护人</Tag>
                    )}
                    {it.proxy_pay_enabled && (
                      <Tag color='warning' style={{ background: WARN }}>代付中</Tag>
                    )}
                    {readOnly && (
                      <Tag color='default'>{it.status === 'cancelled' ? '已解除' : '待守护'}</Tag>
                    )}
                  </div>
                  <div style={{ fontSize: 12, color: '#8C8C8C', marginTop: 4 }}>
                    关系：{it.relation_label || '亲友'} · 守护开始 {fmtDate(it.created_at)}
                  </div>
                </div>
              </div>
              {!readOnly && (
                <div style={{ display: 'flex', gap: 8 }}>
                  <Button size='mini' fill='outline' style={{ flex: 1, borderRadius: 22, borderColor: PRIMARY, color: PRIMARY }}
                    onClick={() => router.push(`/health-profile?member_user_id=${it.managed_user_id}`)}>
                    查看档案
                  </Button>
                  <Button size='mini' fill='outline' style={{ flex: 1, borderRadius: 22, borderColor: PRIMARY, color: PRIMARY }}
                    onClick={() => openRemindersDrawer(it)}>
                    提醒设置
                  </Button>
                  <Button size='mini' fill='solid' style={{ flex: 1, borderRadius: 22, background: PRIMARY }}
                    onClick={() => openGuardianDrawer(it)}>
                    守护管理
                  </Button>
                </div>
              )}
            </div>
          );

          return (
            <>
              <div data-testid='i-guard-group-active'>
                <div style={{ fontSize: 13, fontWeight: 600, color: PRIMARY_DARK, margin: '4px 4px 8px' }}>
                  ✅ 守护中（{activeItems.length}）
                </div>
                {activeItems.length === 0 ? (
                  <div style={{
                    padding: 14, marginBottom: 12, borderRadius: 12,
                    background: '#fff', color: '#8C8C8C', textAlign: 'center', fontSize: 13,
                  }}>暂无守护中的人</div>
                ) : (
                  activeItems.map((it) => renderItem(it, false))
                )}
              </div>
              {pendingItems.length > 0 && (
                <div data-testid='i-guard-group-pending' style={{ marginTop: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#8C8C8C', margin: '4px 4px 8px' }}>
                    ⏸ 待守护 / 已解除（{pendingItems.length}）
                  </div>
                  {pendingItems.map((it) => renderItem(it, true))}
                </div>
              )}
            </>
          );
        })()}

        <div style={{ marginTop: 16, padding: '12px 16px', background: PRIMARY_BG, borderRadius: 12, fontSize: 12, color: PRIMARY_DARK }}>
          💡 您目前守护 {activeCount} 人（共 {totalCount} 条守护记录）{maxManaged > 0 ? `，上限 ${maxManaged === -1 ? '不限' : maxManaged}` : ''}。
          {maxManaged > 0 && activeCount >= maxManaged && maxManaged !== -1 && (
            <span style={{ color: DANGER, marginLeft: 4 }}>已达上限，可升级会员扩容</span>
          )}
        </div>
      </div>

      {/* 守护管理抽屉 */}
      {drawerManaged && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 999,
          display: 'flex', alignItems: 'flex-end',
        }} onClick={() => setDrawerManaged(null)}>
          <div style={{
            background: '#fff', width: '100%', borderTopLeftRadius: 24, borderTopRightRadius: 24,
            padding: '16px 16px 32px', maxHeight: '85vh', overflow: 'auto',
          }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>
              守护管理 - {drawerManaged.managed_user_nickname || ''}
            </div>

            {drawerManaged.role_badge === 'primary' && (
              <div style={{
                padding: 12, background: PRIMARY_BG, borderRadius: 12, marginBottom: 12,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a' }}>代付该被守护人的 AI 外呼额度</div>
                  <div style={{ fontSize: 12, color: '#8C8C8C', marginTop: 4 }}>开启后，对方自己设置的提醒扣您的额度</div>
                </div>
                <Switch checked={drawerProxyPay} onChange={handleProxyPayToggle} />
              </div>
            )}

            {drawerGuardians.map((g) => (
              <div key={g.management_id} style={{
                padding: 12, border: '1px solid #f0f0f0', borderRadius: 12, marginBottom: 8,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontWeight: 600 }}>{g.manager_nickname || '—'}{g.is_self ? '（我）' : ''}</span>
                    {g.is_primary_guardian ? (
                      <Tag color='primary' fill='solid' style={{ background: PRIMARY }}>主</Tag>
                    ) : (
                      <Tag color='default'>普通</Tag>
                    )}
                    {g.is_paid_member && <Tag color='warning'>付费</Tag>}
                  </div>
                  <div style={{ fontSize: 12, color: '#8C8C8C', marginTop: 4 }}>
                    {g.relation_label || '亲友'} · 守护开始 {fmtDate(g.created_at)}
                  </div>
                </div>
                <div>
                  {g.is_self ? (
                    g.is_primary_guardian ? (
                      <Button size='mini' color='primary' onClick={() => {
                        const others = drawerGuardians.filter(x => !x.is_self);
                        if (others.length === 0) {
                          showToast('暂无其他守护人可转让', 'fail');
                          return;
                        }
                        // 简化版：选第一个其他守护人
                        const tgt = others[0];
                        Dialog.confirm({
                          title: '转让主守护人',
                          content: `转让给 ${tgt.manager_nickname}？接收者同意后立即生效。`,
                        }).then(ok => ok && handleTransferPrimary(tgt.management_id));
                      }}>转让主守护人</Button>
                    ) : (
                      <Button size='mini' color='danger' onClick={handleExitGuard}>退出守护</Button>
                    )
                  ) : drawerManaged.is_primary_guardian && !g.is_primary_guardian ? (
                    <Button size='mini' color='danger' fill='outline' onClick={() => handleRemoveOther(g)}>移除</Button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 提醒设置抽屉 */}
      {remindManaged && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 999,
          display: 'flex', alignItems: 'flex-end',
        }} onClick={() => setRemindManaged(null)}>
          <div style={{
            background: '#fff', width: '100%', borderTopLeftRadius: 24, borderTopRightRadius: 24,
            padding: '16px 16px 32px', maxHeight: '85vh', overflow: 'auto',
          }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
              提醒设置 - {remindManaged.managed_user_nickname || ''}
            </div>
            {remindMeta && (
              <div style={{ padding: 10, background: PRIMARY_BG, borderRadius: 8, fontSize: 12, color: PRIMARY_DARK, marginBottom: 12 }}>
                我的本月 AI 外呼剩余：
                {remindMeta.my_total_quota === -1 ? '不限' :
                  <strong style={{ color: remindMeta.my_remaining_quota <= 2 ? WARN : PRIMARY }}>
                    {' '}{remindMeta.my_remaining_quota} / {remindMeta.my_total_quota}
                  </strong>
                }
                {remindMeta.proxy_pay_payer_nickname && (
                  <div style={{ marginTop: 4, color: WARN }}>
                    💰 您的 AI 外呼额度由 {remindMeta.proxy_pay_payer_nickname} 代付中
                  </div>
                )}
              </div>
            )}

            {reminders.length === 0 ? (
              <Empty description="还没有 AI 外呼提醒" />
            ) : reminders.map(r => (
              <div key={r.id} style={{ padding: 12, border: '1px solid #f0f0f0', borderRadius: 12, marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600 }}>{r.title}</div>
                    {r.content && <div style={{ fontSize: 12, color: '#8C8C8C', marginTop: 4 }}>{r.content}</div>}
                    <div style={{ fontSize: 12, color: '#8C8C8C', marginTop: 4 }}>
                      由 {r.setter_nickname || '—'} 设置{r.setter_is_me ? '（我）' : ''}
                    </div>
                  </div>
                  {r.can_edit && (
                    <Button size='mini' color='danger' fill='outline' onClick={() => handleDeleteReminder(r.id)}>删除</Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 邀请记录抽屉 */}
      {showInviteRec && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 999,
          display: 'flex', alignItems: 'flex-end',
        }} onClick={() => setShowInviteRec(false)}>
          <div style={{
            background: '#fff', width: '100%', borderTopLeftRadius: 24, borderTopRightRadius: 24,
            padding: '16px 16px 32px', maxHeight: '85vh', overflow: 'auto',
          }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>邀请记录</div>
            {inviteRecords.length === 0 ? <Empty description="暂无邀请记录" /> :
              inviteRecords.map((rec, idx) => (
                <div key={idx} style={{ padding: 12, border: '1px solid #f0f0f0', borderRadius: 12, marginBottom: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontWeight: 600 }}>
                      {rec.direction === 'sent' ? '我发起的' : '别人邀请我的'}
                    </span>
                    <Tag color={rec.status_color === 'success' ? 'success'
                      : rec.status_color === 'warning' ? 'warning'
                      : rec.status_color === 'info' ? 'primary' : 'default'}>{rec.status_label}</Tag>
                  </div>
                  <div style={{ fontSize: 12, color: '#8C8C8C', marginTop: 4 }}>
                    {rec.relation_type ? `关系：${rec.relation_type}` : ''} · 创建 {fmtDate(rec.created_at)}
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
