'use client';

/**
 * [守护人体系 PRD v1.1 2026-05-25]
 * 我的守护人列表 + 主守护人转移 + 邀请记录 + 告警额度
 */
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Dialog, Tabs, Tag, Button, Empty, ActionSheet } from 'antd-mobile';
import type { Action } from 'antd-mobile/es/components/action-sheet';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { formatDate as fmtServerDate } from '@/lib/datetime';

interface GuardianItem {
  management_id: number;
  manager_user_id: number;
  manager_nickname?: string;
  manager_phone?: string;
  managed_user_id: number;
  is_primary_guardian: boolean;
  priority_order: number;
  is_paid_member: boolean;
  status: string;
  created_at: string;
}

interface InvitationRecord {
  invite_code: string;
  member_nickname?: string;
  relation_type?: string;
  status: string;
  status_label: string;
  expires_at: string;
  accepted_by_nickname?: string;
  accepted_at?: string;
  created_at: string;
  can_reinvite: boolean;
}

interface AlertQuota {
  is_paid_member: boolean;
  monthly_free_quota: number;
  used_this_month: number;
  remaining: number;
  can_receive_call: boolean;
}

interface TransferRequest {
  id: number;
  managed_user_id: number;
  from_user_nickname?: string;
  to_user_nickname?: string;
  status: string;
  created_at: string;
  expires_at: string;
  can_approve: boolean;
}

export default function GuardianSystemPage() {
  const router = useRouter();
  const [tab, setTab] = useState<'guardians' | 'iGuard' | 'invitations'>('guardians');
  const [loading, setLoading] = useState(true);
  const [guardians, setGuardians] = useState<GuardianItem[]>([]);
  const [iGuardList, setIGuardList] = useState<GuardianItem[]>([]);
  const [invitations, setInvitations] = useState<InvitationRecord[]>([]);
  const [quota, setQuota] = useState<AlertQuota | null>(null);
  const [maxCount, setMaxCount] = useState<number>(3);
  const [isPaid, setIsPaid] = useState<boolean>(false);
  const [pendingTransfers, setPendingTransfers] = useState<TransferRequest[]>([]);
  const [actionVisible, setActionVisible] = useState(false);
  const [activeItem, setActiveItem] = useState<GuardianItem | null>(null);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [g, ig, inv, q, t]: any[] = await Promise.all([
        api.get('/api/guardian/list').catch(() => ({ data: { items: [] } })),
        api.get('/api/guardian/i-guard').catch(() => ({ data: { items: [] } })),
        api.get('/api/guardian/invitations/records').catch(() => ({ data: { items: [] } })),
        api.get('/api/guardian/alert-quota').catch(() => ({ data: null })),
        api.get('/api/guardian/transfer/pending').catch(() => ({ data: { items: [] } })),
      ]);
      const gData = g.data || g;
      const igData = ig.data || ig;
      const invData = inv.data || inv;
      const qData = q.data || q;
      const tData = t.data || t;
      setGuardians(gData.items || []);
      setIGuardList(igData.items || []);
      setInvitations(invData.items || []);
      setQuota(qData || null);
      setMaxCount(gData.max_count || 3);
      setIsPaid(!!gData.is_paid_member);
      setPendingTransfers(tData.items || []);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const formatDate = (s: string) => (s ? fmtServerDate(s) : '');

  const handleInitiateTransfer = async (target: GuardianItem) => {
    const ok = await Dialog.confirm({
      title: '转移主守护人',
      content: `确认将主守护人身份转移给 ${target.manager_nickname || '该守护人'}？被守护人需要确认后转移才会生效。`,
    });
    if (!ok) return;
    try {
      await api.post('/api/guardian/transfer/initiate', {
        target_management_id: target.management_id,
      });
      showToast('已发起转移申请', 'success');
      fetchAll();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const handleApproveTransfer = async (t: TransferRequest) => {
    try {
      await api.post(`/api/guardian/transfer/${t.id}/approve`);
      showToast('已同意，主守护人已更新', 'success');
      fetchAll();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const handleCancelTransfer = async (t: TransferRequest) => {
    try {
      await api.post(`/api/guardian/transfer/${t.id}/cancel`);
      showToast('已取消', 'success');
      fetchAll();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '操作失败', 'fail');
    }
  };

  const actions: Action[] = activeItem
    ? [
        {
          text: activeItem.is_primary_guardian
            ? '主守护人无法转移给自己'
            : '将主守护人身份转给Ta',
          key: 'transfer',
          disabled: activeItem.is_primary_guardian,
          onClick: () => {
            setActionVisible(false);
            handleInitiateTransfer(activeItem);
          },
        },
      ]
    : [];

  const renderRoleBadges = (g: GuardianItem) => (
    <div className="flex items-center gap-1 flex-wrap">
      {g.is_primary_guardian ? (
        <Tag color="primary" style={{ fontSize: 10 }}>
          ⭐ 主守护人
        </Tag>
      ) : (
        <Tag color="default" style={{ fontSize: 10 }}>普通守护人</Tag>
      )}
      {g.is_paid_member ? (
        <Tag color="warning" style={{ fontSize: 10 }}>付费</Tag>
      ) : (
        <Tag color="default" style={{ fontSize: 10 }}>免费</Tag>
      )}
    </div>
  );

  return (
    <div
      className="min-h-screen"
      style={{ background: 'linear-gradient(160deg, #f0faf0 0%, #e8f4ff 100%)' }}
    >
      <GreenNavBar>守护人体系</GreenNavBar>

      {/* 额度信息卡片 */}
      {quota && (
        <div className="px-4 pt-3">
          <div
            className="rounded-xl px-4 py-3"
            style={{ background: '#ffffff', boxShadow: '0 2px 8px rgba(0,0,0,0.04)' }}
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs text-gray-500">本月异常告警电话额度</div>
                <div className="text-lg font-semibold mt-1">
                  {quota.is_paid_member ? '不限次（付费会员）' : `${quota.remaining}/${quota.monthly_free_quota} 次`}
                </div>
              </div>
              {!quota.is_paid_member && !quota.can_receive_call && (
                <Tag color="danger" style={{ fontSize: 10 }}>额度已用完</Tag>
              )}
            </div>
            {!quota.is_paid_member && quota.remaining <= 1 && (
              <div className="text-xs text-red-500 mt-2">
                提示：电话告警额度即将用完，升级付费会员可获得不限次电话告警
              </div>
            )}
          </div>
        </div>
      )}

      {/* 待处理转移请求 */}
      {pendingTransfers.length > 0 && (
        <div className="px-4 pt-3">
          {pendingTransfers.map(t => (
            <div
              key={t.id}
              className="rounded-xl px-4 py-3 mb-2"
              style={{ background: '#fffbe6', border: '1px solid #ffe58f' }}
            >
              <div className="text-sm font-medium">主守护人转移申请</div>
              <div className="text-xs text-gray-600 mt-1">
                {t.from_user_nickname || '原主守护人'} 申请将主守护人身份转移给{' '}
                {t.to_user_nickname || '新主守护人'}
              </div>
              <div className="flex gap-2 mt-2">
                {t.can_approve ? (
                  <>
                    <Button color="primary" size="mini" onClick={() => handleApproveTransfer(t)}>
                      同意
                    </Button>
                    <Button size="mini" onClick={() => handleCancelTransfer(t)}>
                      拒绝
                    </Button>
                  </>
                ) : (
                  <Button size="mini" onClick={() => handleCancelTransfer(t)}>
                    取消申请
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <Tabs activeKey={tab} onChange={(k) => setTab(k as any)}>
        <Tabs.Tab title={`我的守护人(${guardians.length}/${maxCount})`} key="guardians" />
        <Tabs.Tab title={`我守护的人(${iGuardList.length})`} key="iGuard" />
        <Tabs.Tab title="邀请记录" key="invitations" />
      </Tabs>

      <div className="px-4 pt-2 pb-12">
        {loading ? (
          <div className="text-center py-16 text-gray-400 text-sm">加载中...</div>
        ) : tab === 'guardians' ? (
          guardians.length === 0 ? (
            <Empty description="暂无守护人，去邀请家人守护您" />
          ) : (
            <div className="space-y-3">
              {guardians.map((g) => (
                <div
                  key={g.management_id}
                  className="rounded-2xl bg-white p-4"
                  style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.04)' }}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{g.manager_nickname || g.manager_phone || '守护人'}</span>
                      </div>
                      <div className="mt-1">{renderRoleBadges(g)}</div>
                      <div className="text-xs text-gray-400 mt-2">
                        绑定时间：{formatDate(g.created_at)}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              <div className="text-center text-xs text-gray-400 mt-4">
                {isPaid ? '付费会员可绑定 10 个守护人' : `免费会员最多 ${maxCount} 个守护人，升级解锁更多`}
              </div>
            </div>
          )
        ) : tab === 'iGuard' ? (
          iGuardList.length === 0 ? (
            <Empty description="您还未守护任何人" />
          ) : (
            <div className="space-y-3">
              {iGuardList.map((g) => (
                <div
                  key={g.management_id}
                  className="rounded-2xl bg-white p-4"
                  style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.04)' }}
                  onClick={() => {
                    setActiveItem(g);
                    setActionVisible(true);
                  }}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">
                        被守护人：{g.manager_nickname || `用户#${g.managed_user_id}`}
                      </div>
                      <div className="mt-1">
                        {g.is_primary_guardian ? (
                          <Tag color="primary" style={{ fontSize: 10 }}>⭐ 我是主守护人</Tag>
                        ) : (
                          <Tag color="default" style={{ fontSize: 10 }}>普通守护人</Tag>
                        )}
                      </div>
                      <div className="text-xs text-gray-400 mt-2">
                        绑定时间：{formatDate(g.created_at)}
                      </div>
                    </div>
                    <div className="text-xs text-blue-500">查看操作 ›</div>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : (
          // invitations tab
          invitations.length === 0 ? (
            <Empty description="暂无邀请记录" />
          ) : (
            <div className="space-y-3">
              {invitations.map((inv) => (
                <div
                  key={inv.invite_code}
                  className="rounded-2xl bg-white p-4"
                  style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.04)' }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="text-sm font-medium">
                        {inv.member_nickname || '家庭成员'}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        关系：{inv.relation_type || '—'}
                      </div>
                      <div className="text-xs text-gray-400 mt-1">
                        发起时间：{formatDate(inv.created_at)}
                      </div>
                      {inv.accepted_at && (
                        <div className="text-xs text-green-600 mt-1">
                          {inv.accepted_by_nickname || '某人'} 已接受于 {formatDate(inv.accepted_at)}
                        </div>
                      )}
                    </div>
                    <div className="text-right">
                      <Tag
                        color={
                          inv.status === 'accepted'
                            ? 'success'
                            : inv.status === 'pending'
                            ? 'primary'
                            : inv.status === 'expired'
                            ? 'warning'
                            : 'default'
                        }
                        style={{ fontSize: 10 }}
                      >
                        {inv.status_label}
                      </Tag>
                      {inv.can_reinvite && (
                        <div className="mt-2">
                          <Button
                            size="mini"
                            color="primary"
                            fill="outline"
                            onClick={() => router.push('/family-invite')}
                          >
                            重新发送
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        )}
      </div>

      <ActionSheet
        visible={actionVisible}
        actions={actions}
        onClose={() => setActionVisible(false)}
        cancelText="关闭"
      />
    </div>
  );
}
