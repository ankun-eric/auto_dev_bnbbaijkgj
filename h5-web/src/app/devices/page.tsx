'use client';
/**
 * [PRD-HEALTH-OPT-V1 2026-05-14 R2] 设备管理页 — 通用样式版本（占位实现）。
 *
 * 用户后续提供参考图后，再做局部替换；功能与接口契约保持不变。
 */
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { BH_TOKENS } from '@/lib/health-tokens';
import { ToastUnified } from '@/lib/toast-unified';
import { showUnifiedConfirm } from '@/lib/dialog-unified';
import { formatDateTime } from '@/lib/datetime';

interface DeviceItem {
  id: number;
  device_type?: string;
  device_name?: string;
  device_sn?: string | null;
  status?: string;
  bound_at?: string | null;
  last_sync_at?: string | null;
  battery?: number | null;
  is_online?: boolean;
}

export default function DevicesPage() {
  const router = useRouter();
  const [list, setList] = useState<DeviceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<DeviceItem | null>(null);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/devices/list').catch(() => null);
      const data = (res?.data || res) as any;
      const items: DeviceItem[] = Array.isArray(data?.items)
        ? data.items
        : Array.isArray(data)
        ? data
        : [];
      setList(items);
    } catch {
      setList([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchList(); }, [fetchList]);

  const handleUnbind = async (item: DeviceItem) => {
    const ok = await showUnifiedConfirm({
      title: '解绑设备',
      content: `确认解绑 ${item.device_name || '该设备'} 吗？解绑后将停止同步数据。`,
      danger: true,
      confirmText: '解绑',
    });
    if (!ok) return;
    try {
      await api.delete(`/api/devices/${item.id}`);
      ToastUnified.success('已解绑');
      setDetail(null);
      fetchList();
    } catch {
      ToastUnified.fail('解绑失败，请稍后重试');
    }
  };

  return (
    <div style={{ background: BH_TOKENS.bgPage, minHeight: '100vh' }}>
      <GreenNavBar
        right={
          <span
            onClick={() => ToastUnified.show({ content: '即将开放，请前往「健康档案」绑定页' })}
            data-testid="bh-add-device"
            style={{ color: BH_TOKENS.brand600, fontSize: 14, cursor: 'pointer' }}
          >+ 添加</span>
        }
      >
        我的设备
      </GreenNavBar>

      <div style={{ padding: 16 }}>
        {loading ? (
          <div style={{ textAlign: 'center', color: BH_TOKENS.textSecondary, padding: 40 }}>加载中…</div>
        ) : list.length === 0 ? (
          <div
            data-testid="bh-devices-empty"
            style={{
              background: BH_TOKENS.cardSurface,
              borderRadius: BH_TOKENS.cardRadius,
              padding: '40px 24px',
              boxShadow: BH_TOKENS.cardShadow,
              textAlign: 'center',
              color: BH_TOKENS.textSecondary,
            }}
          >
            <div style={{ fontSize: 56, marginBottom: 12 }}>⌚</div>
            <div style={{ fontSize: 15, marginBottom: 16 }}>暂无已绑定设备</div>
            <button
              onClick={() => router.push('/health-profile')}
              style={{
                padding: '10px 24px',
                borderRadius: 22,
                background: BH_TOKENS.accentBlue,
                color: '#fff',
                fontSize: 14,
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
              }}
            >立即添加</button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {list.map((d) => (
              <div
                key={d.id}
                data-testid={`bh-device-${d.id}`}
                onClick={() => setDetail(d)}
                style={{
                  background: BH_TOKENS.cardSurface,
                  borderRadius: BH_TOKENS.cardRadius,
                  padding: 16,
                  boxShadow: BH_TOKENS.cardShadow,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  cursor: 'pointer',
                  borderLeft: `4px solid ${BH_TOKENS.accentBlue}`,
                }}
              >
                <div style={{ fontSize: 28 }}>⌚</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 16, fontWeight: 600, color: BH_TOKENS.textPrimary }}>{d.device_name || '未命名设备'}</div>
                  <div style={{ fontSize: 12, color: BH_TOKENS.textSecondary, marginTop: 2 }}>
                    {d.device_type || '通用'} · {d.is_online === false ? '离线' : '在线'}
                    {d.last_sync_at ? ` · 同步 ${formatDateTime(d.last_sync_at)}` : ''}
                  </div>
                </div>
                <div style={{ fontSize: 18, color: BH_TOKENS.brand500 }}>›</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {detail && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
            zIndex: 100, display: 'flex', alignItems: 'flex-end',
          }}
          onClick={() => setDetail(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#fff', width: '100%',
              borderTopLeftRadius: BH_TOKENS.cardRadius,
              borderTopRightRadius: BH_TOKENS.cardRadius,
              padding: 20, maxHeight: '70vh', overflowY: 'auto',
            }}
          >
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>{detail.device_name}</div>
            <div style={{ fontSize: 14, color: BH_TOKENS.textSecondary, marginBottom: 8 }}>
              类型：{detail.device_type || '通用'}
            </div>
            <div style={{ fontSize: 14, color: BH_TOKENS.textSecondary, marginBottom: 8 }}>
              SN：{detail.device_sn || '—'}
            </div>
            <div style={{ fontSize: 14, color: BH_TOKENS.textSecondary, marginBottom: 8 }}>
              状态：{detail.status || 'active'}
            </div>
            <div style={{ fontSize: 14, color: BH_TOKENS.textSecondary, marginBottom: 20 }}>
              绑定时间：{detail.bound_at ? formatDateTime(detail.bound_at) : '—'}
            </div>
            <button
              onClick={() => handleUnbind(detail)}
              data-testid="bh-device-unbind"
              style={{
                width: '100%', height: 44, borderRadius: 22,
                background: '#fff', border: `1px solid ${BH_TOKENS.statusDanger}`,
                color: BH_TOKENS.statusDanger, fontSize: 15, fontWeight: 600,
                cursor: 'pointer',
              }}
            >解绑</button>
          </div>
        </div>
      )}
    </div>
  );
}
