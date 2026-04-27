'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Input, Toast, SpinLoading, Swiper } from 'antd-mobile';
import { THEME } from '@/lib/theme';
import api from '@/lib/api';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/ai-chat/Sidebar';
import MoreMenu from '@/components/ai-chat/MoreMenu';
import ConsultantPicker from '@/components/ai-chat/ConsultantPicker';
import RecommendCards from '@/components/ai-chat/RecommendCards';
import SharePanel from '@/components/ai-chat/SharePanel';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  time: string;
}

interface Banner {
  id: number;
  image_url: string;
  link_url?: string;
  title?: string;
}

interface FunctionButton {
  id: string;
  name: string;
  icon?: string;
  button_type: string;
  params?: Record<string, any>;
}

interface FamilyMember {
  id: number;
  nickname: string;
  relationship_type: string;
  relation_type_name: string;
  avatar?: string;
  is_self: boolean;
}

const FUNCTION_ROUTES: Record<string, string> = {
  'view_report': '/checkup',
  'check_drug': '/drug',
  'view_archive': '/health-archive',
  'check_order': '/unified-orders',
  'find_expert': '/service',
  'find_service': '/service',
};

const FUNCTION_ICONS: Record<string, string> = {
  'view_report': '📋',
  'check_drug': '💊',
  'view_archive': '📁',
  'check_order': '📦',
  'find_expert': '👨‍⚕️',
  'find_service': '🏥',
};

const DIALOG_TRIGGERS = new Set(['view_report', 'check_drug']);

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 6) return '夜深了，注意休息';
  if (h < 9) return '早上好';
  if (h < 12) return '上午好';
  if (h < 14) return '中午好';
  if (h < 18) return '下午好';
  return '晚上好';
}

export default function AiHomePage() {
  const router = useRouter();
  const { user } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [consultantOpen, setConsultantOpen] = useState(false);

  const [banners, setBanners] = useState<Banner[]>([]);
  const [funcButtons, setFuncButtons] = useState<FunctionButton[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [inputFocused, setInputFocused] = useState(false);
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [hasHealthTask, setHasHealthTask] = useState(false);
  const [selectedConsultant, setSelectedConsultant] = useState<FamilyMember | null>(null);

  const [recommendQuestions, setRecommendQuestions] = useState<{ tag: string; text: string }[]>([
    { tag: '健康', text: '最近总是失眠怎么办？' },
    { tag: '体检', text: '帮我解读最新体检报告' },
    { tag: '用药', text: '感冒了吃什么药比较好？' },
    { tag: '饮食', text: '高血压患者饮食注意什么？' },
  ]);

  useEffect(() => {
    api.get('/api/h5/home-banners').then((res: any) => {
      const data = res.data || res;
      setBanners(Array.isArray(data.items) ? data.items : []);
    }).catch(() => {});

    api.get('/api/function-buttons').then((res: any) => {
      const data = res.data || res;
      setFuncButtons(Array.isArray(data.items) ? data.items : []);
    }).catch(() => {});

    api.get('/api/health-plan/today-tasks').then((res: any) => {
      const data = res.data || res;
      setHasHealthTask(!!data.has_tasks);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(async (text?: string) => {
    const msg = text || inputValue.trim();
    if (!msg || sending) return;

    setInputValue('');
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: msg,
      time: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);
    setSending(true);

    try {
      const body: any = { message: msg };
      if (sessionId) body.session_id = sessionId;
      if (selectedConsultant) body.member_id = selectedConsultant.id;

      const res: any = await api.post('/api/ai/chat', body);
      const data = res.data || res;
      if (data.session_id) setSessionId(data.session_id);

      const aiMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: data.reply || data.message || '抱歉，我暂时无法回复',
        time: new Date().toISOString(),
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch {
      const errMsg: ChatMessage = {
        id: `e-${Date.now()}`,
        role: 'assistant',
        content: '网络异常，请稍后重试',
        time: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errMsg]);
    }
    setSending(false);
  }, [inputValue, sending, sessionId, selectedConsultant]);

  const handleFuncButton = (btn: FunctionButton) => {
    const key = btn.button_type || btn.id;
    if (DIALOG_TRIGGERS.has(key)) {
      const route = FUNCTION_ROUTES[key] || '/';
      const cardMsg: ChatMessage = {
        id: `c-${Date.now()}`,
        role: 'assistant',
        content: `💡 点击前往${btn.name}：${route}`,
        time: new Date().toISOString(),
      };
      setMessages(prev => [...prev, cardMsg]);
    } else {
      const route = FUNCTION_ROUTES[key];
      if (route) router.push(route);
    }
  };

  const hasConversation = messages.length > 0;

  return (
    <div className="flex flex-col h-screen" style={{ background: THEME.background, maxWidth: 750, margin: '0 auto' }}>
      {/* Top Bar */}
      <div
        className="flex items-center justify-between px-4 flex-shrink-0"
        style={{ height: 48, background: THEME.cardBg, borderBottom: `1px solid ${THEME.divider}` }}
      >
        <div className="flex items-center gap-3">
          <button className="text-xl" onClick={() => setSidebarOpen(true)}>☰</button>
          <span className="font-bold text-base" style={{ color: THEME.textPrimary }}>小康</span>
        </div>
        <button className="text-xl tracking-widest" onClick={() => setMoreMenuOpen(true)}>···</button>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        {!hasConversation ? (
          /* Welcome State */
          <div className="px-4 py-6">
            {/* Logo + Greeting */}
            <div className="flex flex-col items-center py-6">
              <div
                className="flex items-center justify-center rounded-full text-3xl mb-3"
                style={{ width: 64, height: 64, background: THEME.gradient, color: '#fff' }}
              >
                🌿
              </div>
              <div className="text-lg font-bold" style={{ color: THEME.textPrimary }}>
                {getGreeting()}，{user?.nickname || '您好'}
              </div>
              <div className="text-sm mt-1" style={{ color: THEME.textSecondary }}>
                我是小康，您的AI健康助手
              </div>
            </div>

            {/* Banners */}
            {banners.length > 0 && (
              <div className="rounded-2xl overflow-hidden mb-5">
                <Swiper autoplay autoplayInterval={4000} loop>
                  {banners.map(banner => (
                    <Swiper.Item key={banner.id}>
                      <div
                        className="h-36 bg-cover bg-center rounded-2xl cursor-pointer"
                        style={{ backgroundImage: `url(${banner.image_url})` }}
                        onClick={() => banner.link_url && router.push(banner.link_url)}
                      />
                    </Swiper.Item>
                  ))}
                </Swiper>
              </div>
            )}

            {/* Function Cards */}
            <div className="grid grid-cols-3 gap-3">
              {funcButtons.slice(0, 6).map(btn => {
                const key = btn.button_type || btn.id;
                const icon = btn.icon || FUNCTION_ICONS[key] || '📌';
                return (
                  <div
                    key={btn.id}
                    className="flex flex-col items-center gap-2 py-4 rounded-2xl cursor-pointer active:opacity-70"
                    style={{ background: THEME.cardBg, boxShadow: '0 2px 8px rgba(91,108,255,0.08)' }}
                    onClick={() => handleFuncButton(btn)}
                  >
                    <span className="text-2xl">{icon}</span>
                    <span className="text-xs font-medium" style={{ color: THEME.textPrimary }}>{btn.name}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* Conversation State */
          <div className="px-4 py-3 space-y-3">
            {messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'assistant' && (
                  <div
                    className="flex-shrink-0 flex items-center justify-center rounded-full mr-2 text-sm"
                    style={{ width: 32, height: 32, background: THEME.gradient, color: '#fff' }}
                  >
                    🌿
                  </div>
                )}
                <div
                  className="max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed"
                  style={{
                    background: msg.role === 'user' ? THEME.cardBg : THEME.primaryLight,
                    color: THEME.textPrimary,
                    boxShadow: msg.role === 'user' ? '0 1px 4px rgba(0,0,0,0.06)' : 'none',
                    borderTopRightRadius: msg.role === 'user' ? 4 : 16,
                    borderTopLeftRadius: msg.role === 'assistant' ? 4 : 16,
                  }}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div
                  className="flex-shrink-0 flex items-center justify-center rounded-full mr-2 text-sm"
                  style={{ width: 32, height: 32, background: THEME.gradient, color: '#fff' }}
                >
                  🌿
                </div>
                <div className="px-4 py-3 rounded-2xl" style={{ background: THEME.primaryLight }}>
                  <SpinLoading style={{ '--size': '18px', '--color': THEME.primary }} />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Floating Check-in Button */}
      <div
        className="fixed right-4 cursor-pointer active:scale-95 transition-transform z-30"
        style={{ bottom: 120 }}
        onClick={() => router.push('/health-plan')}
      >
        <div
          className="relative flex items-center justify-center rounded-full shadow-lg text-xl"
          style={{ width: 48, height: 48, background: THEME.gradient, color: '#fff' }}
        >
          ✅
          {hasHealthTask && (
            <div
              className="absolute -top-0.5 -right-0.5 rounded-full"
              style={{ width: 10, height: 10, background: '#FF4D4F', border: '2px solid #fff' }}
            />
          )}
        </div>
      </div>

      {/* Bottom Quick Tags */}
      {funcButtons.length > 0 && (
        <div
          className="flex-shrink-0 overflow-x-auto px-4 py-2 flex gap-2"
          style={{ borderTop: `1px solid ${THEME.divider}`, background: THEME.cardBg, scrollbarWidth: 'none' }}
        >
          {funcButtons.slice(0, 8).map(btn => (
            <div
              key={btn.id}
              className="flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium cursor-pointer active:opacity-70"
              style={{ background: THEME.primaryLight, color: THEME.primary, whiteSpace: 'nowrap' }}
              onClick={() => handleFuncButton(btn)}
            >
              {btn.name}
            </div>
          ))}
        </div>
      )}

      {/* Input Bar */}
      <div
        className="flex-shrink-0 px-4 py-3"
        style={{
          background: THEME.cardBg,
          borderTop: `1px solid ${THEME.divider}`,
          paddingBottom: 'calc(12px + env(safe-area-inset-bottom))',
        }}
      >
        {/* Consultant picker & Recommend questions (focused state) */}
        {inputFocused && !inputValue && (
          <div className="mb-2 space-y-2">
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-xl cursor-pointer"
              style={{ background: THEME.primaryLight }}
              onClick={() => setConsultantOpen(true)}
            >
              <span className="text-sm">👤</span>
              <span className="text-xs" style={{ color: THEME.primary }}>
                {selectedConsultant ? `咨询人：${selectedConsultant.nickname}` : '+ 选择咨询人'}
              </span>
            </div>
            <RecommendCards items={recommendQuestions} onSelect={handleSend} />
          </div>
        )}

        <div className="flex items-center gap-2">
          {!inputValue && (
            <button className="text-xl flex-shrink-0" style={{ color: THEME.textSecondary }}>🎤</button>
          )}
          <div
            className="flex-1 flex items-center rounded-full px-4"
            style={{ background: THEME.background, height: 40 }}
          >
            <input
              className="flex-1 bg-transparent outline-none text-sm"
              placeholder="问问小康"
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              onFocus={() => setInputFocused(true)}
              onBlur={() => setTimeout(() => setInputFocused(false), 200)}
              onKeyDown={e => { if (e.key === 'Enter') handleSend(); }}
              style={{ color: THEME.textPrimary }}
            />
          </div>
          {inputValue ? (
            <button
              className="flex-shrink-0 flex items-center justify-center rounded-full text-sm font-medium"
              style={{ width: 40, height: 40, background: THEME.primary, color: '#fff' }}
              onClick={() => handleSend()}
            >
              ➤
            </button>
          ) : (
            <button className="text-xl flex-shrink-0" style={{ color: THEME.textSecondary }}>📷</button>
          )}
        </div>
      </div>

      {/* Overlays */}
      <Sidebar visible={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <MoreMenu
        visible={moreMenuOpen}
        onClose={() => setMoreMenuOpen(false)}
        onShare={() => setShareOpen(true)}
      />
      <ConsultantPicker
        visible={consultantOpen}
        onClose={() => setConsultantOpen(false)}
        onSelect={setSelectedConsultant}
      />
      <SharePanel visible={shareOpen} onClose={() => setShareOpen(false)} />
    </div>
  );
}
