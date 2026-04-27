'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { List, Switch, Dialog, Toast, Button, NavBar } from 'antd-mobile';
import { THEME } from '@/lib/theme';
import { logout, useAuth } from '@/lib/auth';
import api from '@/lib/api';

export default function AiSettingsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [pushEnabled, setPushEnabled] = useState(true);
  const [healthReminder, setHealthReminder] = useState(true);
  const [dataSharing, setDataSharing] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);

  const handleLogout = () => {
    Dialog.confirm({
      content: '确定要退出登录吗？',
      confirmText: '退出',
      cancelText: '取消',
      onConfirm: () => { logout(); },
    });
  };

  const handleClearCache = () => {
    Dialog.confirm({
      content: '确定要清除缓存吗？',
      confirmText: '清除',
      cancelText: '取消',
      onConfirm: () => {
        Toast.show({ content: '缓存已清除', icon: 'success' });
      },
    });
  };

  const switchStyle = { '--checked-color': THEME.primary } as React.CSSProperties;

  return (
    <div className="min-h-screen" style={{ background: THEME.background }}>
      <NavBar
        onBack={() => router.back()}
        style={{ background: THEME.cardBg, '--border-bottom': `1px solid ${THEME.divider}` } as React.CSSProperties}
      >
        <span style={{ color: THEME.textPrimary, fontWeight: 600 }}>设置</span>
      </NavBar>

      <div className="pt-2 pb-24">
        <List header="个人信息" style={{ '--border-top': 'none', '--header-font-size': '13px' } as React.CSSProperties}>
          <List.Item
            arrow
            extra={user?.nickname || '未设置'}
            onClick={() => router.push('/profile/edit')}
          >
            个人资料
          </List.Item>
          <List.Item arrow onClick={() => router.push('/account-security')}>
            账号安全
          </List.Item>
        </List>

        <List header="通知设置" style={{ '--border-top': 'none', '--header-font-size': '13px' } as React.CSSProperties}>
          <List.Item extra={<Switch checked={pushEnabled} onChange={setPushEnabled} style={switchStyle} />}>
            推送通知
          </List.Item>
          <List.Item extra={<Switch checked={healthReminder} onChange={setHealthReminder} style={switchStyle} />}>
            健康提醒
          </List.Item>
        </List>

        <List header="隐私设置" style={{ '--border-top': 'none', '--header-font-size': '13px' } as React.CSSProperties}>
          <List.Item extra={<Switch checked={dataSharing} onChange={setDataSharing} style={switchStyle} />}>
            数据共享
          </List.Item>
          <List.Item arrow>
            隐私政策
          </List.Item>
        </List>

        <List header="语音设置" style={{ '--border-top': 'none', '--header-font-size': '13px' } as React.CSSProperties}>
          <List.Item extra={<Switch checked={voiceEnabled} onChange={setVoiceEnabled} style={switchStyle} />}>
            语音输入
          </List.Item>
        </List>

        <List header="存储" style={{ '--border-top': 'none', '--header-font-size': '13px' } as React.CSSProperties}>
          <List.Item arrow onClick={handleClearCache}>
            清除缓存
          </List.Item>
        </List>

        <List header="关于" style={{ '--border-top': 'none', '--header-font-size': '13px' } as React.CSSProperties}>
          <List.Item extra="1.0.0" arrow={false}>
            当前版本
          </List.Item>
          <List.Item arrow>用户协议</List.Item>
          <List.Item arrow>隐私政策</List.Item>
          <List.Item arrow onClick={() => router.push('/feedback')}>
            意见反馈
          </List.Item>
          <List.Item arrow>关于我们</List.Item>
        </List>

        <div className="px-4 mt-6">
          <Button
            block
            onClick={handleLogout}
            style={{
              color: '#FF4D4F',
              borderColor: '#FF4D4F',
              borderRadius: 24,
              height: 44,
              background: 'transparent',
            }}
          >
            退出登录
          </Button>
        </div>
      </div>
    </div>
  );
}
