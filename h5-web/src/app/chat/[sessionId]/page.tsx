'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, Input, Button, SpinLoading, Image } from 'antd-mobile';
import api from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  time: string;
}

const mockMessages: Message[] = [
  {
    id: '1',
    role: 'assistant',
    content: '您好！我是宾尼小康AI健康助手。请问您有什么健康问题需要咨询吗？',
    time: '14:30',
  },
];

export default function ChatPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;
  const [messages, setMessages] = useState<Message[]>(mockMessages);
  const [inputVal, setInputVal] = useState('');
  const [loading, setLoading] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  };

  const sendMessage = async () => {
    const text = inputVal.trim();
    if (!text || loading) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputVal('');
    setLoading(true);

    try {
      const res: any = await api.post(`/api/chat/sessions/${sessionId}/messages`, {
        content: text,
        message_type: 'text',
      });
      const resData = res.data || res;
      const aiMsg: Message = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: resData.content || '抱歉，我暂时无法回答这个问题。请稍后重试。',
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      const fallbackMsg: Message = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: '网络连接异常，请检查网络后重试。您也可以尝试描述更多症状细节，以便我更好地为您分析。',
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, fallbackMsg]);
    }
    setLoading(false);
  };

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

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <NavBar
        onBack={() => router.back()}
        style={{
          '--height': '48px',
          background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
          color: '#fff',
          '--border-bottom': 'none',
        } as React.CSSProperties}
      >
        <span className="text-white font-medium">AI健康助手</span>
      </NavBar>

      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex mb-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mr-2"
                style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
                <span className="text-white text-xs">AI</span>
              </div>
            )}
            <div className="max-w-[75%]">
              <div
                className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-primary text-white rounded-tr-sm'
                    : 'bg-white text-gray-700 rounded-tl-sm shadow-sm'
                }`}
              >
                {msg.role === 'assistant' ? renderMarkdown(msg.content) : msg.content}
              </div>
              <div
                className={`text-xs text-gray-300 mt-1 ${
                  msg.role === 'user' ? 'text-right' : 'text-left'
                }`}
              >
                {msg.time}
              </div>
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-primary flex-shrink-0 flex items-center justify-center ml-2">
                <span className="text-white text-xs">我</span>
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-center mb-4">
            <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mr-2"
              style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
              <span className="text-white text-xs">AI</span>
            </div>
            <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
              <SpinLoading style={{ '--size': '20px', '--color': '#52c41a' }} />
            </div>
          </div>
        )}
      </div>

      <div className="bg-white border-t border-gray-100 px-4 py-3 flex items-end gap-2 safe-area-bottom">
        <div className="flex-1 bg-gray-50 rounded-2xl px-4 py-2">
          <Input
            placeholder="输入您的健康问题..."
            value={inputVal}
            onChange={setInputVal}
            onEnterPress={sendMessage}
            style={{ '--font-size': '14px' }}
          />
        </div>
        <Button
          onClick={sendMessage}
          disabled={!inputVal.trim() || loading}
          style={{
            background: inputVal.trim() ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#e8e8e8',
            color: inputVal.trim() ? '#fff' : '#999',
            border: 'none',
            borderRadius: '50%',
            width: 40,
            height: 40,
            padding: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          ➤
        </Button>
      </div>
    </div>
  );
}
