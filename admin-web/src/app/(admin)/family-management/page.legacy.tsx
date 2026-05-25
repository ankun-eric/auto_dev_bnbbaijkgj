'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Tag, Modal, Descriptions, message, Typography, Select, Popconfirm } from 'antd';
import { EyeOutlined, DisconnectOutlined } from '@ant-design/icons';
import { get, del } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;

type ManagementStatus = 'active' | 'cancelled';

interface ManagementRecord {
  id: number;
  managerUserId: number;
  managerNickname: string;
  managerPhone: string;
  managedUserId: number;
  managedNickname: string;
  managedPhone: string;
  managedMemberId: number;
  status: ManagementStatus;
  createdAt: string;
  cancelledAt: string | null;
}

function mapApiRecord(row: Record<string, unknown>): ManagementRecord {
  const status: ManagementStatus =
    row.status === 'cancelled' ? 'cancelled' : 'active';

  return {
    id: Number(row.id),
    managerUserId: Number(row.manager_user_id ?? 0),
    managerNickname: String(row.manager_nickname ?? '-'),
    managerPhone: String(row.manager_phone ?? '-'),
    managedUserId: Number(row.managed_user_id ?? 0),
    managedNickname: String(row.managed_user_nickname ?? row.managed_nickname ?? '-'),
    managedPhone: String(row.managed_phone ?? '-'),
    managedMemberId: Number(row.managed_member_id ?? 0),
    status,
    createdAt: String(row.created_at ?? ''),
    cancelledAt: row.cancelled_at ? String(row.cancelled_at) : null,
  };
}

export default function FamilyManagementPage() {
  const [records, setRecords] = useState<ManagementRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [detailVisible, setDetailVisible] = useState(false);
  const [currentRecord, setCurrentRecord] = useState<ManagementRecord | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  // TODO: 后端需要增加管理员级别的接口 GET /api/admin/family-management
  // 当前使用的接口需要后端配合开发，暂时先尝试调用，失败后回退到空列表
  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get<{
        items?: Record<string, unknown>[];
        list?: Record<string, unknown>[];
        total?: number;
        page?: number;
        page_size?: number;
      }>('/api/admin/family-management', {
        page,
        page_size: pageSize,
        ...(statusFilter ? { status: statusFilter } : {}),
      });

      const rawItems = res.items ?? res.list ?? [];
      const items = Array.isArray(rawItems) ? rawItems.map(mapApiRecord) : [];
      setRecords(items);
      setPagination((prev) => ({
        ...prev,
        current: res.page ?? page,
        pageSize: res.page_size ?? pageSize,
        total: res.total ?? items.length,
      }));
    } catch {
      setRecords([]);
      setPagination((prev) => ({ ...prev, current: page, pageSize, total: 0 }));
    } finally {
      setLoading(false);
    }
  };

  // TODO: 后端需要增加管理员解除关联接口 DELETE /api/admin/family-management/:id
  const handleCancel = async (record: ManagementRecord) => {
    try {
      await del(`/api/admin/family-management/${record.id}`);
      message.success('已解除关联关系');
      setRecords((prev) =>
        prev.map((r) =>
          r.id === record.id ? { ...r, status: 'cancelled' as ManagementStatus, cancelledAt: new Date().toISOString() } : r
        )
      );
      if (currentRecord?.id === record.id) {
        setCurrentRecord((prev) =>
          prev ? { ...prev, status: 'cancelled', cancelledAt: new Date().toISOString() } : prev
        );
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { message?: string; detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.response?.data?.message || err?.message || '操作失败');
    }
  };

  const statusTag = (status: ManagementStatus) => {
    if (status === 'active') return <Tag color="green">生效中</Tag>;
    if (status === 'cancelled') return <Tag color="default">已取消</Tag>;
    return <Tag>{status}</Tag>;
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    {
      title: '管理者',
      key: 'manager',
      width: 180,
      render: (_: unknown, record: ManagementRecord) => (
        <div>
          <div>{record.managerNickname}</div>
          <div style={{ fontSize: 12, color: '#999' }}>{record.managerPhone}</div>
        </div>
      ),
    },
    {
      title: '被管理方',
      key: 'managed',
      width: 180,
      render: (_: unknown, record: ManagementRecord) => (
        <div>
          <div>{record.managedNickname}</div>
          <div style={{ fontSize: 12, color: '#999' }}>{record.managedPhone}</div>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: ManagementStatus) => statusTag(v),
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 170,
      render: (v: string) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '取消时间',
      dataIndex: 'cancelledAt',
      key: 'cancelledAt',
      width: 170,
      render: (v: string | null) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: unknown, record: ManagementRecord) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => { setCurrentRecord(record); setDetailVisible(true); }}
          >
            详情
          </Button>
          {record.status === 'active' && (
            <Popconfirm
              title="确定解除该共管关系？"
              description="解除后双方将无法再查看对方的健康档案"
              onConfirm={() => handleCancel(record)}
            >
              <Button type="link" size="small" danger icon={<DisconnectOutlined />}>
                解除
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>家庭共管关系管理</Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          placeholder="按状态筛选"
          allowClear
          style={{ width: 160 }}
          value={statusFilter}
          onChange={(val) => setStatusFilter(val)}
          options={[
            { label: '生效中', value: 'active' },
            { label: '已取消', value: 'cancelled' },
          ]}
        />
        <Button type="primary" onClick={() => fetchData(1)}>查询</Button>
        <Button onClick={() => { setStatusFilter(undefined); setTimeout(() => fetchData(1), 0); }}>重置</Button>
      </Space>

      <Table
        columns={columns}
        dataSource={records}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1100 }}
      />

      <Modal
        title="共管关系详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={600}
      >
        {currentRecord && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="ID">{currentRecord.id}</Descriptions.Item>
            <Descriptions.Item label="状态">{statusTag(currentRecord.status)}</Descriptions.Item>
            <Descriptions.Item label="管理者昵称">{currentRecord.managerNickname}</Descriptions.Item>
            <Descriptions.Item label="管理者手机号">{currentRecord.managerPhone}</Descriptions.Item>
            <Descriptions.Item label="被管理方昵称">{currentRecord.managedNickname}</Descriptions.Item>
            <Descriptions.Item label="被管理方手机号">{currentRecord.managedPhone}</Descriptions.Item>
            <Descriptions.Item label="被管理成员ID">{currentRecord.managedMemberId}</Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {currentRecord.createdAt ? dayjs(currentRecord.createdAt).format('YYYY-MM-DD HH:mm:ss') : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="取消时间" span={2}>
              {currentRecord.cancelledAt ? dayjs(currentRecord.cancelledAt).format('YYYY-MM-DD HH:mm:ss') : '-'}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
}
