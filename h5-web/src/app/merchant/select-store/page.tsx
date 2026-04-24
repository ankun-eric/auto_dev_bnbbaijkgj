'use client';

import React from 'react';
import { Card, List, Button, Typography, Empty } from 'antd';
import { ShopOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import { getProfile, setCurrentStoreId, isAuthed } from '../lib';
import { useEffect, useState } from 'react';

const { Title } = Typography;

export default function SelectStorePage() {
  const router = useRouter();
  const [profile, setProfile] = useState(getProfile());

  useEffect(() => {
    if (!isAuthed()) {
      router.replace('/merchant/login');
      return;
    }
    setProfile(getProfile());
  }, [router]);

  if (!profile) return null;

  const enter = (storeId: number) => {
    setCurrentStoreId(storeId);
    router.push('/merchant/dashboard');
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5', padding: '40px 16px' }}>
      <Card style={{ maxWidth: 640, margin: '0 auto' }}>
        <Title level={4}>选择进入门店</Title>
        {profile.stores.length === 0 ? (
          <Empty description="您还未被绑定到任何门店，请联系平台客服" />
        ) : (
          <List
            dataSource={profile.stores}
            renderItem={s => (
              <List.Item
                actions={[
                  <Button key="enter" type="primary" onClick={() => enter(s.id)}>
                    进入
                  </Button>,
                ]}
              >
                <List.Item.Meta avatar={<ShopOutlined style={{ fontSize: 24, color: '#52c41a' }} />} title={s.name} />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
}
