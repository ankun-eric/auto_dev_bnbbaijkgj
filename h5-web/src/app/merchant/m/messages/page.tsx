'use client';

// [2026-04-24] 移动端 - 消息中心（只读列表）

import React, { useEffect, useState } from 'react';
import { NavBar, List, Empty, Toast, PullToRefresh } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

export default function MessagesMobilePage() {
  const router = useRouter();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/merchant/v1/messages', { params: { page: 1, page_size: 50 } });
      setItems(res.items || res || []);
    } catch (e: any) {
      // 接口可能尚未提供，静默降级
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa' }}>
      <NavBar onBack={() => router.back()}>消息中心</NavBar>
      <PullToRefresh onRefresh={load}>
        {items.length === 0 ? (
          <div style={{ padding: 48 }}>
            <Empty description={loading ? '加载中...' : '暂无消息'} />
          </div>
        ) : (
          <List>
            {items.map((m: any) => (
              <List.Item key={m.id} description={m.created_at ? new Date(m.created_at).toLocaleString('zh-CN') : ''}>
                <div style={{ fontWeight: m.is_read ? 400 : 600 }}>{m.title || m.content}</div>
                {m.title && m.content && <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>{m.content}</div>}
              </List.Item>
            ))}
          </List>
        )}
      </PullToRefresh>
    </div>
  );
}
