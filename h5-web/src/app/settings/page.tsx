'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, List, Switch, Dialog, Toast, Button } from 'antd-mobile';
import { logout, useAuth } from '@/lib/auth';
import { useFontSize } from '@/lib/useFontSize';
import FontSettingPopup from '@/components/FontSettingPopup';
import api from '@/lib/api';

export default function SettingsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [pushEnabled, setPushEnabled] = useState(true);
  const [fontPopupVisible, setFontPopupVisible] = useState(false);
  const [fontConfig, setFontConfig] = useState<{
    font_switch_enabled: boolean;
    font_default_level: 'standard' | 'large' | 'xlarge';
    font_standard_size: number;
    font_large_size: number;
    font_xlarge_size: number;
  }>({
    font_switch_enabled: false,
    font_default_level: 'standard',
    font_standard_size: 14,
    font_large_size: 18,
    font_xlarge_size: 22,
  });

  useEffect(() => {
    api.get('/api/home-config').then((res: unknown) => {
      const data = res as Record<string, unknown>;
      setFontConfig({
        font_switch_enabled: !!data.font_switch_enabled,
        font_default_level: (data.font_default_level as 'standard' | 'large' | 'xlarge') || 'standard',
        font_standard_size: (data.font_standard_size as number) || 14,
        font_large_size: (data.font_large_size as number) || 18,
        font_xlarge_size: (data.font_xlarge_size as number) || 22,
      });
    }).catch(() => {});
  }, []);

  const { fontLevel, setFontLevel } = useFontSize(fontConfig);

  const handleLogout = () => {
    Dialog.confirm({
      content: '确定要退出登录吗？',
      confirmText: '退出',
      cancelText: '取消',
      onConfirm: () => {
        logout();
      },
    });
  };

  const handleClearCache = () => {
    Dialog.confirm({
      content: '确定要清除缓存吗？',
      confirmText: '清除',
      cancelText: '取消',
      onConfirm: () => {
        Toast.show({ content: '缓存已清除' });
      },
    });
  };

  const FONT_LEVEL_LABELS: Record<string, string> = {
    standard: '标准',
    large: '大',
    xlarge: '超大',
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        设置
      </NavBar>

      <div className="pt-2">
        <List header="通知设置" style={{ '--border-top': 'none' }}>
          <List.Item extra={<Switch checked={pushEnabled} onChange={setPushEnabled}
            style={{ '--checked-color': '#52c41a' }} />}>
            推送通知
          </List.Item>
          <List.Item extra={<Switch defaultChecked style={{ '--checked-color': '#52c41a' }} />}>
            健康提醒
          </List.Item>
        </List>

        {fontConfig.font_switch_enabled && (
          <List header="显示设置" style={{ '--border-top': 'none' }}>
            <List.Item
              extra={FONT_LEVEL_LABELS[fontLevel] || '标准'}
              arrow
              onClick={() => setFontPopupVisible(true)}
            >
              字体大小
            </List.Item>
          </List>
        )}

        <List header="其他" style={{ '--border-top': 'none' }}>
          <List.Item onClick={handleClearCache} arrow>
            清除缓存
          </List.Item>
          <List.Item extra="1.0.0" arrow={false}>
            当前版本
          </List.Item>
          <List.Item arrow>用户协议</List.Item>
          <List.Item arrow>隐私政策</List.Item>
          <List.Item arrow>关于我们</List.Item>
        </List>

        <div className="px-4 mt-6 mb-8">
          <Button
            block
            onClick={handleLogout}
            style={{
              color: '#f5222d',
              borderColor: '#f5222d',
              borderRadius: 24,
              height: 44,
            }}
          >
            退出登录
          </Button>
        </div>
      </div>

      <FontSettingPopup
        visible={fontPopupVisible}
        onClose={() => setFontPopupVisible(false)}
        fontLevel={fontLevel}
        onFontLevelChange={setFontLevel}
        standardSize={fontConfig.font_standard_size}
        largeSize={fontConfig.font_large_size}
        xlargeSize={fontConfig.font_xlarge_size}
      />
    </div>
  );
}
