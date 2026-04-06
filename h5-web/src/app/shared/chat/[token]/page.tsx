'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import { SpinLoading } from 'antd-mobile';
import axios from 'axios';

interface SharedMessage {
  role: 'user' | 'assistant';
  content: string;
  message_type: string;
  file_url?: string;
  image_urls?: string[];
  file_urls?: string[];
  created_at: string;
}

interface SharedChat {
  title: string;
  session_type: string;
  message_count: number;
  created_at: string;
  messages: SharedMessage[];
}

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export default function SharedChatPage() {
  const params = useParams();
  const token = params.token as string;
  const [chat, setChat] = useState<SharedChat | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!token) return;
    const fetchSharedChat = async () => {
      setLoading(true);
      try {
        const res = await axios.get(`${basePath}/api/shared/chat/${token}`);
        const data = res.data;
        setChat(data);
      } catch (err: any) {
        if (err?.response?.status === 404) {
          setError('该分享链接不存在或已过期');
        } else {
          setError('加载失败，请稍后重试');
        }
      } finally {
        setLoading(false);
      }
    };
    fetchSharedChat();
  }, [token]);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [chat]);

  const renderMarkdown = (text: string) => {
    const lines = text.split('\n');
    return lines.map((line, i) => {
      const boldLine = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      return (
        <p
          key={i}
          className="mb-1 last:mb-0"
          dangerouslySetInnerHTML={{ __html: boldLine }}
        />
      );
    });
  };

  const renderImages = (urls: string[]) => (
    <div className="flex flex-wrap gap-2 mt-2">
      {urls.map((url, i) => (
        <img
          key={i}
          src={url}
          alt=""
          className="rounded-lg max-w-[200px] max-h-[200px] object-cover"
          loading="lazy"
        />
      ))}
    </div>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <SpinLoading style={{ '--size': '36px', '--color': '#52c41a' }} />
          <p className="text-sm text-gray-400 mt-4">加载中...</p>
        </div>
      </div>
    );
  }

  if (error || !chat) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center px-6">
          <div className="text-5xl mb-4">😔</div>
          <p className="text-base text-gray-500">{error || '加载失败'}</p>
          <p className="text-xs text-gray-300 mt-3">请检查链接是否正确</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      {/* Header */}
      <div
        className="flex-shrink-0 px-4 py-4"
        style={{
          background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ background: 'rgba(255,255,255,0.2)' }}
          >
            <span className="text-white text-sm font-bold">AI</span>
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-white font-bold text-base truncate">{chat.title}</h1>
            <p className="text-white/70 text-xs mt-0.5">
              {chat.message_count}条消息 · {new Date(chat.created_at).toLocaleDateString('zh-CN')}
            </p>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3">
        {chat.messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex mb-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'assistant' && (
              <div
                className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mr-2"
                style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
              >
                <span className="text-white text-xs">AI</span>
              </div>
            )}
            <div className="max-w-[75%]">
              <div
                className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'rounded-tr-sm text-white'
                    : 'bg-white text-gray-700 rounded-tl-sm shadow-sm'
                }`}
                style={
                  msg.role === 'user'
                    ? { background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }
                    : undefined
                }
              >
                {msg.role === 'assistant' ? renderMarkdown(msg.content) : msg.content}
                {msg.image_urls && msg.image_urls.length > 0 && renderImages(msg.image_urls)}
              </div>
              <div
                className={`text-xs text-gray-300 mt-1 ${
                  msg.role === 'user' ? 'text-right' : 'text-left'
                }`}
              >
                {new Date(msg.created_at).toLocaleTimeString('zh-CN', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </div>
            </div>
            {msg.role === 'user' && (
              <div
                className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center ml-2"
                style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
              >
                <span className="text-white text-xs">用户</span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Brand footer */}
      <div className="flex-shrink-0 border-t border-gray-100 bg-white px-4 py-4 text-center">
        <div className="flex items-center justify-center gap-2">
          <span className="text-lg">🌿</span>
          <span
            className="font-bold text-sm"
            style={{
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            宾尼小康 AI健康管家
          </span>
        </div>
        <p className="text-[11px] text-gray-300 mt-1">
          此为分享内容，仅供参考，不构成医疗建议
        </p>
      </div>
    </div>
  );
}
