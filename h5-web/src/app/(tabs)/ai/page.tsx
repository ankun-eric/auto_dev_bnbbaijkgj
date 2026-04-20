'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { List, Card, Button, Tag, FloatingBubble, Toast, SpinLoading } from 'antd-mobile';
import { AddOutline, MessageOutline } from 'antd-mobile-icons';
import api from '@/lib/api';
import ChatSidebar from '@/components/ChatSidebar';

const consultTypes = [
  {
    key: 'health_qa',
    title: '健康问答',
    desc: 'AI健康顾问在线解答',
    icon: '💬',
    color: '#52c41a',
  },
  {
    key: 'symptom',
    title: '健康自查',
    desc: '智能健康自查参考',
    icon: '🔍',
    color: '#1890ff',
  },
  {
    key: 'tcm',
    title: '中医养生',
    desc: '中医养生体质调理',
    icon: '🏥',
    color: '#eb2f96',
  },
  {
    key: 'drug',
    title: '用药参考',
    desc: '用药参考与注意事项',
    icon: '💊',
    color: '#fa8c16',
  },
];

interface SessionItem {
  id: number;
  title: string;
  session_type: string;
  updated_at: string;
}

const typeLabel: Record<string, { text: string; color: string }> = {
  health_qa: { text: '问答', color: '#52c41a' },
  health: { text: '问答', color: '#52c41a' },
  symptom_check: { text: '健康自查', color: '#1890ff' },
  symptom: { text: '健康自查', color: '#1890ff' },
  tcm: { text: '养生', color: '#eb2f96' },
  drug_query: { text: '用药参考', color: '#fa8c16' },
  drug: { text: '用药参考', color: '#fa8c16' },
};

export default function AIPage() {
  const router = useRouter();
  const [recentChats, setRecentChats] = useState<SessionItem[]>([]);
  const [creating, setCreating] = useState(false);
  const [sidebarVisible, setSidebarVisible] = useState(false);
  // Bug 7：AI 咨询页标题栏不显示 LOGO（保留 AI 头像渐变圆 + 标题文字即可）
  const fetchSessions = useCallback(async () => {
    try {
      const res: any = await api.get('/api/chat/sessions', { params: { page: 1, page_size: 10 } });
      const data = res.data || res;
      setRecentChats(data.items || []);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const startNewChat = async (type: string) => {
    if (creating) return;
    setCreating(true);
    try {
      const res: any = await api.post('/api/chat/sessions', {
        session_type: type,
        title: '新对话',
      });
      const data = res.data || res;
      const sessionId = data.id;
      router.push(`/chat/${sessionId}?type=${type}`);
    } catch {
      Toast.show({ content: '创建会话失败，请检查网络或登录状态', icon: 'fail' });
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="pb-20">
      <div className="gradient-header">
        <div className="flex items-center justify-between">
          <button
            onClick={() => setSidebarVisible(true)}
            className="w-9 h-9 flex items-center justify-center rounded-lg"
            style={{ background: 'rgba(255,255,255,0.2)' }}
            aria-label="打开历史对话"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <div className="text-center flex-1">
            <div className="flex items-center justify-center gap-2">
              {/* v6: AI 头像统一为绿青渐变圆 + 白色 "AI" 文字（去 LOGO） */}
              <span
                className="ai-avatar-gradient"
                style={{ width: 32, height: 32, fontSize: 12 }}
              >
                AI
              </span>
              <h1 className="text-xl font-bold">AI健康咨询</h1>
            </div>
            <p className="text-xs opacity-80 mt-1">选择咨询类型，开始健康咨询</p>
          </div>
          <div className="w-9" />
        </div>
      </div>

      <div className="px-4 -mt-4">
        <div className="grid grid-cols-2 gap-3 mb-4">
          {consultTypes.map((ct) => (
            <div
              key={ct.key}
              className="card cursor-pointer"
              onClick={() => {
                if (ct.key === 'symptom') router.push('/symptom');
                else if (ct.key === 'tcm') router.push('/tcm');
                else if (ct.key === 'drug') router.push('/drug');
                else startNewChat(ct.key);
              }}
              style={{ opacity: creating ? 0.6 : 1, pointerEvents: creating ? 'none' : 'auto' }}
            >
              <div className="flex items-start">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-xl mr-3"
                  style={{ background: `${ct.color}15` }}
                >
                  {ct.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm">{ct.title}</div>
                  <div className="text-xs text-gray-400 mt-1">{ct.desc}</div>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between mb-3">
          <span className="section-title mb-0">最近对话</span>
          <button
            className="text-xs px-3 py-1 rounded-full"
            style={{ color: '#52c41a', background: '#f0faf0' }}
            onClick={() => setSidebarVisible(true)}
          >
            查看全部
          </button>
        </div>

        {recentChats.length === 0 ? (
          <div className="card text-center py-10">
            <MessageOutline style={{ fontSize: 40, color: '#ddd' }} />
            <p className="text-sm text-gray-400 mt-3">暂无对话记录</p>
            <Button
              size="small"
              onClick={() => startNewChat('health_qa')}
              loading={creating}
              style={{
                marginTop: 12,
                color: '#52c41a',
                borderColor: '#52c41a',
                borderRadius: 20,
              }}
            >
              开始第一次健康咨询
            </Button>
          </div>
        ) : (
          <List style={{ '--border-top': 'none', '--border-bottom': 'none' }}>
            {recentChats.map((chat) => {
              const label = typeLabel[chat.session_type] || { text: '对话', color: '#999' };
              return (
                <Card
                  key={chat.id}
                  onClick={() => router.push(`/chat/${chat.id}`)}
                  style={{ marginBottom: 8, borderRadius: 12 }}
                >
                  <div className="flex items-start">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center">
                        <span className="font-medium text-sm">{chat.title}</span>
                        <Tag
                          style={{
                            '--border-radius': '4px',
                            '--background-color': `${label.color}15`,
                            '--text-color': label.color,
                            '--border-color': 'transparent',
                            fontSize: 10,
                            marginLeft: 8,
                          }}
                        >
                          {label.text}
                        </Tag>
                      </div>
                    </div>
                    <span className="text-xs text-gray-300 ml-2 whitespace-nowrap">
                      {new Date(chat.updated_at).toLocaleDateString('zh-CN')}
                    </span>
                  </div>
                </Card>
              );
            })}
          </List>
        )}
      </div>

      <FloatingBubble
        style={{
          '--initial-position-bottom': 'calc(80px + env(safe-area-inset-bottom))',
          '--initial-position-right': '20px',
          '--edge-distance': '20px',
          '--background': 'linear-gradient(135deg, #52c41a, #13c2c2)',
          '--size': '52px',
        }}
        onClick={() => startNewChat('health_qa')}
      >
        <AddOutline fontSize={24} color="#fff" />
      </FloatingBubble>

      <ChatSidebar
        visible={sidebarVisible}
        onClose={() => setSidebarVisible(false)}
      />
    </div>
  );
}
