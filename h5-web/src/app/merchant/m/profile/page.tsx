'use client';

// [PRD V1.0 §M3] 商家 H5 - 个人信息（只读）
// 数据来源：GET /api/merchant/profile

import React, { useEffect, useState } from 'react';
import { NavBar, List, Tag, Toast, Button } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

interface MerchantProfileFull {
  id: number;
  name?: string;
  phone?: string;
  role_code: string;
  role_name: string;
  merchant_name?: string;
  store_names: string[];
  store_ids: number[];
}

export default function MerchantMobileProfilePage() {
  const router = useRouter();
  const [data, setData] = useState<MerchantProfileFull | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .get<MerchantProfileFull, MerchantProfileFull>('/api/merchant/profile')
      .then(setData)
      .catch((e: any) => Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '加载失败' }))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa' }}>
      <NavBar onBack={() => router.back()}>个人信息</NavBar>
      <div style={{ padding: 12 }}>
        <List style={{ borderRadius: 10, overflow: 'hidden' }}>
          <List.Item extra={data?.name || '—'}>姓名</List.Item>
          <List.Item extra={data?.phone || '—'}>手机号</List.Item>
          <List.Item extra={<Tag color="primary">{data?.role_name || '—'}</Tag>}>角色</List.Item>
          <List.Item
            extra={
              <span style={{ maxWidth: 200, textAlign: 'right' }}>
                {data?.store_names?.length ? data.store_names.join('、') : '—'}
              </span>
            }
          >
            所属门店
          </List.Item>
          <List.Item extra={data?.merchant_name || '—'}>所属商家</List.Item>
        </List>

        <div style={{ marginTop: 16 }}>
          <Button
            block
            color="primary"
            fill="outline"
            onClick={() => router.push('/merchant/m/profile/change-password')}
          >
            修改密码
          </Button>
        </div>

        <div style={{ marginTop: 16, color: '#999', fontSize: 12, textAlign: 'center' }}>
          如需修改信息，请联系老板。
        </div>
      </div>
    </div>
  );
}
