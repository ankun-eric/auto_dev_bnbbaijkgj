'use client';

import React, { useEffect, useState, useRef } from 'react';
import { Layout, List, Avatar, Input, Button, Badge, Tag, Typography, Space, Descriptions, Empty, Popconfirm, message } from 'antd';
import { SendOutlined, UserOutlined, CloseCircleOutlined, CheckCircleOutlined, CustomerServiceOutlined } from '@ant-design/icons';

const { Sider, Content } = Layout;
const { Title, Text } = Typography;

interface ChatSession {
  id: string;
  userId: number;
  userName: string;
  userPhone: string;
  avatar: string;
  lastMessage: string;
  lastTime: string;
  unread: number;
  status: 'waiting' | 'active' | 'closed';
}

interface ChatMessage {
  id: string;
  sender: 'user' | 'admin';
  content: string;
  time: string;
}

const mockSessions: ChatSession[] = [
  { id: 's1', userId: 1, userName: '张三', userPhone: '138****1234', avatar: '', lastMessage: '你好，我想咨询一下营养方案', lastTime: '10:30', unread: 2, status: 'waiting' },
  { id: 's2', userId: 2, userName: '李四', userPhone: '139****5678', avatar: '', lastMessage: '我的订单什么时候可以完成？', lastTime: '10:15', unread: 1, status: 'active' },
  { id: 's3', userId: 3, userName: '王五', userPhone: '137****9012', avatar: '', lastMessage: '体检报告解读结果在哪里看？', lastTime: '09:45', unread: 0, status: 'active' },
  { id: 's4', userId: 4, userName: '赵六', userPhone: '136****3456', avatar: '', lastMessage: '我要申请退款', lastTime: '09:20', unread: 3, status: 'waiting' },
  { id: 's5', userId: 5, userName: '孙七', userPhone: '135****7890', avatar: '', lastMessage: '感谢解答，问题已解决！', lastTime: '昨天', unread: 0, status: 'closed' },
];

const mockMessages: Record<string, ChatMessage[]> = {
  s1: [
    { id: 'm1', sender: 'user', content: '你好，请问在吗？', time: '10:25' },
    { id: 'm2', sender: 'admin', content: '您好！我是宾尼小康客服，请问有什么可以帮您？', time: '10:26' },
    { id: 'm3', sender: 'user', content: '我想咨询一下营养方案的具体内容', time: '10:28' },
    { id: 'm4', sender: 'user', content: '你好，我想咨询一下营养方案', time: '10:30' },
  ],
  s2: [
    { id: 'm5', sender: 'user', content: '你好，我下了一个深度健康咨询的订单', time: '10:00' },
    { id: 'm6', sender: 'admin', content: '您好，请提供您的订单号，我帮您查看', time: '10:02' },
    { id: 'm7', sender: 'user', content: '订单号是 ORD20260327002', time: '10:05' },
    { id: 'm8', sender: 'admin', content: '已查到您的订单，目前正在处理中，预计2小时内完成', time: '10:08' },
    { id: 'm9', sender: 'user', content: '我的订单什么时候可以完成？', time: '10:15' },
  ],
  s3: [
    { id: 'm10', sender: 'user', content: '体检报告解读结果在哪里看？', time: '09:45' },
  ],
  s4: [
    { id: 'm11', sender: 'user', content: '我对中医体质辨识服务不满意', time: '09:10' },
    { id: 'm12', sender: 'user', content: '感觉分析结果不准确', time: '09:15' },
    { id: 'm13', sender: 'user', content: '我要申请退款', time: '09:20' },
  ],
  s5: [
    { id: 'm14', sender: 'user', content: '心理评估的结果我不太理解', time: '昨天 15:00' },
    { id: 'm15', sender: 'admin', content: '您好，心理评估结果说明已发送到您的消息中，您可以查看详细解读', time: '昨天 15:05' },
    { id: 'm16', sender: 'user', content: '感谢解答，问题已解决！', time: '昨天 15:10' },
  ],
};

export default function CustomerServicePage() {
  const [sessions, setSessions] = useState<ChatSession[]>(mockSessions);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeSession) {
      setMessages(mockMessages[activeSession] || []);
      setSessions((prev) =>
        prev.map((s) => (s.id === activeSession ? { ...s, unread: 0 } : s))
      );
    }
  }, [activeSession]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!inputValue.trim() || !activeSession) return;
    const newMsg: ChatMessage = {
      id: `m${Date.now()}`,
      sender: 'admin',
      content: inputValue.trim(),
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages((prev) => [...prev, newMsg]);
    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSession ? { ...s, lastMessage: inputValue.trim(), lastTime: newMsg.time, status: 'active' as const } : s
      )
    );
    setInputValue('');
  };

  const handleAccept = (sessionId: string) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === sessionId ? { ...s, status: 'active' as const } : s))
    );
    message.success('已接入会话');
  };

  const handleClose = (sessionId: string) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === sessionId ? { ...s, status: 'closed' as const } : s))
    );
    if (activeSession === sessionId) {
      setActiveSession(null);
      setMessages([]);
    }
    message.success('会话已关闭');
  };

  const currentSession = sessions.find((s) => s.id === activeSession);

  const statusTag = (status: string) => {
    const map: Record<string, { color: string; text: string }> = {
      waiting: { color: 'orange', text: '等待中' },
      active: { color: 'green', text: '对话中' },
      closed: { color: 'default', text: '已关闭' },
    };
    const s = map[status] || { color: 'default', text: status };
    return <Tag color={s.color} style={{ fontSize: 11 }}>{s.text}</Tag>;
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>客服工作台</Title>
      <Layout style={{ height: 'calc(100vh - 220px)', borderRadius: 12, overflow: 'hidden', border: '1px solid #f0f0f0' }}>
        <Sider width={300} style={{ background: '#fff', borderRight: '1px solid #f0f0f0', overflow: 'auto' }}>
          <div style={{ padding: '16px', borderBottom: '1px solid #f0f0f0' }}>
            <Space>
              <CustomerServiceOutlined style={{ color: '#52c41a', fontSize: 18 }} />
              <Text strong>会话列表</Text>
              <Badge count={sessions.filter((s) => s.status === 'waiting').length} style={{ backgroundColor: '#faad14' }} />
            </Space>
          </div>
          <List
            dataSource={sessions}
            renderItem={(session) => (
              <List.Item
                key={session.id}
                onClick={() => setActiveSession(session.id)}
                style={{
                  padding: '12px 16px',
                  cursor: 'pointer',
                  backgroundColor: activeSession === session.id ? '#f6ffed' : 'transparent',
                  borderLeft: activeSession === session.id ? '3px solid #52c41a' : '3px solid transparent',
                  transition: 'all 0.2s',
                }}
              >
                <List.Item.Meta
                  avatar={
                    <Badge count={session.unread} size="small">
                      <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#52c41a' }} />
                    </Badge>
                  }
                  title={
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text strong style={{ fontSize: 14 }}>{session.userName}</Text>
                      {statusTag(session.status)}
                    </div>
                  }
                  description={
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }} ellipsis>{session.lastMessage}</Text>
                      <div style={{ fontSize: 11, color: '#bbb', marginTop: 2 }}>{session.lastTime}</div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        </Sider>

        <Content style={{ display: 'flex', flexDirection: 'column', background: '#fafafa' }}>
          {activeSession && currentSession ? (
            <>
              <div style={{ padding: '12px 20px', background: '#fff', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Space>
                  <Text strong>{currentSession.userName}</Text>
                  {statusTag(currentSession.status)}
                </Space>
                <Space>
                  {currentSession.status === 'waiting' && (
                    <Button type="primary" size="small" icon={<CheckCircleOutlined />} onClick={() => handleAccept(currentSession.id)}>
                      接入
                    </Button>
                  )}
                  {currentSession.status !== 'closed' && (
                    <Popconfirm title="确定关闭该会话？" onConfirm={() => handleClose(currentSession.id)}>
                      <Button size="small" danger icon={<CloseCircleOutlined />}>关闭</Button>
                    </Popconfirm>
                  )}
                </Space>
              </div>

              <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    style={{
                      display: 'flex',
                      justifyContent: msg.sender === 'admin' ? 'flex-end' : 'flex-start',
                      marginBottom: 12,
                    }}
                  >
                    <div style={{ maxWidth: '70%' }}>
                      <div style={{ fontSize: 11, color: '#999', marginBottom: 4, textAlign: msg.sender === 'admin' ? 'right' : 'left' }}>
                        {msg.sender === 'admin' ? '客服' : currentSession.userName} · {msg.time}
                      </div>
                      <div
                        style={{
                          padding: '10px 16px',
                          borderRadius: msg.sender === 'admin' ? '12px 12px 4px 12px' : '12px 12px 12px 4px',
                          background: msg.sender === 'admin' ? '#52c41a' : '#fff',
                          color: msg.sender === 'admin' ? '#fff' : '#333',
                          boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                          fontSize: 14,
                          lineHeight: 1.6,
                        }}
                      >
                        {msg.content}
                      </div>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>

              {currentSession.status !== 'closed' && (
                <div style={{ padding: '12px 20px', background: '#fff', borderTop: '1px solid #f0f0f0', display: 'flex', gap: 12 }}>
                  <Input
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onPressEnter={handleSend}
                    placeholder="输入消息..."
                    style={{ borderRadius: 8 }}
                  />
                  <Button type="primary" icon={<SendOutlined />} onClick={handleSend}>发送</Button>
                </div>
              )}
            </>
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Empty description="请选择一个会话" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            </div>
          )}
        </Content>

        {activeSession && currentSession && (
          <Sider width={260} style={{ background: '#fff', borderLeft: '1px solid #f0f0f0', padding: 20, overflow: 'auto' }}>
            <div style={{ textAlign: 'center', marginBottom: 24 }}>
              <Avatar size={64} icon={<UserOutlined />} style={{ backgroundColor: '#52c41a', marginBottom: 12 }} />
              <Title level={5} style={{ margin: 0 }}>{currentSession.userName}</Title>
              <Text type="secondary">{currentSession.userPhone}</Text>
            </div>
            <Descriptions column={1} size="small" style={{ fontSize: 12 }}>
              <Descriptions.Item label="用户ID">{currentSession.userId}</Descriptions.Item>
              <Descriptions.Item label="手机号">{currentSession.userPhone}</Descriptions.Item>
              <Descriptions.Item label="会话状态">{statusTag(currentSession.status)}</Descriptions.Item>
              <Descriptions.Item label="最后消息">{currentSession.lastTime}</Descriptions.Item>
            </Descriptions>
          </Sider>
        )}
      </Layout>
    </div>
  );
}
