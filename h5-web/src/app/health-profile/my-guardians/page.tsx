'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Dialog } from 'antd-mobile';
import { QRCodeCanvas } from 'qrcode.react';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { BH_TOKENS } from '@/lib/health-tokens';
import { UNBIND_GUARDIAN_CONFIRM } from '@/lib/family-relation';

// [PRD-GUARDIAN-DUALCARD-V1 2026-05-28] 守护我的人 详情：合并 active + pending 两类
interface Guardian {
  item_type?: 'active' | 'pending';
  management_id?: number | null;
  invitation_id?: number | null;
  invite_code?: string | null;
  user_id?: number | null;
  nickname: string | null;
  avatar?: string | null;
  guardian_since: string | null;
  permission_scope: string;
  last_viewed_at?: string | null;
  invite_expires_at?: string | null;
  invite_status?: string | null;
  guardian_name?: string | null;
}

interface CountInfo {
  active_count: number;
  pending_count: number;
  total_count: number;
  max_guardians_for_me: number;
  is_unlimited?: boolean;
}

const T = {
  brand500: BH_TOKENS.brand500,
  brand600: BH_TOKENS.brand600,
  textPrimary: BH_TOKENS.textPrimary,
  textSecondary: BH_TOKENS.textSecondary,
};

function MyGuardiansPageInner() {
  const router = useRouter();
  const [guardians, setGuardians] = useState<Guardian[]>([]);
  const [loading, setLoading] = useState(true);
  const [countInfo, setCountInfo] = useState<CountInfo | null>(null);

  // [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 查看邀请码抽屉
  const [qrDrawer, setQrDrawer] = useState<Guardian | null>(null);

  const fetchGuardians = useCallback(async () => {
    setLoading(true);
    try {
      const [listRes, cntRes]: any[] = await Promise.all([
        api.get('/api/reverse-guardian/my-guardians'),
        api.get('/api/reverse-guardian/guardian-count'),
      ]);
      const data = listRes.data || listRes;
      setGuardians(Array.isArray(data.items) ? data.items : []);
      const cnt = cntRes.data || cntRes;
      setCountInfo({
        active_count: cnt.active_count || 0,
        pending_count: cnt.pending_count || 0,
        total_count: cnt.total_count || 0,
        max_guardians_for_me: cnt.max_guardians_for_me || 3,
        is_unlimited: !!cnt.is_unlimited,
      });
    } catch {
      setGuardians([]);
      setCountInfo(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGuardians();
  }, [fetchGuardians]);

  const handleRemove = async (g: Guardian) => {
    if (!g.management_id) return;
    const confirmed = await Dialog.confirm({
      title: UNBIND_GUARDIAN_CONFIRM.title,
      content: UNBIND_GUARDIAN_CONFIRM.content,
      cancelText: UNBIND_GUARDIAN_CONFIRM.cancelText,
      confirmText: UNBIND_GUARDIAN_CONFIRM.confirmText,
    });
    if (!confirmed) return;
    try {
      await api.post('/api/reverse-guardian/remove', { management_id: g.management_id });
      showToast('已解除守护');
      fetchGuardians();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '操作失败';
      showToast(String(msg), 'fail');
    }
  };

  // [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 取消邀请 二次确认文案统一
  const handleCancelInvite = async (g: Guardian) => {
    if (!g.invitation_id && !g.invite_code) return;
    const targetName = (g.guardian_name || g.nickname || '对方');
    const confirmed = await Dialog.confirm({
      title: '取消邀请',
      content: `确定取消对${targetName}的邀请吗？取消后对方扫码将失效。`,
      cancelText: '我再想想',
      confirmText: '确定取消',
    });
    if (!confirmed) return;
    try {
      await api.post('/api/reverse-guardian/invite/cancel', {
        invitation_id: g.invitation_id ?? undefined,
        invite_code: g.invite_code ?? undefined,
      });
      showToast('已取消邀请');
      fetchGuardians();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : (detail?.message || e?.message || '取消失败');
      showToast(String(msg), 'fail');
    }
  };

  const formatDateTime = (dateStr?: string | null) => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      const hh = String(d.getHours()).padStart(2, '0');
      const mm = String(d.getMinutes()).padStart(2, '0');
      return `${y}-${m}-${day} ${hh}:${mm}`;
    } catch {
      return dateStr;
    }
  };

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    } catch {
      return dateStr;
    }
  };

  const formatPermissions = (scope: string) => scope || '查看健康数据';

  // [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 上限判断
  const x = countInfo?.total_count ?? 0;
  const y = countInfo?.max_guardians_for_me ?? 3;
  const isUnlimited = !!countInfo?.is_unlimited;
  const limitReached = !isUnlimited && x >= y;

  const handleInviteClick = async () => {
    if (limitReached) {
      const confirmed = await Dialog.confirm({
        title: '您的守护者已达上限',
        content: `当前已有 ${x} 位守护者（含邀请中），上限 ${y} 位。请先升级会员或解绑现有守护者。`,
        cancelText: '取消',
        confirmText: '升级会员',
      });
      if (confirmed) router.push('/membership');
      return;
    }
    router.push('/health-profile/my-guardians/invite');
  };

  // [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 查看邀请码：本页抽屉
  const handleViewQrCode = (g: Guardian) => {
    if (!g.invite_code) {
      showToast('邀请码缺失', 'fail');
      return;
    }
    setQrDrawer(g);
  };

  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
  const drawerQrUrl = qrDrawer
    ? `${typeof window !== 'undefined' ? window.location.origin : ''}${basePath}/family-auth?code=${qrDrawer.invite_code}&type=reverse`
    : '';
  const drawerLabel = qrDrawer
    ? (() => {
        const nm = qrDrawer.guardian_name || qrDrawer.nickname || '';
        const rel = qrDrawer.permission_scope && qrDrawer.permission_scope !== '待确认' ? qrDrawer.permission_scope : '';
        if (nm && rel) return `${nm}（${rel}）`;
        return nm || '—';
      })()
    : '';

  return (
    <div style={{ background: BH_TOKENS.bgPage, minHeight: '100vh', paddingBottom: 100 }}>
      <GreenNavBar>守护我的人</GreenNavBar>

      <div style={{ padding: '12px 16px' }}>
        {/* [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 名额条 */}
        {!loading && countInfo && (
          <div
            data-testid="guardian-quota-bar"
            style={{
              background: '#fff', borderRadius: 12, padding: '10px 14px', marginBottom: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
            }}
          >
            <span style={{ fontSize: 13, color: T.textSecondary }}>已使用名额</span>
            <span style={{
              fontSize: 15, fontWeight: 700,
              color: limitReached ? '#DC2626' : T.brand600,
            }}>
              {isUnlimited ? `${x} / 不限` : `${x} / ${y}`}
            </span>
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 40 }}>加载中…</div>
        ) : guardians.length === 0 ? (
          <div style={{
            background: '#fff', borderRadius: 16, padding: '40px 20px',
            textAlign: 'center', boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
          }}>
            <div style={{ fontSize: 56, marginBottom: 12 }}>💚</div>
            <div style={{ fontSize: 17, fontWeight: 700, color: T.textPrimary, marginBottom: 8 }}>
              还没有人守护你
            </div>
            <div style={{ fontSize: 14, color: T.textSecondary, marginBottom: 20 }}>
              邀请家人或朋友守护你，让他们随时关注你的健康状况
            </div>
            <button
              onClick={handleInviteClick}
              disabled={limitReached}
              style={{
                padding: '12px 32px', borderRadius: 24,
                background: limitReached ? '#E5E7EB' : T.brand500,
                color: limitReached ? '#9CA3AF' : '#fff',
                border: 'none', fontSize: 15, fontWeight: 600,
                cursor: limitReached ? 'not-allowed' : 'pointer',
              }}
            >邀请别人守护我</button>
            {limitReached && (
              <div style={{ marginTop: 8, fontSize: 12, color: '#DC2626' }}>
                已达上限 {x}/{y}
              </div>
            )}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {guardians.map((g, idx) => {
              const isPending = g.item_type === 'pending';
              const cardKey = isPending
                ? `pending-${g.invitation_id ?? idx}`
                : `active-${g.management_id ?? idx}`;
              // [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 头像首字：用对方名字第一个字
              const displayName = isPending
                ? (g.guardian_name || g.nickname || '')
                : (g.nickname || '');
              const avatarChar = (displayName || '守').charAt(0);
              const relText = isPending && g.permission_scope && g.permission_scope !== '待确认'
                ? g.permission_scope
                : '';

              return (
                <div
                  key={cardKey}
                  data-testid={isPending ? `guardian-pending-${g.invitation_id}` : `guardian-card-${g.management_id}`}
                  style={{
                    background: '#fff', borderRadius: 14, padding: 16,
                    boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
                    border: isPending ? '1px dashed #F59E0B' : 'none',
                  }}
                >
                  {/* 头像 + 信息行 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{
                      width: 48, height: 48, borderRadius: '50%',
                      background: isPending ? '#FFF7E6' : '#E8F5E9',
                      display: 'flex',
                      alignItems: 'center', justifyContent: 'center',
                      fontSize: 22, fontWeight: 700,
                      color: isPending ? '#D97706' : '#2E7D32', flexShrink: 0,
                      overflow: 'hidden',
                    }}>
                      {g.avatar && !isPending ? (
                        <img src={g.avatar} alt="" style={{ width: 48, height: 48, borderRadius: '50%', objectFit: 'cover' }} />
                      ) : (
                        avatarChar
                      )}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 16, fontWeight: 600, color: T.textPrimary,
                        display: 'flex', alignItems: 'center', gap: 6,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {isPending
                            ? (displayName ? (relText ? `${displayName}（${relText}）` : displayName) : '邀请中')
                            : (displayName || '未知用户')
                          }
                        </span>
                        {isPending && (
                          <span style={{
                            fontSize: 11, padding: '2px 6px', borderRadius: 6,
                            background: '#FEF3C7', color: '#D97706', fontWeight: 500,
                            flexShrink: 0,
                          }}>待确认</span>
                        )}
                      </div>
                      <div style={{ fontSize: 12, color: T.textSecondary, marginTop: 4 }}>
                        {isPending
                          ? `邀请于 ${formatDateTime(g.guardian_since)}`
                          : `守护开始：${formatDate(g.guardian_since)}`
                        }
                      </div>
                    </div>
                    {/* 已激活卡片：解除按钮仍在右上 */}
                    {!isPending && (
                      <button
                        onClick={() => handleRemove(g)}
                        style={{
                          padding: '6px 14px', borderRadius: 16,
                          background: '#FEE2E2', color: '#DC2626',
                          border: 'none', fontSize: 12, fontWeight: 500, cursor: 'pointer',
                        }}
                      >解除</button>
                    )}
                  </div>

                  {/* [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 邀请态卡片底部按钮独立一行 */}
                  {isPending && (
                    <div style={{
                      marginTop: 12, paddingTop: 12, borderTop: '1px solid #F3F4F6',
                      display: 'flex', justifyContent: 'space-between', gap: 10,
                    }}>
                      <button
                        data-testid={`cancel-invite-${g.invitation_id}`}
                        onClick={() => handleCancelInvite(g)}
                        style={{
                          flex: 1, padding: '10px 0', borderRadius: 18,
                          background: '#FFF7E6', color: '#D97706',
                          border: '1px solid #F59E0B', fontSize: 13, fontWeight: 500, cursor: 'pointer',
                        }}
                      >取消邀请</button>
                      <button
                        data-testid={`view-invite-code-${g.invitation_id}`}
                        onClick={() => handleViewQrCode(g)}
                        disabled={!g.invite_code}
                        style={{
                          flex: 1, padding: '10px 0', borderRadius: 18,
                          background: '#E0F2FE', color: '#0369A1',
                          border: '1px solid #38BDF8', fontSize: 13, fontWeight: 500,
                          cursor: g.invite_code ? 'pointer' : 'not-allowed',
                          opacity: g.invite_code ? 1 : 0.5,
                        }}
                      >查看邀请码</button>
                    </div>
                  )}

                  {!isPending && (
                    <div style={{
                      marginTop: 10, paddingTop: 10, borderTop: '1px solid #F3F4F6',
                      display: 'flex', justifyContent: 'space-between', fontSize: 12, color: T.textSecondary,
                    }}>
                      <span>权限: {formatPermissions(g.permission_scope)}</span>
                      <span>最近查看: {formatDate(g.last_viewed_at)}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 底部"邀请别人守护我"按钮 */}
      {!loading && guardians.length > 0 && (
        <div style={{ padding: '12px 16px', position: 'fixed', bottom: 0, left: 0, right: 0, background: 'linear-gradient(transparent, rgba(255,255,255,0.95) 20%)' }}>
          <button
            data-testid="invite-new-guardian-btn"
            onClick={handleInviteClick}
            disabled={limitReached}
            style={{
              width: '100%', padding: '14px 0', borderRadius: 24,
              background: limitReached ? '#E5E7EB' : T.brand500,
              color: limitReached ? '#9CA3AF' : '#fff',
              border: 'none', fontSize: 16, fontWeight: 600,
              cursor: limitReached ? 'not-allowed' : 'pointer',
              boxShadow: limitReached ? 'none' : '0 4px 12px rgba(74,158,224,0.3)',
            }}
          >邀请别人守护我</button>
          {limitReached && (
            <div style={{ marginTop: 6, fontSize: 12, color: '#DC2626', textAlign: 'center' }}>
              已达上限 {x}/{y}
            </div>
          )}
        </div>
      )}

      {/* [BUGFIX-GUARDIAN-INVITE-MULTI-PENDING 2026-06-03] 查看邀请码抽屉 */}
      {qrDrawer && (
        <div
          data-testid="invite-qrcode-drawer"
          style={{
            position: 'fixed', inset: 0, zIndex: 1100,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
          }}
          onClick={() => setQrDrawer(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#fff', borderRadius: '20px 20px 0 0',
              width: '100%', maxWidth: 500, padding: '20px 20px 28px',
            }}
          >
            <div style={{ fontSize: 17, fontWeight: 700, color: '#333', marginBottom: 16, textAlign: 'center' }}>
              邀请二维码
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{
                display: 'inline-flex', padding: 10, borderRadius: 14,
                border: '2px solid #E8F5E9', background: '#fff',
              }}>
                <QRCodeCanvas
                  value={drawerQrUrl}
                  size={180}
                  level="M"
                  includeMargin={false}
                  bgColor="#ffffff"
                  fgColor="#333333"
                />
              </div>
              <div style={{ marginTop: 14, fontSize: 14, color: '#333', fontWeight: 500 }}>
                邀请对象：{drawerLabel}
              </div>
              <div style={{ marginTop: 6, fontSize: 12, color: '#9CA3AF' }}>
                24 小时内有效
              </div>
            </div>
            <button
              data-testid="invite-qrcode-drawer-close"
              onClick={() => setQrDrawer(null)}
              style={{
                marginTop: 20, width: '100%', padding: '12px 0', borderRadius: 22,
                background: '#fff', color: T.brand500,
                border: `1.5px solid ${T.brand500}`,
                fontSize: 15, fontWeight: 600, cursor: 'pointer',
              }}
            >关闭</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function MyGuardiansPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>加载中…</div>}>
      <MyGuardiansPageInner />
    </Suspense>
  );
}
