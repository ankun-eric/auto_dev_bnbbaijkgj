'use client';

// [2026-04-24] 移动端 - 选择门店页

import React, { useEffect, useState } from 'react';
import { List, Empty, Button } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import { getProfile, isAuthed, setCurrentStoreId, MerchantLoginProfile } from '../mobile-lib';

export default function SelectStoreMobilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<MerchantLoginProfile | null>(null);

  useEffect(() => {
    if (!isAuthed()) {
      router.replace('/merchant/m/login');
      return;
    }
    setProfile(getProfile());
  }, [router]);

  if (!profile) return null;

  const enter = (storeId: number) => {
    setCurrentStoreId(storeId);
    router.push('/merchant/m/dashboard');
  };

  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontSize: 20, fontWeight: 600, marginBottom: 16 }}>选择进入门店</div>
      {profile.stores.length === 0 ? (
        <Empty description="您还未被绑定到任何门店，请联系平台客服" />
      ) : (
        <List>
          {profile.stores.map((s) => (
            <List.Item
              key={s.id}
              prefix={<span style={{ fontSize: 24 }}>🏬</span>}
              onClick={() => enter(s.id)}
              clickable
              extra={<Button size="mini" color="primary">进入</Button>}
            >
              <div style={{ fontSize: 15, fontWeight: 500 }}>{s.name}</div>
            </List.Item>
          ))}
        </List>
      )}
    </div>
  );
}
