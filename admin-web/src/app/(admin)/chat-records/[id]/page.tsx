'use client';

import React, { useEffect, useState } from 'react';
import { Typography, Card, Avatar, Spin, Button, Space, Image, message, Descriptions } from 'antd';
import {
  ArrowLeftOutlined, DownloadOutlined, UserOutlined, RobotOutlined,
  FileOutlined,
} from '@ant-design/icons';
import { get } from '@/lib/api';
import api from '@/lib/api';
import { useRouter, useParams } from 'next/navigation';
import dayjs from 'dayjs';

const { Title, Text } = Typography;

interface ChatMessage {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  message_type: string;
  file_url: string | null;
  image_urls: string[] | null;
  file_urls: string[] | null;
  response_time_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  created_at: string;
}

interface ChatSessionDetail {
  id: number;
  user_id: number;
  user_nickname: string;
  user_avatar: string;
  session_type: string;
  title: string;
  model_name: string;
  message_count: number;
  device_info: string;
  ip_address: string;
  ip_location: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

export default function ChatRecordDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;

  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<ChatSessionDetail | null>(null);

  useEffect(() => {
    const fetchDetail = async () => {
      setLoading(true);
      try {
        const res = await get<ChatSessionDetail>(`/api/admin/chat-sessions/${id}`);
        setDetail(res);
      } catch {
        message.error('获取对话详情失败');
      } finally {
        setLoading(false);
      }
    };
    if (id) fetchDetail();
  }, [id]);

  const handleExport = async (format: 'xlsx' | 'csv') => {
    try {
      const res = await api.get(`/api/admin/chat-sessions/${id}/export`, {
        params: { format },
        responseType: 'blob',
      });
      const blob = new Blob([res.data]);
      const disposition = res.headers['content-disposition'];
      let filename = `chat_${id}.${format}`;
      if (disposition) {
        const match = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';\n]+)/i);
        if (match) filename = decodeURIComponent(match[1]);
      }
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      message.error('导出失败');
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Text type="secondary">未找到对话记录</Text>
        <br />
        <Button style={{ marginTop: 16 }} onClick={() => router.push('/chat-records')}>返回列表</Button>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>对话详情</Title>
        <Space>
          <Button icon={<DownloadOutlined />} onClick={() => handleExport('xlsx')}>导出Excel</Button>
          <Button icon={<DownloadOutlined />} onClick={() => handleExport('csv')}>导出CSV</Button>
          <Button icon={<ArrowLeftOutlined />} onClick={() => router.push('/chat-records')}>返回列表</Button>
        </Space>
      </div>

      <Card style={{ marginBottom: 24, borderRadius: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
          <Avatar src={detail.user_avatar} size={48} icon={<UserOutlined />}>
            {detail.user_nickname?.[0]}
          </Avatar>
          <div>
            <Title level={5} style={{ margin: 0 }}>{detail.user_nickname || '未知用户'}</Title>
            <Text type="secondary">用户ID: {detail.user_id}</Text>
          </div>
        </div>
        <Descriptions column={{ xs: 1, sm: 2, md: 3 }} size="small">
          <Descriptions.Item label="对话时间">
            {dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss')}
          </Descriptions.Item>
          <Descriptions.Item label="AI模型">{detail.model_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="对话轮数">{detail.message_count}</Descriptions.Item>
          <Descriptions.Item label="设备信息">{detail.device_info || '-'}</Descriptions.Item>
          <Descriptions.Item label="IP归属地">
            {detail.ip_location || detail.ip_address || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="对话类型">{detail.session_type || '-'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card style={{ borderRadius: 12 }}>
        <div style={{ maxHeight: 'calc(100vh - 400px)', overflowY: 'auto', padding: '16px 0' }}>
          {detail.messages.map((msg) => {
            const isUser = msg.role === 'user';
            const isSystem = msg.role === 'system';

            if (isSystem) {
              return (
                <div key={msg.id} style={{ textAlign: 'center', margin: '12px 0' }}>
                  <Text type="secondary" style={{ fontSize: 12, background: '#f5f5f5', padding: '4px 12px', borderRadius: 12 }}>
                    {msg.content}
                  </Text>
                </div>
              );
            }

            return (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  justifyContent: isUser ? 'flex-end' : 'flex-start',
                  marginBottom: 20,
                  gap: 10,
                  flexDirection: isUser ? 'row-reverse' : 'row',
                }}
              >
                <Avatar
                  size={36}
                  src={isUser ? detail.user_avatar : undefined}
                  icon={isUser ? <UserOutlined /> : <RobotOutlined />}
                  style={{
                    backgroundColor: isUser ? '#87d068' : '#1677ff',
                    flexShrink: 0,
                  }}
                />
                <div style={{ maxWidth: '70%' }}>
                  <div
                    style={{
                      background: isUser ? '#95ec69' : '#ffffff',
                      border: isUser ? 'none' : '1px solid #e8e8e8',
                      borderRadius: isUser ? '12px 2px 12px 12px' : '2px 12px 12px 12px',
                      padding: '10px 14px',
                      lineHeight: 1.6,
                      wordBreak: 'break-word',
                      whiteSpace: 'pre-wrap',
                      boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
                    }}
                  >
                    {msg.content}
                  </div>

                  {Array.isArray(msg.image_urls) && msg.image_urls.length > 0 && (
                    <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <Image.PreviewGroup>
                        {msg.image_urls.map((url, idx) => (
                          <Image
                            key={idx}
                            src={url}
                            width={120}
                            style={{ borderRadius: 8 }}
                            alt={`图片${idx + 1}`}
                          />
                        ))}
                      </Image.PreviewGroup>
                    </div>
                  )}

                  {Array.isArray(msg.file_urls) && msg.file_urls.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      {msg.file_urls.map((url, idx) => {
                        const fileName = url.split('/').pop() || `文件${idx + 1}`;
                        return (
                          <div key={idx} style={{ marginBottom: 4 }}>
                            <a href={url} target="_blank" rel="noopener noreferrer">
                              <Space size={4}>
                                <FileOutlined />
                                <span>{fileName}</span>
                              </Space>
                            </a>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  <div style={{ marginTop: 4, display: 'flex', gap: 12, alignItems: 'center' }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {dayjs(msg.created_at).format('HH:mm:ss')}
                    </Text>
                    {!isUser && msg.response_time_ms != null && (
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        回复耗时 {msg.response_time_ms}ms
                      </Text>
                    )}
                    {!isUser && (msg.prompt_tokens != null || msg.completion_tokens != null) && (
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        Tokens: {msg.prompt_tokens ?? '-'}/{msg.completion_tokens ?? '-'}
                      </Text>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'center' }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => router.push('/chat-records')}>返回列表</Button>
          <Button icon={<DownloadOutlined />} onClick={() => handleExport('xlsx')}>导出Excel</Button>
          <Button icon={<DownloadOutlined />} onClick={() => handleExport('csv')}>导出CSV</Button>
        </Space>
      </div>
    </div>
  );
}
