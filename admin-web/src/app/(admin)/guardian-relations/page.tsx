'use client';

/**
 * [守护人体系 PRD v1.1 2026-05-25] 后台守护关系查询
 * 支持过滤主守护人、关键词搜索、查看付费/免费状态
 */
import React, { useEffect, useState } from 'react';
import { Table, Tag, Input, Select, Space, Card, Typography, message } from 'antd';
import { get } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;

interface GuardianRelation {
  id: number;
  manager_user_id: number;
  manager_nickname?: string;
  manager_phone?: string;
  managed_user_id: number;
  managed_nickname?: string;
  managed_phone?: string;
  is_primary_guardian: boolean;
  priority_order: number;
  is_paid_manager: boolean;
  created_at: string;
}

export default function GuardianRelationsPage() {
  const [records, setRecords] = useState<GuardianRelation[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [isPrimaryFilter, setIsPrimaryFilter] = useState<string | undefined>(undefined);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const fetchData = async (page = 1, pageSize = 20) => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (keyword) params.keyword = keyword;
      if (isPrimaryFilter === 'true') params.is_primary = true;
      if (isPrimaryFilter === 'false') params.is_primary = false;
      const res: any = await get('/api/admin/guardian/relations', { params });
      const data = res?.data || res;
      setRecords(data.items || []);
      setPagination({ current: page, pageSize, total: data.total || 0 });
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
      setRecords([]);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData(1, pagination.pageSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPrimaryFilter]);

  const columns = [
    {
      title: '守护人',
      key: 'manager',
      render: (_: any, r: GuardianRelation) => (
        <div>
          <div>{r.manager_nickname || `用户#${r.manager_user_id}`}</div>
          <div style={{ color: '#999', fontSize: 12 }}>{r.manager_phone || '-'}</div>
        </div>
      ),
    },
    {
      title: '角色',
      key: 'role',
      render: (_: any, r: GuardianRelation) =>
        r.is_primary_guardian ? (
          <Tag color="gold">⭐ 主守护人</Tag>
        ) : (
          <Tag>普通守护人</Tag>
        ),
    },
    {
      title: '会员等级',
      key: 'paid',
      render: (_: any, r: GuardianRelation) =>
        r.is_paid_manager ? <Tag color="orange">付费</Tag> : <Tag>免费</Tag>,
    },
    {
      title: '被守护人',
      key: 'managed',
      render: (_: any, r: GuardianRelation) => (
        <div>
          <div>{r.managed_nickname || `用户#${r.managed_user_id}`}</div>
          <div style={{ color: '#999', fontSize: 12 }}>{r.managed_phone || '-'}</div>
        </div>
      ),
    },
    {
      title: '优先级',
      dataIndex: 'priority_order',
      key: 'priority',
      render: (v: number) => v,
    },
    {
      title: '绑定时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>守护关系查询</Title>
      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Input.Search
            placeholder="搜索手机号/昵称"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onSearch={() => fetchData(1, pagination.pageSize)}
            style={{ width: 240 }}
            allowClear
          />
          <Select
            placeholder="主守护人筛选"
            value={isPrimaryFilter}
            onChange={(v) => setIsPrimaryFilter(v)}
            allowClear
            style={{ width: 160 }}
            options={[
              { value: 'true', label: '仅主守护人' },
              { value: 'false', label: '仅普通守护人' },
            ]}
          />
        </Space>
        <Table<GuardianRelation>
          dataSource={records}
          columns={columns as any}
          rowKey="id"
          loading={loading}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => fetchData(p, ps),
          }}
        />
      </Card>
    </div>
  );
}
