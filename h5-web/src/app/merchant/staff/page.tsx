'use client';

import React, { useEffect, useState } from 'react';
import { Table, Typography, Tag, Alert, message } from 'antd';
import api from '@/lib/api';

const { Title, Paragraph } = Typography;

const roleLabel: Record<string, string> = {
  owner: '老板', store_manager: '店长', verifier: '核销员', finance: '财务', staff: '员工',
};

export default function StaffPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.get('/api/merchant/v1/staff').then((d: any) => setRows(d || [])).catch((e: any) => message.error(e?.response?.data?.detail || '加载失败')).finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <Title level={4}>员工与权限</Title>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="员工的增删与权限变更由平台管理员负责，如需调整请联系平台客服。"
      />
      <Table
        rowKey="user_id"
        loading={loading}
        dataSource={rows}
        pagination={false}
        columns={[
          { title: '手机号', dataIndex: 'phone' },
          { title: '昵称', dataIndex: 'nickname' },
          { title: '所属门店ID', dataIndex: 'store_ids', render: (v: number[]) => (v || []).join(', ') },
          { title: '角色', dataIndex: 'member_role', render: (v: string) => <Tag color="blue">{roleLabel[v] || v}</Tag> },
          { title: '状态', dataIndex: 'status' },
        ] as any}
      />
    </div>
  );
}
