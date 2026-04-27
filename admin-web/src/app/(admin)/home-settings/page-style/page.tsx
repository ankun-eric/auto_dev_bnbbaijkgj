'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Card, Typography, Modal, Spin, message, Alert } from 'antd';
import {
  CheckCircleOutlined, RobotOutlined, AppstoreOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { get, put } from '@/lib/api';

const { Title, Text } = Typography;

type PageStyleValue = 'ai_chat' | 'menu';

interface StyleOption {
  value: PageStyleValue;
  title: string;
  description: string;
  icon: React.ReactNode;
  badge: string | null;
  badgeColor: string;
}

const styleOptions: StyleOption[] = [
  {
    value: 'ai_chat',
    title: 'AI对话模式',
    description: '以AI对话为核心交互方式，用户通过自然语言获取健康服务，体验更智能、更便捷。',
    icon: <RobotOutlined style={{ fontSize: 40 }} />,
    badge: '推荐',
    badgeColor: '#52c41a',
  },
  {
    value: 'menu',
    title: '菜单模式',
    description: '传统菜单导航方式，用户通过菜单入口访问各功能模块，操作路径清晰明确。',
    icon: <AppstoreOutlined style={{ fontSize: 40 }} />,
    badge: '过渡期',
    badgeColor: '#faad14',
  },
];

export default function PageStylePage() {
  const [loading, setLoading] = useState(false);
  const [currentStyle, setCurrentStyle] = useState<PageStyleValue>('ai_chat');
  const [switching, setSwitching] = useState(false);

  const fetchStyle = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<{ value?: PageStyleValue }>('/api/app-settings/page-style');
      setCurrentStyle(res.value || 'ai_chat');
    } catch {
      message.error('获取页面风格配置失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStyle();
  }, [fetchStyle]);

  const handleSwitch = (targetValue: PageStyleValue) => {
    if (targetValue === currentStyle) return;

    const targetOption = styleOptions.find((o) => o.value === targetValue);
    Modal.confirm({
      title: '确认切换',
      icon: <ExclamationCircleOutlined />,
      content: `确定切换到${targetOption?.title}？切换后用户端将在下次加载时生效。`,
      okText: '确定切换',
      cancelText: '取消',
      onOk: async () => {
        setSwitching(true);
        try {
          await put('/api/admin/app-settings/page-style', { value: targetValue });
          setCurrentStyle(targetValue);
          message.success(`已切换到${targetOption?.title}`);
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '切换失败');
        } finally {
          setSwitching(false);
        }
      },
    });
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>页面风格配置</Title>

      <Spin spinning={loading || switching}>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', maxWidth: 760 }}>
          {styleOptions.map((option) => {
            const isSelected = currentStyle === option.value;
            return (
              <Card
                key={option.value}
                hoverable
                onClick={() => handleSwitch(option.value)}
                style={{
                  flex: '1 1 320px',
                  maxWidth: 360,
                  borderRadius: 12,
                  cursor: isSelected ? 'default' : 'pointer',
                  border: isSelected ? '2px solid #52c41a' : '2px solid transparent',
                  position: 'relative',
                  transition: 'all 0.3s',
                  boxShadow: isSelected
                    ? '0 4px 16px rgba(82, 196, 26, 0.15)'
                    : '0 2px 8px rgba(0, 0, 0, 0.06)',
                }}
                bodyStyle={{ padding: 24, textAlign: 'center' }}
              >
                {option.badge && (
                  <div
                    style={{
                      position: 'absolute',
                      top: 12,
                      right: 12,
                      padding: '2px 10px',
                      borderRadius: 10,
                      fontSize: 12,
                      fontWeight: 600,
                      color: '#fff',
                      background: option.badgeColor,
                    }}
                  >
                    {option.badge}
                  </div>
                )}

                {isSelected && (
                  <div
                    style={{
                      position: 'absolute',
                      top: 12,
                      left: 12,
                    }}
                  >
                    <CheckCircleOutlined style={{ fontSize: 22, color: '#52c41a' }} />
                  </div>
                )}

                <div
                  style={{
                    width: 80,
                    height: 80,
                    borderRadius: '50%',
                    background: isSelected
                      ? 'linear-gradient(135deg, #52c41a, #13c2c2)'
                      : '#f5f5f5',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 16px',
                    color: isSelected ? '#fff' : '#999',
                    transition: 'all 0.3s',
                  }}
                >
                  {option.icon}
                </div>

                <Title
                  level={5}
                  style={{
                    margin: '0 0 8px',
                    color: isSelected ? '#52c41a' : '#333',
                  }}
                >
                  {option.title}
                </Title>

                <Text type="secondary" style={{ fontSize: 13, lineHeight: 1.6 }}>
                  {option.description}
                </Text>
              </Card>
            );
          })}
        </div>

        <Alert
          message="菜单模式为过渡方案，建议使用AI对话模式"
          type="warning"
          showIcon
          style={{ maxWidth: 760, marginTop: 24, borderRadius: 8 }}
        />
      </Spin>
    </div>
  );
}
