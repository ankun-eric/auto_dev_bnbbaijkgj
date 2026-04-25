'use client';

import React, { useEffect, useState } from 'react';
import { Card, Descriptions, Spin, Typography, Tag } from 'antd';
import { get } from '@/lib/api';

const { Text, Title } = Typography;

interface AdminProfile {
  id: number;
  name?: string;
  phone?: string;
  role: string;
  role_name: string;
  merchant_name: string;
  is_superuser: boolean;
  must_change_password: boolean;
}

export default function AdminProfilePage() {
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<AdminProfile | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await get<AdminProfile>('/api/admin/profile');
        setProfile(res);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>
        个人信息
      </Title>
      <Card>
        {loading ? (
          <Spin />
        ) : profile ? (
          <Descriptions column={1} bordered labelStyle={{ width: 160, background: '#fafafa' }}>
            <Descriptions.Item label="姓名">{profile.name || '-'}</Descriptions.Item>
            <Descriptions.Item label="手机号">{profile.phone || '-'}</Descriptions.Item>
            <Descriptions.Item label="角色">
              <Tag color="blue">{profile.role_name || '管理员'}</Tag>
              {profile.is_superuser && <Tag color="gold">超级管理员</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="所属商家">{profile.merchant_name || '平台'}</Descriptions.Item>
          </Descriptions>
        ) : (
          <Text type="secondary">未获取到信息</Text>
        )}
        <div style={{ marginTop: 24, color: '#999', fontSize: 12 }}>
          如需修改信息，请联系超级管理员。
        </div>
      </Card>
    </div>
  );
}
