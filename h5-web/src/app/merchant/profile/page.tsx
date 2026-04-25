'use client';

// [PRD V1.0 §M3] 商家 PC 端 - 个人信息（只读）
// 数据来源：GET /api/merchant/profile

import React, { useEffect, useState } from 'react';
import { Card, Descriptions, Tag, Spin, Alert, Typography, Space, Button } from 'antd';
import { LockOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

const { Title } = Typography;

interface MerchantProfileFull {
  id: number;
  name?: string;
  phone?: string;
  role_code: string;
  role_name: string;
  merchant_name?: string;
  store_names: string[];
  store_ids: number[];
  must_change_password: boolean;
}

export default function MerchantProfilePage() {
  const router = useRouter();
  const [data, setData] = useState<MerchantProfileFull | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    setLoading(true);
    api
      .get<MerchantProfileFull, MerchantProfileFull>('/api/merchant/profile')
      .then((d) => setData(d))
      .catch((e: any) => setErr(e?.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <Title level={4}>个人信息</Title>
      {err && <Alert type="error" showIcon message={err} style={{ marginBottom: 16 }} />}
      <Spin spinning={loading}>
        <Card>
          <Descriptions column={1} labelStyle={{ width: 120 }}>
            <Descriptions.Item label="姓名">{data?.name || '—'}</Descriptions.Item>
            <Descriptions.Item label="手机号">{data?.phone || '—'}</Descriptions.Item>
            <Descriptions.Item label="角色">
              <Tag color="purple">{data?.role_name || '—'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="所属门店">
              {data?.store_names?.length ? (
                <Space wrap>
                  {data.store_names.map((n, i) => (
                    <Tag key={i} color="green">{n}</Tag>
                  ))}
                </Space>
              ) : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="所属商家">{data?.merchant_name || '—'}</Descriptions.Item>
          </Descriptions>
          <div style={{ marginTop: 16 }}>
            <Button
              type="primary"
              icon={<LockOutlined />}
              onClick={() => router.push('/merchant/profile/change-password')}
            >
              修改密码
            </Button>
          </div>
          <div style={{ marginTop: 16, color: '#999', fontSize: 12 }}>
            如需修改信息，请联系老板。
          </div>
        </Card>
      </Spin>
    </div>
  );
}
