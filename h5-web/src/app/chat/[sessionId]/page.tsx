'use client';

import { useState, useRef, useEffect, useCallback, Suspense } from 'react';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import { NavBar, Input, Button, SpinLoading, Toast, Popup, Tag } from 'antd-mobile';
import api from '@/lib/api';
import { useAuth } from '@/lib/auth';
import ChatSidebar from '@/components/ChatSidebar';
import KnowledgeCard, { type KnowledgeHit } from '@/components/KnowledgeCard';

type FontSizeLevel = 'standard' | 'large' | 'extra_large';

const FONT_SIZE_MAP: Record<FontSizeLevel, number> = {
  standard: 14,
  large: 18,
  extra_large: 22,
};

const FONT_LABEL_MAP: Record<FontSizeLevel, string> = {
  standard: '标准（14px）',
  large: '大（18px）',
  extra_large: '超大（22px）',
};

const FONT_TOAST_MAP: Record<FontSizeLevel, string> = {
  standard: '已切换为标准字体',
  large: '已切换为大字体',
  extra_large: '已切换为超大字体',
};

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  time: string;
  knowledge_hits?: KnowledgeHit[];
}

interface FamilyMember {
  id: number;
  nickname: string;
  relationship_type: string;
}

const relationshipLabelMap: Record<string, string> = {
  father: '父亲',
  mother: '母亲',
  spouse: '配偶',
  child: '子女',
  sibling: '兄弟姐妹',
  grandparent: '祖父母',
  maternal_grandparent: '外祖父母',
  other: '其他',
};

const welcomeMessage: Message = {
  id: 'welcome',
  role: 'assistant',
  content: '您好！我是宾尼小康AI健康助手。请问您有什么健康问题需要咨询吗？',
  time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
};

function ChatPageInner() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const sessionId = params.sessionId as string;
  const { isLoggedIn } = useAuth();

  const urlType = searchParams.get('type') || '';
  const urlMsg = searchParams.get('msg') || '';
  const urlMember = searchParams.get('member') || '';
  const isSymptom = urlType === 'symptom';

  const [messages, setMessages] = useState<Message[]>([welcomeMessage]);
  const [inputVal, setInputVal] = useState('');
  const [loading, setLoading] = useState(false);
  const [sidebarVisible, setSidebarVisible] = useState(false);

  // Font size state
  const [fontSizeLevel, setFontSizeLevel] = useState<FontSizeLevel>('standard');
  const [fontPopoverVisible, setFontPopoverVisible] = useState(false);
  const fontBtnRef = useRef<HTMLButtonElement>(null);
  const fontPopoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isLoggedIn) return;
    api.get('/api/user/font-setting')
      .then((res: any) => {
        const data = res.data || res;
        const level = data.font_size_level;
        if (level && FONT_SIZE_MAP[level as FontSizeLevel] !== undefined) {
          setFontSizeLevel(level as FontSizeLevel);
        }
      })
      .catch(() => {});
  }, [isLoggedIn]);

  useEffect(() => {
    if (!fontPopoverVisible) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (
        fontPopoverRef.current && !fontPopoverRef.current.contains(e.target as Node) &&
        fontBtnRef.current && !fontBtnRef.current.contains(e.target as Node)
      ) {
        setFontPopoverVisible(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside as any);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside as any);
    };
  }, [fontPopoverVisible]);

  const handleFontChange = (level: FontSizeLevel) => {
    setFontSizeLevel(level);
    setFontPopoverVisible(false);
    Toast.show({ content: FONT_TOAST_MAP[level], duration: 1500 });
    if (isLoggedIn) {
      api.put('/api/user/font-setting', { font_size_level: level }).catch(() => {
        Toast.show({ content: '保存失败，请稍后重试', icon: 'fail', duration: 1500 });
      });
    }
  };

  const chatFontSize = FONT_SIZE_MAP[fontSizeLevel];

  // Symptom banner
  const [bannerExpanded, setBannerExpanded] = useState(true);
  const [firstCardExpanded, setFirstCardExpanded] = useState(false);
  const autoSentRef = useRef(false);
  const firstUserMsgIdRef = useRef<string | null>(null);

  // Switch member popup
  const [memberPopupVisible, setMemberPopupVisible] = useState(false);
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([]);
  const [switchingMember, setSwitchingMember] = useState(false);

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

  // Auto-send symptom message after history loads
  useEffect(() => {
    if (!isSymptom || !urlMsg || autoSentRef.current) return;
    const timer = setTimeout(() => {
      if (autoSentRef.current) return;
      autoSentRef.current = true;
      sendMessageText(urlMsg);
    }, 300);
    return () => clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSymptom, urlMsg]);

  // Collapse banner after AI first reply
  useEffect(() => {
    if (!isSymptom) return;
    const aiReplies = messages.filter((m) => m.role === 'assistant' && m.id !== 'welcome');
    if (aiReplies.length > 0 && bannerExpanded) {
      setBannerExpanded(false);
    }
  }, [messages, isSymptom]);

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

  const sendMessageText = async (text: string) => {
    if (!text || loading) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    };

    if (firstUserMsgIdRef.current === null) {
      firstUserMsgIdRef.current = userMsg.id;
    }

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

  const sendMessage = async () => {
    const text = inputVal.trim();
    if (!text || loading) return;
    await sendMessageText(text);
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
    const disclaimerSize = Math.max(chatFontSize - 3, 11);
    return (
      <>
        <div>{renderMarkdownBlock(parts[0])}</div>
        {parts[1] && (
          <div style={{
            marginTop: 8,
            paddingTop: 8,
            borderTop: '1px dashed #e8e8e8',
            fontSize: disclaimerSize,
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

  const openMemberPopup = async () => {
    try {
      const res: any = await api.get('/api/family/members');
      const data = res.data || res;
      setFamilyMembers(Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : []);
    } catch {
      setFamilyMembers([]);
    }
    setMemberPopupVisible(true);
  };

  const handleSwitchMember = async (memberId: number | null, label: string) => {
    setSwitchingMember(true);
    try {
      await api.post(`/api/chat/sessions/${sessionId}/switch-member`, {
        family_member_id: memberId,
      });
      setMemberPopupVisible(false);
      Toast.show({
        content: `已切换为${label}，后续AI回复将基于新的档案`,
        icon: 'success',
        duration: 2500,
      });
    } catch {
      Toast.show({ content: '切换失败，请稍后重试', icon: 'fail' });
    }
    setSwitchingMember(false);
  };

  // Determine if a message is the first user message (for symptom card rendering)
  const isFirstUserMsg = (msg: Message): boolean => {
    if (!isSymptom) return false;
    const userMsgs = messages.filter((m) => m.role === 'user');
    return userMsgs.length > 0 && userMsgs[0].id === msg.id;
  };

  const bannerText = urlMsg.slice(0, 50) + (urlMsg.length > 50 ? '...' : '');

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
        right={
          isLoggedIn ? (
            <div style={{ position: 'relative' }}>
              <button
                ref={fontBtnRef}
                onClick={(e) => {
                  e.stopPropagation();
                  setFontPopoverVisible((v) => !v);
                }}
                className="w-8 h-8 flex items-center justify-center rounded-lg"
                style={{ background: 'rgba(255,255,255,0.2)' }}
                aria-label="字体大小设置"
              >
                <span className="text-white text-sm font-bold">Aa</span>
              </button>
              {fontPopoverVisible && (
                <div
                  ref={fontPopoverRef}
                  style={{
                    position: 'absolute',
                    top: '100%',
                    right: 0,
                    marginTop: 8,
                    width: 120,
                    background: '#fff',
                    borderRadius: 8,
                    boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
                    zIndex: 100,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      position: 'absolute',
                      top: -6,
                      right: 12,
                      width: 12,
                      height: 12,
                      background: '#fff',
                      transform: 'rotate(45deg)',
                      boxShadow: '-2px -2px 4px rgba(0,0,0,0.04)',
                    }}
                  />
                  {(['standard', 'large', 'extra_large'] as FontSizeLevel[]).map((level) => {
                    const isActive = fontSizeLevel === level;
                    return (
                      <div
                        key={level}
                        onClick={() => handleFontChange(level)}
                        style={{
                          padding: '10px 12px',
                          fontSize: 13,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          background: isActive ? '#f6ffed' : '#fff',
                          color: isActive ? '#52c41a' : '#333',
                          fontWeight: isActive ? 600 : 400,
                        }}
                      >
                        <span>{FONT_LABEL_MAP[level]}</span>
                        {isActive && <span style={{ color: '#52c41a', fontSize: 14 }}>✓</span>}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : null
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

      {/* Symptom banner */}
      {isSymptom && urlMsg && (
        <div
          className="mx-3 mt-2 rounded-xl px-3 py-2 cursor-pointer flex items-start gap-2"
          style={{ background: '#f6ffed', border: '1px solid #b7eb8f' }}
          onClick={() => setBannerExpanded((v) => !v)}
        >
          <span style={{ color: '#52c41a', fontSize: 15, flexShrink: 0, marginTop: 1 }}>✚</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-1">
              <span className="text-xs font-medium" style={{ color: '#52c41a' }}>健康自查</span>
              {urlMember && (
                <span className="text-xs" style={{ color: '#87d068' }}>
                  咨询对象：{urlMember}
                </span>
              )}
              <span className="text-xs" style={{ color: '#52c41a', flexShrink: 0 }}>
                {bannerExpanded ? '▲' : '▼'}
              </span>
            </div>
            <div
              className="text-xs mt-1"
              style={{
                color: '#555',
                overflow: 'hidden',
                maxHeight: bannerExpanded ? 'none' : '1.5em',
                whiteSpace: bannerExpanded ? 'normal' : 'nowrap',
                textOverflow: bannerExpanded ? 'unset' : 'ellipsis',
              }}
            >
              {bannerText}
            </div>
          </div>
        </div>
      )}

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
              {/* Symptom card for first user message */}
              {msg.role === 'user' && isFirstUserMsg(msg) ? (
                <div
                  className="rounded-2xl rounded-tr-sm px-4 py-3 leading-relaxed cursor-pointer"
                  style={{ background: '#f6ffed', border: '1.5px solid #52c41a', fontSize: chatFontSize }}
                  onClick={() => setFirstCardExpanded((v) => !v)}
                >
                  <div className="flex items-center gap-1 mb-2">
                    <span style={{ color: '#52c41a', fontSize: 14 }}>✚</span>
                    <span className="font-semibold text-xs" style={{ color: '#52c41a' }}>健康自查摘要</span>
                    <span className="ml-auto text-xs" style={{ color: '#52c41a' }}>
                      {firstCardExpanded ? '▲' : '▼'}
                    </span>
                  </div>
                  <div
                    style={{
                      color: '#444',
                      overflow: 'hidden',
                      maxHeight: firstCardExpanded ? 'none' : '1.6em',
                      whiteSpace: firstCardExpanded ? 'normal' : 'nowrap',
                      textOverflow: firstCardExpanded ? 'unset' : 'ellipsis',
                    }}
                  >
                    {msg.content}
                  </div>
                </div>
              ) : (
                <div
                  className={`rounded-2xl px-4 py-3 leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-primary text-white rounded-tr-sm'
                      : 'bg-white text-gray-700 rounded-tl-sm shadow-sm'
                  }`}
                  style={{ fontSize: chatFontSize }}
                >
                  {msg.role === 'assistant' ? renderMarkdown(msg.content) : msg.content}
                </div>
              )}
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

      <div className="bg-white border-t border-gray-100 px-3 py-3 flex items-end gap-2 safe-area-bottom">
        {/* Switch member button */}
        <button
          onClick={openMemberPopup}
          className="w-10 h-10 flex-shrink-0 flex items-center justify-center rounded-full"
          style={{ background: '#f0fff0', border: '1px solid #b7eb8f' }}
          aria-label="切换咨询对象"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#52c41a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
          </svg>
        </button>

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

      {/* Switch member popup */}
      <Popup
        visible={memberPopupVisible}
        onMaskClick={() => setMemberPopupVisible(false)}
        position="bottom"
        bodyStyle={{ borderRadius: '16px 16px 0 0', maxHeight: '70vh', overflowY: 'auto' }}
      >
        <div className="px-4 pb-6">
          <div className="flex items-center justify-between py-4 border-b border-gray-100">
            <span className="text-base font-semibold">切换咨询对象</span>
            <button
              onClick={() => setMemberPopupVisible(false)}
              className="text-gray-400 text-xl leading-none"
            >
              ×
            </button>
          </div>

          <div className="mt-3 space-y-2">
            <div
              className="flex items-center gap-3 px-3 py-3 rounded-xl cursor-pointer"
              style={{ background: '#f9f9f9' }}
              onClick={() => handleSwitchMember(null, '自己')}
            >
              <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm"
                style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
                我
              </div>
              <span className="text-sm font-medium">为自己</span>
            </div>

            {familyMembers.map((m) => (
              <div
                key={m.id}
                className="flex items-center gap-3 px-3 py-3 rounded-xl cursor-pointer"
                style={{ background: '#f9f9f9' }}
                onClick={() => {
                  const label = `${relationshipLabelMap[m.relationship_type] || m.relationship_type}·${m.nickname}`;
                  handleSwitchMember(m.id, label);
                }}
              >
                <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm"
                  style={{ background: '#87d068' }}>
                  {m.nickname.charAt(0)}
                </div>
                <div>
                  <div className="text-sm font-medium">{m.nickname}</div>
                  <div className="text-xs text-gray-400">
                    {relationshipLabelMap[m.relationship_type] || m.relationship_type}
                  </div>
                </div>
              </div>
            ))}

            <div
              className="flex items-center gap-3 px-3 py-3 rounded-xl cursor-pointer"
              style={{ background: '#f9f9f9' }}
              onClick={() => {
                setMemberPopupVisible(false);
                router.push('/family/add');
              }}
            >
              <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-lg"
                style={{ background: '#52c41a' }}>
                +
              </div>
              <span className="text-sm font-medium" style={{ color: '#52c41a' }}>新建家庭成员</span>
            </div>
          </div>
        </div>
      </Popup>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen"><SpinLoading /></div>}>
      <ChatPageInner />
    </Suspense>
  );
}
