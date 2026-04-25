'use client';

// [2026-04-24] 移动端 - 我的 PRD §4.9

import React, { useEffect, useState } from 'react';
import { List, Button, Toast, Dialog } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import { getProfile, logoutMerchantMobile, roleLabel, MerchantLoginProfile, getCurrentStoreId, setCurrentStoreId } from '../mobile-lib';

export default function MeMobilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<MerchantLoginProfile | null>(null);
  const [storeId, setStoreId] = useState<number | null>(null);

  useEffect(() => {
    setProfile(getProfile());
    setStoreId(getCurrentStoreId());
  }, []);

  const currentStoreName = React.useMemo(() => {
    if (!profile) return '';
    const s = profile.stores.find((x) => x.id === storeId);
    return s?.name || profile.stores[0]?.name || '';
  }, [profile, storeId]);

  const switchStore = async () => {
    if (!profile || profile.stores.length <= 1) return;
    const result = await Dialog.show({
      title: '切换门店',
      closeOnAction: true,
      actions: [
        profile.stores.map((s) => ({
          key: String(s.id),
          text: s.name + (s.id === storeId ? ' ✓' : ''),
        })),
        [{ key: 'cancel', text: '取消' }],
      ],
    });
    const sid = Number((result as any) ?? 0);
    if (sid && sid !== storeId) {
      setCurrentStoreId(sid);
      setStoreId(sid);
      Toast.show({ icon: 'success', content: '已切换门店' });
    }
  };

  const copyPc = () => {
    const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
    const url = `${window.location.origin}${basePath}/merchant/dashboard?desktop=1`;
    navigator.clipboard?.writeText(url).then(
      () => Toast.show({ icon: 'success', content: 'PC 端链接已复制到剪贴板' }),
      () => Dialog.alert({ title: 'PC 端链接', content: url })
    );
  };

  const doLogout = async () => {
    const ok = await Dialog.confirm({ title: '退出登录', content: '确认退出登录？' });
    if (ok) logoutMerchantMobile();
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa', paddingBottom: 24 }}>
      {/* 顶部 */}
      <div
        style={{
          background: 'linear-gradient(135deg, #52c41a 0%, #73d13d 100%)',
          color: '#fff',
          padding: '36px 20px 28px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'rgba(255,255,255,0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 28,
            }}
          >
            👤
          </div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>{profile?.merchant_name || '商家'}</div>
            <div style={{ fontSize: 13, opacity: 0.9, marginTop: 4 }}>
              {profile ? roleLabel[profile.role] || profile.role : ''}
              {currentStoreName ? ` · ${currentStoreName}` : ''}
            </div>
          </div>
        </div>
      </div>

      <List style={{ margin: 12, borderRadius: 10, overflow: 'hidden' }}>
        {profile && profile.stores.length > 1 && (
          <List.Item prefix="🏬" onClick={switchStore} clickable extra={currentStoreName}>
            切换门店
          </List.Item>
        )}
        <List.Item prefix="💬" onClick={() => router.push('/merchant/m/messages')} clickable>
          消息中心
        </List.Item>
        <List.Item prefix="🧾" onClick={() => router.push('/merchant/m/invoice')} clickable>
          发票管理
        </List.Item>
        <List.Item prefix="📥" onClick={() => router.push('/merchant/m/downloads')} clickable>
          下载中心
        </List.Item>
      </List>

      <List style={{ margin: 12, borderRadius: 10, overflow: 'hidden' }}>
        <List.Item prefix="🖥️" onClick={copyPc} clickable>
          访问 PC 版（复制链接）
        </List.Item>
        <List.Item
          prefix="👤"
          onClick={() => router.push('/merchant/m/profile')}
          clickable
        >
          个人信息
        </List.Item>
        <List.Item
          prefix="🏪"
          onClick={() => router.push('/merchant/m/store-settings')}
          clickable
        >
          店铺信息
        </List.Item>
        <List.Item
          prefix="🔐"
          onClick={() => router.push('/merchant/m/profile/change-password')}
          clickable
        >
          修改密码
        </List.Item>
        <List.Item prefix="ℹ️" extra="v1.0">
          关于我们
        </List.Item>
      </List>

      <div style={{ padding: '12px 12px 24px' }}>
        <Button block color="danger" fill="outline" size="large" onClick={doLogout}>
          退出登录
        </Button>
      </div>
    </div>
  );
}
