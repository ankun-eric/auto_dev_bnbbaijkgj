'use client';

import React, { useEffect, useState } from 'react';
import { Card, Descriptions, Typography, Spin, Alert, message } from 'antd';
import api from '@/lib/api';
import { getProfile, getCurrentStoreId } from '../lib';

const { Title } = Typography;

export default function StoreSettingsPage() {
  const [loading, setLoading] = useState(true);
  const [info, setInfo] = useState<any>(null);
  const profile = getProfile();
  const storeId = getCurrentStoreId();

  useEffect(() => {
    api.get('/api/merchant/v1/dashboard/metrics', { params: storeId ? { store_id: storeId } : {} })
      .then((d: any) => setInfo(d))
      .catch((e: any) => message.error(e?.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, [storeId]);

  if (loading) return <Spin />;

  return (
    <div>
      <Title level={4}>门店设置</Title>
      <Alert type="info" showIcon message="门店主数据统一由平台管理员维护。如需调整营业时间、联系方式等，请联系平台客服。" style={{ marginBottom: 16 }} />
      <Card>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="机构名称">{profile?.merchant_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="当前登录角色">{profile?.role}</Descriptions.Item>
          <Descriptions.Item label="当前门店">{info?.store_name || '(全部)'}</Descriptions.Item>
          <Descriptions.Item label="门店总数">{profile?.stores?.length || 0}</Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  );
}
