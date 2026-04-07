'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, TextArea, Button, SpinLoading, Toast, ImageViewer } from 'antd-mobile';
import api from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  image_urls?: string[];
  time: string;
  created_at?: string;
}

const welcomeMessage: Message = {
  id: 'welcome',
  role: 'assistant',
  content: '您好！我是宾尼小康AI用药助手。我已收到您的药品图片，正在为您分析用药信息。如有其他问题，请随时提问。',
  time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
};

function formatMsgTime(dateStr?: string) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function DrugChatPage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [messages, setMessages] = useState<Message[]>([welcomeMessage]);
  const [inputVal, setInputVal] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [imageViewerVisible, setImageViewerVisible] = useState(false);
  const [viewerImages, setViewerImages] = useState<string[]>([]);

  const listRef = useRef<HTMLDivElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const albumRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      if (listRef.current) {
        listRef.current.scrollTop = listRef.current.scrollHeight;
      }
    });
  }, []);

  const loadHistory = useCallback(async () => {
    if (!sessionId) return;
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
          image_urls: m.image_urls,
          time: formatMsgTime(m.created_at) || new Date(m.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
          created_at: m.created_at,
        }));
        setMessages([welcomeMessage, ...historyMsgs]);
      }
    } catch {
      // first time, no history
    }
  }, [sessionId]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

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
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      let errorContent = '网络连接异常，请检查网络后重试。';
      const status = err?.response?.status;
      if (status === 401) errorContent = '登录已过期，请重新登录。';
      else if (status === 404) errorContent = '会话不存在，请返回重新创建对话。';
      else if (status === 422) errorContent = '请求参数异常，请返回重新创建对话。';

      setMessages((prev) => [
        ...prev,
        {
          id: `ai-${Date.now()}`,
          role: 'assistant',
          content: errorContent,
          time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    }
    setLoading(false);
  };

  const handlePhotoFile = async (file: File | undefined) => {
    if (!file || uploading) return;
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('scene_name', '拍照识药');
      const ocrRes: any = await api.post('/api/ocr/recognize', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });
      const ocrData = ocrRes.data || ocrRes;

      const drugName = ocrData.drug_name || ocrData.result?.drug_name || '药品';
      const content = `请分析这个新药品：${drugName}，并与之前的药品进行对比`;

      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: 'user',
        content,
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);

      const res: any = await api.post(`/api/chat/sessions/${sessionId}/messages`, {
        content,
        message_type: 'text',
      });
      const resData = res.data || res;
      const aiMsg: Message = {
        id: resData.id != null ? String(resData.id) : `ai-${Date.now()}`,
        role: 'assistant',
        content: resData.content || '药品识别完成，请查看分析结果。',
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      Toast.show({ content: '识别失败，请重试', icon: 'fail' });
    } finally {
      setUploading(false);
      setLoading(false);
      if (cameraRef.current) cameraRef.current.value = '';
      if (albumRef.current) albumRef.current.value = '';
    }
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
          <div
            style={{
              marginTop: 8,
              paddingTop: 8,
              borderTop: '1px dashed #e8e8e8',
              fontSize: 11,
              color: '#999',
              fontStyle: 'italic',
              lineHeight: 1.4,
            }}
          >
            {parts[1].trim()}
          </div>
        )}
      </>
    );
  };

  const openImageViewer = (urls: string[]) => {
    setViewerImages(urls);
    setImageViewerVisible(true);
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <NavBar
        onBack={() => router.push('/drug')}
        style={{
          '--height': '48px',
          background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
          color: '#fff',
          '--border-bottom': 'none',
        } as React.CSSProperties}
      >
        <span className="text-white font-medium">用药咨询</span>
      </NavBar>

      {/* Hidden file inputs */}
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => handlePhotoFile(e.target.files?.[0])}
      />
      <input
        ref={albumRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => handlePhotoFile(e.target.files?.[0])}
      />

      {/* Upload overlay */}
      {uploading && (
        <div className="fixed inset-0 z-50 bg-black/50 flex flex-col items-center justify-center">
          <SpinLoading style={{ '--size': '48px', '--color': '#52c41a' }} />
          <span className="text-white text-base mt-4 font-medium">AI识别中...</span>
        </div>
      )}

      {/* Messages */}
      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3">
        {messages.map((msg) => (
          <div
            key={msg.id}
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
            <div className="max-w-[80%]">
              {/* Image thumbnails */}
              {msg.image_urls && msg.image_urls.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-2">
                  {msg.image_urls.map((url, idx) => (
                    <img
                      key={idx}
                      src={url}
                      alt="药品图片"
                      className="w-20 h-20 rounded-lg object-cover cursor-pointer"
                      onClick={() => openImageViewer(msg.image_urls!)}
                    />
                  ))}
                </div>
              )}

              {/* Message bubble */}
              <div
                className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'text-white rounded-tr-sm'
                    : 'bg-[#f5f5f5] text-gray-700 rounded-tl-sm'
                }`}
                style={
                  msg.role === 'user'
                    ? { background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }
                    : undefined
                }
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
            <div
              className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mr-2"
              style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
            >
              <span className="text-white text-xs">AI</span>
            </div>
            <div className="bg-[#f5f5f5] rounded-2xl rounded-tl-sm px-4 py-3">
              <SpinLoading style={{ '--size': '20px', '--color': '#52c41a' }} />
            </div>
          </div>
        )}
      </div>

      {/* Bottom input area */}
      <div className="bg-white border-t border-gray-100 px-4 py-3 safe-area-bottom">
        <div className="flex items-end gap-2">
          {/* Camera button */}
          <button
            onClick={() => cameraRef.current?.click()}
            disabled={uploading || loading}
            className="w-10 h-10 flex-shrink-0 rounded-full flex items-center justify-center"
            style={{
              background: '#f5f5f5',
              opacity: uploading || loading ? 0.5 : 1,
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#52c41a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
              <circle cx="12" cy="13" r="4" />
            </svg>
          </button>

          {/* Album button */}
          <button
            onClick={() => albumRef.current?.click()}
            disabled={uploading || loading}
            className="w-10 h-10 flex-shrink-0 rounded-full flex items-center justify-center"
            style={{
              background: '#f5f5f5',
              opacity: uploading || loading ? 0.5 : 1,
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#52c41a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
          </button>

          {/* Text input */}
          <div className="flex-1 bg-gray-50 rounded-2xl px-4 py-2">
            <TextArea
              placeholder="输入用药问题..."
              value={inputVal}
              onChange={setInputVal}
              autoSize={{ minRows: 1, maxRows: 3 }}
              style={{ '--font-size': '14px' } as React.CSSProperties}
            />
          </div>

          {/* Send button */}
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
              flexShrink: 0,
            }}
          >
            ➤
          </Button>
        </div>
      </div>

      {/* Image viewer */}
      <ImageViewer.Multi
        images={viewerImages}
        visible={imageViewerVisible}
        defaultIndex={0}
        onClose={() => setImageViewerVisible(false)}
      />
    </div>
  );
}
