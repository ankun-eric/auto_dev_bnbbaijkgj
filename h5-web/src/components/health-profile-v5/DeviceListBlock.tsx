'use client';

/**
 * [PRD-469 M9] 设备绑定列表 —— 10 项设备清单
 */

import { useEffect, useState } from 'react';
import { Toast } from 'antd-mobile';
import api from '@/lib/api';

interface DeviceItem {
  key: string;
  name: string;
  status: 'connected' | 'coming_soon';
  icon: string;
  bound?: boolean;
  bound_at?: string | null;
  last_sync_at?: string | null;
}

interface Props {
  token: any;
}

export default function DeviceListBlock({ token: T }: Props) {
  const [items, setItems] = useState<DeviceItem[]>([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res: any = await api.get('/api/prd469/device/list');
        const data = res.data || res;
        setItems(Array.isArray(data.items) ? data.items : []);
      } catch {
        setItems([]);
      }
    })();
  }, []);

  const handleClick = async (it: DeviceItem) => {
    if (it.status === 'connected') {
      Toast.show({ content: it.bound ? '已绑定，正在打开设备详情…' : '请前往「华为运动健康」授权绑定', icon: 'success' });
    } else {
      try {
        await api.post('/api/prd469/device/subscribe', { device_key: it.key });
        Toast.show({ content: '该设备即将上线，敬请期待！上线后我们将通知您', icon: 'success' });
      } catch {
        Toast.show({ content: '该设备即将上线，敬请期待', icon: 'success' });
      }
    }
  };

  const shown = expanded ? items : items.slice(0, 4);

  return (
    <div data-testid="prd469-device-block" style={{ padding: '12px 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '8px 0 12px' }}>
        <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: 0 }}>我的设备</h3>
        <span
          onClick={() => setExpanded((v) => !v)}
          style={{ fontSize: 13, color: T.brand600, cursor: 'pointer' }}
        >{expanded ? '收起 ▲' : '查看全部 ▼'}</span>
      </div>
      <div
        style={{
          background: '#fff', borderRadius: 12, padding: 12,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          borderLeft: '3px solid #22c55e',
        }}
      >
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
          {shown.map((it) => (
            <div
              key={it.key}
              onClick={() => handleClick(it)}
              data-testid={`prd469-device-${it.key}`}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 12px', borderRadius: 10,
                background: it.status === 'connected' ? T.brand100 : '#f9fafb',
                cursor: 'pointer',
              }}
            >
              <div style={{ fontSize: 20 }}>{it.icon}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#1f2937', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{it.name}</div>
                <div style={{ fontSize: 11, color: it.status === 'connected' ? T.brand700 : '#9ca3af', marginTop: 2 }}>
                  {it.status === 'connected' ? (it.bound ? '✓ 已绑定' : '已接通') : '敬请期待'}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
