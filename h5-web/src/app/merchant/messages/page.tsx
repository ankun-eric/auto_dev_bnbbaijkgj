'use client';

import React, { useEffect, useState } from 'react';
import { List, Typography, Tag, Empty, Spin, message } from 'antd';
import api from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;

export default function MessagesPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.get('/api/merchant/notifications', { params: { page: 1, page_size: 50 } })
      .then((d: any) => setRows(d.items || d || []))
      .catch((e: any) => message.error(e?.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <Title level={4}>消息中心</Title>
      {loading ? <Spin /> : rows.length === 0 ? <Empty /> : (
        <List
          dataSource={rows}
          renderItem={m => (
            <List.Item>
              <List.Item.Meta
                title={
                  <span>
                    {m.title || m.message_type}
                    {!m.is_read && <Tag color="red" style={{ marginLeft: 8 }}>未读</Tag>}
                  </span>
                }
                description={m.content || m.body}
              />
              <div style={{ color: '#999', fontSize: 12 }}>{m.created_at && dayjs(m.created_at).format('YYYY-MM-DD HH:mm')}</div>
            </List.Item>
          )}
        />
      )}
    </div>
  );
}
