'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Dialog } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { BH_TOKENS } from '@/lib/health-tokens';

interface Guardian {
  management_id: number;
  user_id: number;
  nickname: string | null;
  avatar?: string | null;
  guardian_since: string | null;
  permission_scope: string;
  last_viewed_at?: string | null;
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

  const fetchGuardians = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/reverse-guardian/my-guardians');
      const data = res.data || res;
      setGuardians(Array.isArray(data.items) ? data.items : []);
    } catch {
      setGuardians([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGuardians();
  }, [fetchGuardians]);

  const handleRemove = async (g: Guardian) => {
    const confirmed = await Dialog.confirm({
      title: '解除守护',
      content: '解除后，对方将无法查看您的健康数据。确定要解除吗？',
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

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    } catch {
      return dateStr;
    }
  };

  const formatPermissions = (scope: string) => {
    return scope || '查看健康数据';
  };

  return (
    <div style={{ background: BH_TOKENS.bgPage, minHeight: '100vh', paddingBottom: 100 }}>
      <GreenNavBar>守护我的人</GreenNavBar>

      <div style={{ padding: '12px 16px' }}>
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
              onClick={() => router.push('/health-profile/my-guardians/invite')}
              style={{
                padding: '12px 32px', borderRadius: 24,
                background: T.brand500, color: '#fff',
                border: 'none', fontSize: 15, fontWeight: 600, cursor: 'pointer',
              }}
            >邀请别人守护我</button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {guardians.map((g) => (
              <div
                key={g.management_id}
                data-testid={`guardian-card-${g.management_id}`}
                style={{
                  background: '#fff', borderRadius: 14, padding: 16,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
                }}
              >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: '50%',
                    background: '#E8F5E9', display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                    fontSize: 22, fontWeight: 700, color: '#2E7D32', flexShrink: 0,
                  }}>
                    {g.avatar ? (
                      <img src={g.avatar} alt="" style={{ width: 48, height: 48, borderRadius: '50%', objectFit: 'cover' }} />
                    ) : (
                      (g.nickname || '守')[0]
                    )}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 16, fontWeight: 600, color: T.textPrimary }}>
                      {g.nickname || '未知用户'}
                    </div>
                    <div style={{ fontSize: 12, color: T.textSecondary, marginTop: 2 }}>
                      守护开始: {formatDate(g.guardian_since)}
                    </div>
                  </div>
                  <button
                    onClick={() => handleRemove(g)}
                    style={{
                      padding: '6px 14px', borderRadius: 16,
                      background: '#FEE2E2', color: '#DC2626',
                      border: 'none', fontSize: 12, fontWeight: 500, cursor: 'pointer',
                    }}
                  >解除</button>
                </div>
                <div style={{
                  marginTop: 10, paddingTop: 10, borderTop: '1px solid #F3F4F6',
                  display: 'flex', justifyContent: 'space-between', fontSize: 12, color: T.textSecondary,
                }}>
                  <span>权限: {formatPermissions(g.permission_scope)}</span>
                  <span>最近查看: {formatDate(g.last_viewed_at)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {!loading && guardians.length > 0 && (
        <div style={{ padding: '12px 16px', position: 'fixed', bottom: 0, left: 0, right: 0, background: 'linear-gradient(transparent, rgba(255,255,255,0.95) 20%)' }}>
          <button
            onClick={() => router.push('/health-profile/my-guardians/invite')}
            style={{
              width: '100%', padding: '14px 0', borderRadius: 24,
              background: T.brand500, color: '#fff',
              border: 'none', fontSize: 16, fontWeight: 600, cursor: 'pointer',
              boxShadow: '0 4px 12px rgba(74,158,224,0.3)',
            }}
          >邀请别人守护我</button>
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
