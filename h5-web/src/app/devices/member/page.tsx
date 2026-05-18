'use client';

/**
 * [PRD-HEALTH-ARCHIVE-OPTIM-V2 2026-05-18] 当前成员设备列表页
 *
 * 路由：/devices/member?member_id=xxx
 *
 * 顶部：< 返回    {成员称呼}的设备
 *                共 X 台 · Y 台在线
 * 列表：设备图标 / 名称型号 / 在线状态 Pill / 最近上报 / >
 *
 * 权限：本人可管理；其他成员只读
 */

export const dynamic = 'force-dynamic';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface Device {
  id: number;
  device_type: string;
  device_name: string;
  device_sn?: string | null;
  online: boolean;
  last_sync_at?: string | null;
}

interface DevicesResponse {
  member_id: number;
  member_nickname: string;
  relationship_type: string;
  is_self: boolean;
  readonly: boolean;
  total: number;
  online_count: number;
  items: Device[];
}

export default function MemberDevicesPage() {
  return (
    <Suspense fallback={<div style={{ padding: 24, color: '#999', textAlign: 'center' }}>加载中...</div>}>
      <MemberDevicesContent />
    </Suspense>
  );
}

function MemberDevicesContent() {
  const router = useRouter();
  const search = useSearchParams();
  const memberId = search.get('member_id');
  const [data, setData] = useState<DevicesResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!memberId) {
      Toast.show('参数缺失');
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const r: any = await api.get(`/api/family-archive-v2/member/${memberId}/devices`);
      const d = r.data || r;
      setData(d);
    } catch (e: any) {
      Toast.show(e?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [memberId]);

  useEffect(() => {
    load();
  }, [load]);

  const title = data ? `${data.is_self ? '本人' : data.relationship_type || data.member_nickname || 'TA'}的设备` : '设备';

  return (
    <div style={{ minHeight: '100vh', background: '#F5F7FB', paddingBottom: 60 }}>
      <GreenNavBar>{title}</GreenNavBar>

      {data && (
        <div style={{ padding: '12px 16px', color: '#666', fontSize: 13 }}>
          共 {data.total} 台 · {data.online_count} 台在线
        </div>
      )}

      <div style={{ padding: '0 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {loading && <div style={{ color: '#999', textAlign: 'center', padding: 24 }}>加载中...</div>}
        {!loading && data && data.items.length === 0 && (
          <div style={{ color: '#999', textAlign: 'center', padding: 36 }}>暂无设备</div>
        )}
        {data?.items.map((d) => (
          <div
            key={d.id}
            data-testid={`device-${d.id}`}
            style={{
              background: '#fff',
              borderRadius: 10,
              padding: 14,
              display: 'flex',
              alignItems: 'center',
              boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
              cursor: data.readonly ? 'default' : 'pointer',
            }}
          >
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 8,
                background: '#E0EFFF',
                color: '#1F6FE6',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 20,
                marginRight: 12,
                flexShrink: 0,
              }}
            >
              📱
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 15, fontWeight: 600 }}>{d.device_name || d.device_type}</span>
                <OnlinePill online={d.online} />
              </div>
              <div style={{ marginTop: 4, fontSize: 12, color: '#888' }}>
                {d.device_type}
                {d.last_sync_at ? ` · 最近上报 ${formatTime(d.last_sync_at)}` : ' · 暂未上报'}
              </div>
            </div>
            <span style={{ color: '#BBB', fontSize: 18 }}>›</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function OnlinePill({ online }: { online: boolean }) {
  return (
    <span
      style={{
        background: online ? '#1FA168' : '#6B7280',
        color: '#fff',
        padding: '1px 8px',
        borderRadius: 10,
        fontSize: 11,
        fontWeight: 600,
      }}
    >
      ● {online ? '在线' : '离线'}
    </span>
  );
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mi = String(d.getMinutes()).padStart(2, '0');
    return `${mm}/${dd} ${hh}:${mi}`;
  } catch {
    return iso;
  }
}
