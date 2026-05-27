'use client';

/**
 * [守护人体系 PRD v1.3 2026-05-26] 健康档案融合优化（恢复 v13 完整版 @ 2026-05-27）
 * 我守护的人 - 极简两态 Tab（守护中 / 待守护）+ 子状态卡片
 *
 * 关键变更：
 * - 最外层仅 守护中 / 待守护 两个 Tab
 * - 卡片按 invite_lifecycle 子状态显示不同操作按钮
 * - 主守护人金色徽章 + 4 不可删校验直接不显示移除按钮
 * - 代付明细 + 代付开关入口
 * - 守护中 Tab 首行：本人虚拟项（编辑档案 / 邀请记录 / 我的 AI 外呼额度）
 *
 * 历史：commit 8181069a 落地的 v13 完整版（733 行）于 commit fdc3d00a 被误删，
 *       此次恢复 v13 原版页面，直接挂载到 /health-profile/i-guard 路径。
 */
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Dialog, Tag, Button, Empty, Switch, Tabs, Modal } from 'antd-mobile';
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
  tab_active_count: number;
  tab_pending_count: number;
  max_guardians: number;
  used: number;
  can_invite_count: number;
  is_paid_member: boolean;
}

const PRIMARY = '#1890FF';
const PRIMARY_DARK = '#096DD9';
const PRIMARY_BG = '#E6F7FF';
const PAGE_BG = '#F0F8FF';
const GOLD = '#FFB800';
const DANGER = '#FF4D4F';
const WARN_BG = '#FFF7E6';

const LIFECYCLE_LABEL: Record<Lifecycle, string> = {
  never_invited: '未邀请',
  inviting: '邀请中',
  accepted: '已同意',
  rejected: '已拒绝',
  unbound: '已解绑',
  expired: '已过期',
};

export default function IGuardPage() {
  const router = useRouter();
  const [tab, setTab] = useState<'active' | 'pending'>('active');
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
      console.error('[v13] fetchList error', e);
      setResp(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const filtered = (resp?.items || []).filter((it) =>
    tab === 'active' ? it.status === 'active' : it.status !== 'active'
  );

  const handleInvite = () => {
    if (resp && resp.can_invite_count <= 0) {
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
      // 纯邀请记录（无 mgmt 也无 member）
      if (!body.managed_user_id && !body.managed_member_id && it.invite_code) {
        // 通过 invite_code 找到 invitation_id
        try {
          const inviteRes: any = await api.get(
            `/api/guardian/v13/family/invite-history?managed_member_id=0`,
          );
          // 由后端直接通过 code 取消已不可能（接口设计），改用列表对应卡片的 management_id
        } catch {
          /* ignore */
        }
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

  const handleUnGuard = async (it: FamilyItemV13) => {
    const ok = await Dialog.confirm({
      title: '解除守护',
      content: `将解除与 ${it.managed_user_nickname || 'TA'} 的共管关系，TA 的档案数据完整保留`,
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
    // 再次邀请 = 新建邀请，跳转到邀请页（带 relation 预填可选）
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
      setHistory(Array.isArray(d.items) ? d.items : []);
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

  // 卡片样式
  const renderCard = (it: FamilyItemV13, idx: number) => {
    const isActive = it.status === 'active';
    const subStatus = isActive ? '' : `（${LIFECYCLE_LABEL[it.invite_lifecycle]}）`;

    return (
      <div
        key={`${it.management_id || 'inv'}-${idx}`}
        data-testid={`family-card-v13-${it.invite_lifecycle}`}
        style={{
          background: '#fff',
          borderRadius: 20,
          padding: 16,
          marginBottom: 12,
          boxShadow: '0 4px 16px rgba(24, 144, 255, 0.08)',
          border: it.is_primary_guardian ? `1.5px solid ${GOLD}` : `1px solid ${PRIMARY_BG}`,
          position: 'relative',
        }}
      >
        {/* 主守护人金色徽章（右上角） */}
        {it.is_primary_guardian && (
          <div
            style={{
              position: 'absolute',
              top: 12,
              right: 12,
              background: GOLD,
              color: '#fff',
              borderRadius: 12,
              padding: '2px 10px',
              fontSize: 11,
              fontWeight: 700,
              boxShadow: '0 2px 6px rgba(255, 184, 0, 0.4)',
            }}
          >
            👑 主
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: '50%',
              background: PRIMARY_BG,
              color: PRIMARY,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 18,
              fontWeight: 700,
              marginRight: 12,
            }}
          >
            {(it.managed_user_nickname || it.relation_label || '?').charAt(0)}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#1a1a1a' }}>
              {it.managed_user_nickname || it.relation_label || '待邀请家人'}
            </div>
            <div style={{ fontSize: 12, color: '#8C8C8C', marginTop: 4 }}>
              {isActive ? '共管' : '待守护'}
              {subStatus}
              {it.invite_lifecycle === 'inviting' && it.invite_remaining_hours !== undefined && (
                <span style={{ color: GOLD, marginLeft: 4 }}>
                  · 还剩 {it.invite_remaining_hours} 小时
                </span>
              )}
              {isActive && it.created_at && (
                <span style={{ marginLeft: 4 }}>· {fmtDate(it.created_at)} 建立</span>
              )}
              {it.proxy_pay_enabled && (
                <Tag color='warning' style={{ marginLeft: 6, background: WARN_BG, color: GOLD }}>
                  代付中
                </Tag>
              )}
            </div>
          </div>
        </div>

        {/* 按钮区：根据 lifecycle 动态显示 */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {isActive ? (
            <>
              <Button
                size='mini'
                fill='outline'
                style={{ flex: 1, borderRadius: 22, borderColor: PRIMARY, color: PRIMARY }}
                onClick={() =>
                  router.push(`/health-profile?member_user_id=${it.managed_user_id}`)
                }
              >
                查看档案
              </Button>
              {it.is_primary_guardian && (
                <Button
                  size='mini'
                  fill='outline'
                  style={{ flex: 1, borderRadius: 22, borderColor: GOLD, color: GOLD }}
                  onClick={() => openPayDetail(it)}
                >
                  代付明细
                </Button>
              )}
              <Button
                size='mini'
                fill='outline'
                style={{ flex: 1, borderRadius: 22, borderColor: DANGER, color: DANGER }}
                onClick={() => handleUnGuard(it)}
              >
                解除守护
              </Button>
            </>
          ) : (
            <>
              {it.invite_lifecycle === 'inviting' && (
                <>
                  <Button
                    size='mini'
                    fill='solid'
                    style={{ flex: 1, borderRadius: 22, background: PRIMARY }}
                    onClick={() => handleViewQr(it)}
                  >
                    查看二维码
                  </Button>
                  <Button
                    size='mini'
                    fill='outline'
                    style={{ flex: 1, borderRadius: 22, borderColor: DANGER, color: DANGER }}
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
                    style={{ flex: 1, borderRadius: 22, background: PRIMARY }}
                    onClick={() => handleReinvite(it)}
                  >
                    再次邀请
                  </Button>
                  {/* 4 不可删校验通过才显示 */}
                  {it.can_remove && (
                    <Button
                      size='mini'
                      fill='outline'
                      style={{ flex: 1, borderRadius: 22, borderColor: DANGER, color: DANGER }}
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
                    style={{ flex: 1, borderRadius: 22, background: PRIMARY }}
                    onClick={handleInvite}
                  >
                    发起邀请
                  </Button>
                  {it.can_remove && (
                    <Button
                      size='mini'
                      fill='outline'
                      style={{ flex: 1, borderRadius: 22, borderColor: DANGER, color: DANGER }}
                      onClick={() => handleRemove(it)}
                    >
                      移除
                    </Button>
                  )}
                </>
              )}
              {/* 邀请记录入口 */}
              <Button
                size='mini'
                fill='none'
                style={{ borderRadius: 22, color: PRIMARY, fontSize: 12 }}
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

      {/* 顶部配额提示 */}
      {resp && (
        <div
          style={{
            margin: '8px 16px 0',
            padding: '8px 12px',
            background: PRIMARY_BG,
            borderRadius: 8,
            fontSize: 12,
            color: PRIMARY_DARK,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>
            您还可邀请 <b style={{ color: PRIMARY_DARK }}>{resp.can_invite_count}</b> 位 / 共{' '}
            {resp.max_guardians} 位
          </span>
          <Button
            size='mini'
            fill='solid'
            style={{ background: PRIMARY, borderRadius: 16 }}
            onClick={handleInvite}
          >
            + 发起邀请
          </Button>
        </div>
      )}

      {/* 极简两态 Tab */}
      <Tabs
        activeKey={tab}
        onChange={(k) => setTab(k as 'active' | 'pending')}
        style={{ background: '#fff', marginTop: 8 }}
      >
        <Tabs.Tab title={`守护中 (${resp?.tab_active_count || 0})`} key='active' />
        <Tabs.Tab title={`待守护 (${resp?.tab_pending_count || 0})`} key='pending' />
      </Tabs>

      <div style={{ padding: '12px 16px' }}>
        {/* 本人行：仅守护中 Tab 显示 */}
        {tab === 'active' && (
          <div
            style={{
              background: '#fff',
              borderRadius: 20,
              padding: 16,
              marginBottom: 12,
              boxShadow: '0 4px 16px rgba(24, 144, 255, 0.08)',
              border: `1px solid ${PRIMARY_BG}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: '50%',
                  background: `linear-gradient(135deg, ${PRIMARY} 0%, ${PRIMARY_DARK} 100%)`,
                  color: '#fff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 18,
                  fontWeight: 700,
                  marginRight: 12,
                }}
              >
                我
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#1a1a1a' }}>
                  {me.nickname || '本人'}（本人）
                </div>
                <div style={{ fontSize: 12, color: '#8C8C8C', marginTop: 2 }}>
                  我的健康档案与额度
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button
                size='mini'
                color='primary'
                fill='outline'
                style={{ flex: 1, borderRadius: 22 }}
                onClick={() => router.push('/health-profile')}
              >
                编辑档案
              </Button>
              <Button
                size='mini'
                color='primary'
                fill='outline'
                style={{ flex: 1, borderRadius: 22 }}
                onClick={() => openHistory({ manager_user_id: me.id } as any)}
              >
                邀请记录
              </Button>
              <Button
                size='mini'
                color='primary'
                fill='solid'
                style={{ flex: 1, borderRadius: 22 }}
                onClick={() => router.push('/member-center#quota')}
              >
                我的 AI 外呼额度
              </Button>
            </div>
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#8C8C8C' }}>加载中…</div>
        ) : filtered.length === 0 ? (
          <Empty
            description={tab === 'active' ? '暂无守护中的家人' : '暂无待守护的家人'}
          />
        ) : (
          filtered.map(renderCard)
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
                  background: WARN_BG,
                  borderRadius: 8,
                }}
              >
                <span>AI 呼叫代付开关</span>
                <Switch
                  checked={!!payDetail.enabled}
                  onChange={(c) => payDetailModal && togglePay(payDetailModal, c)}
                />
              </div>
              <div style={{ fontSize: 13, color: '#555', marginBottom: 8 }}>
                今日代付 <b>{payDetail.today_count}</b> 次 · 本月代付{' '}
                <b>{payDetail.month_count}</b> 次
              </div>
              <div
                style={{
                  maxHeight: 240,
                  overflowY: 'auto',
                  fontSize: 12,
                  color: '#666',
                }}
              >
                {(payDetail.items || []).length === 0 ? (
                  <div style={{ textAlign: 'center', padding: 16, color: '#999' }}>
                    本月暂无代付记录
                  </div>
                ) : (
                  payDetail.items.map((r: any) => (
                    <div
                      key={r.id}
                      style={{ padding: 8, borderBottom: '1px solid #f0f0f0' }}
                    >
                      <div>
                        {r.call_type_label} · {fmtDate(r.used_at)}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : (
            <div style={{ padding: 16, textAlign: 'center' }}>加载中…</div>
          )
        }
        closeOnAction
        actions={[{ key: 'ok', text: '关闭' }]}
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
          <div
            style={{
              padding: '8px 0',
              maxHeight: 400,
              overflowY: 'auto',
            }}
          >
            {history.length === 0 ? (
              <Empty description='暂无邀请记录' />
            ) : (
              history.map((r: any) => (
                <div
                  key={r.id}
                  style={{
                    padding: 12,
                    borderBottom: '1px solid #f0f0f0',
                    fontSize: 13,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>{fmtDate(r.created_at)} 发起邀请</span>
                    <Tag color={r.status_color === 'success' ? 'success' : 'default'}>
                      {r.status_label}
                    </Tag>
                  </div>
                  {r.relation_type && (
                    <div style={{ color: '#999', marginTop: 4 }}>
                      关系：{r.relation_type}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        }
        closeOnAction
        actions={[{ key: 'ok', text: '关闭' }]}
        onClose={() => {
          setHistoryModal(null);
          setHistory([]);
        }}
      />
    </div>
  );
}
