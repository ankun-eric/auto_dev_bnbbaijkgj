'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, Input, Button, SpinLoading, Toast } from 'antd-mobile';
import api from '@/lib/api';
import ChatSidebar from '@/components/ChatSidebar';
import KnowledgeCard, { type KnowledgeHit } from '@/components/KnowledgeCard';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  time: string;
  knowledge_hits?: KnowledgeHit[];
}

const welcomeMessage: Message = {
  id: 'welcome',
  role: 'assistant',
  content: '您好！我是宾尼小康AI健康助手。请问您有什么健康问题需要咨询吗？',
  time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
};

export default function ChatPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;
  const [messages, setMessages] = useState<Message[]>([welcomeMessage]);
  const [inputVal, setInputVal] = useState('');
  const [loading, setLoading] = useState(false);
  const [sidebarVisible, setSidebarVisible] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  const loadHistory = useCallback(async () => {
    if (!sessionId || isNaN(Number(sessionId))) return;
    try {
      const res: any = await api.get(`/api/chat/sessions/${sessionId}/messages`, {
        params: { page: 1, page_size: 50 },
      });
      const data = res.data || res;
      const items = data.items || [];
      if (items.length > 0) {
        const historyMsgs: Message[] = items.map((m: any) => ({
          id: String(m.id),
          role: m.role as 'user' | 'assistant',
          content: m.content,
          time: new Date(m.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        }));
        setMessages([welcomeMessage, ...historyMsgs]);
      }
    } catch {
      // first time entering, no history yet
    }
  }, [sessionId]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  };

  const handleKnowledgeFeedback = async (hitLogId: number, feedback: 'like' | 'dislike') => {
    try {
      await api.post('/api/chat/feedback', { hit_log_id: hitLogId, feedback });
      Toast.show({ content: '感谢反馈', icon: 'success' });
    } catch {
      Toast.show({ content: '反馈失败，请稍后重试', icon: 'fail' });
      throw new Error('feedback failed');
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
        id: resData.id != null ? String(resData.id) : `ai-${Date.now()}`,
        role: 'assistant',
        content: resData.content || '抱歉，我暂时无法回答这个问题。请稍后重试。',
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        knowledge_hits: Array.isArray(resData.knowledge_hits) ? resData.knowledge_hits : undefined,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      let errorContent = '网络连接异常，请检查网络后重试。';
      const status = err?.response?.status;
      if (status === 401) {
        errorContent = '登录已过期，请重新登录。';
      } else if (status === 404) {
        errorContent = '会话不存在，请返回重新创建对话。';
      } else if (status === 422) {
        errorContent = '请求参数异常，请返回重新创建对话。';
      }
      const fallbackMsg: Message = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: errorContent,
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, fallbackMsg]);
    }
    setLoading(false);
  };

  const renderMarkdownBlock = (text: string) => {
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

  const renderMarkdown = (text: string) => {
    const parts = text.split('---disclaimer---');
    return (
      <>
        <div>{renderMarkdownBlock(parts[0])}</div>
        {parts[1] && (
          <div style={{
            marginTop: 8,
            paddingTop: 8,
            borderTop: '1px dashed #e8e8e8',
            fontSize: 11,
            color: '#999',
            fontStyle: 'italic',
            lineHeight: 1.4,
          }}>
            {parts[1].trim()}
          </div>
        )}
      </>
    );
  };

  const handleSessionCreated = (newSessionId: number) => {
    router.push(`/chat/${newSessionId}`);
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <NavBar
        onBack={() => router.back()}
        left={
          <button
            onClick={(e) => {
              e.stopPropagation();
              setSidebarVisible(true);
            }}
            className="w-8 h-8 flex items-center justify-center rounded-lg -ml-1"
            style={{ background: 'rgba(255,255,255,0.2)' }}
            aria-label="打开历史对话"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        }
        style={{
          '--height': '48px',
          background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
          color: '#fff',
          '--border-bottom': 'none',
        } as React.CSSProperties}
      >
        <span className="text-white font-medium">AI健康咨询</span>
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
              {msg.role === 'assistant' && msg.knowledge_hits && msg.knowledge_hits.length > 0 ? (
                <div className="mt-2 space-y-2 w-full">
                  {msg.knowledge_hits.map((hit, idx) => (
                    <KnowledgeCard
                      key={`${msg.id}-kb-${idx}`}
                      hit={hit}
                      hitLogId={hit.hit_log_id}
                      onFeedback={handleKnowledgeFeedback}
                    />
                  ))}
                </div>
              ) : null}
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

      <ChatSidebar
        visible={sidebarVisible}
        onClose={() => setSidebarVisible(false)}
        currentSessionId={sessionId}
        onSessionCreated={handleSessionCreated}
      />
    </div>
  );
}
