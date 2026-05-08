'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Toast, Swiper, Dialog } from 'antd-mobile';
import { THEME } from '@/lib/theme';
import api from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { createChatSession } from '@/lib/chat-session';
import Sidebar from '@/components/ai-chat/Sidebar';
import MoreMenu from '@/components/ai-chat/MoreMenu';
import ConsultantPicker from '@/components/ai-chat/ConsultantPicker';
import RecommendCards from '@/components/ai-chat/RecommendCards';
import SharePanel from '@/components/ai-chat/SharePanel';
import SectionErrorBoundary from '@/components/SectionErrorBoundary';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  time: string;
  isStreaming?: boolean;
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

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

// ─── PRD-405 AI 对话首页配置 类型与默认值（v1.0） ───────────────
interface FuncGridItemCfg {
  id?: string;
  main_text: string;
  sub_text: string;
  target_path: string;
  icon: string;
  icon_image_url?: string;
  gradient_start: string;
  gradient_end: string;
  badge?: string;
  enabled: boolean;
  sort: number;
}

interface AIHomeConfig {
  welcome: {
    avatar: { type: 'emoji' | 'image'; emoji?: string; image_url?: string };
    greetings: { morning: string[]; afternoon: string[]; evening: string[] };
    subtitles: string[];
    show_nickname: boolean;
    main_title: string;
    sub_title: string;
  };
  topbar: {
    title: string;
    logo: { type: 'emoji' | 'image'; emoji?: string; image_url?: string };
    show_sidebar: boolean;
    show_more_menu: boolean;
    show_share: boolean;
    visible: boolean;
  };
  input: {
    placeholder: string;
    enable_voice: boolean;
    enable_tts: boolean;
    tts_provider: 'auto' | 'cloud' | 'browser';
    family_consult: {
      enabled: boolean;
      template: string;
      show_archive_link: boolean;
      archive_path: string;
    };
  };
  session: {
    idle_timeout_minutes: number;
    auto_new_session: boolean;
    empty_session_welcome: { enabled: boolean; messages: string[] };
    strategy: {
      max_answer_chars: number;
      show_loading: boolean;
      daily_free_quota: number;
      answer_style: 'professional' | 'easy' | 'friendly';
      sensitive_filter: boolean;
      context_memory_rounds: 3 | 5 | 10 | 20;
      disclaimer: string;
    };
  };
  floating_button: {
    enabled: boolean;
    icon: string;
    label?: string;
    show_label: boolean;
    target_path: string;
    position: 'right_bottom' | 'left_bottom';
  };
  banner: { visible: boolean };
  health_tips: { visible: boolean; interval_seconds: number; show_indicator: boolean };
  func_grid: { visible: boolean; columns: 2 | 3 | 4; max_count: number; items: FuncGridItemCfg[] };
  quick_tags: { visible: boolean; max_count: number };
  recommended_questions: Array<{
    id: string;
    icon: string;
    icon_image_url?: string;
    title: string;
    question: string;
    enabled: boolean;
    sort: number;
  }>;
  empty_placeholder: { icon: string; icon_image_url?: string; main_title: string };
  global_switches: {
    welcome_visible: boolean;
    health_tips_visible: boolean;
    func_grid_visible: boolean;
    recommended_visible: boolean;
    empty_placeholder_visible: boolean;
    family_pill_visible: boolean;
    archive_link_visible: boolean;
    voice_input_visible: boolean;
    floating_button_visible: boolean;
  };
}

const FALLBACK_CONFIG: AIHomeConfig = {
  welcome: {
    avatar: { type: 'emoji', emoji: '🌿' },
    greetings: { morning: ['早上好'], afternoon: ['午安'], evening: ['晚上好'] },
    subtitles: ['我是您的AI健康顾问小康'],
    show_nickname: true,
    main_title: '早上好，{昵称}！',
    sub_title: '我是您的AI健康顾问小康',
  },
  topbar: {
    title: 'AI 健康助手',
    logo: { type: 'emoji', emoji: '🌿' },
    show_sidebar: true,
    show_more_menu: true,
    show_share: true,
    visible: false,
  },
  input: {
    placeholder: '发消息或按住说话...',
    enable_voice: true,
    enable_tts: true,
    tts_provider: 'auto',
    family_consult: {
      enabled: true,
      template: '为({name})咨询',
      show_archive_link: true,
      archive_path: '/health-records',
    },
  },
  session: {
    idle_timeout_minutes: 30,
    auto_new_session: true,
    empty_session_welcome: { enabled: false, messages: [] },
    strategy: {
      max_answer_chars: 1000,
      show_loading: true,
      daily_free_quota: 50,
      answer_style: 'friendly',
      sensitive_filter: true,
      context_memory_rounds: 5,
      disclaimer: '以上内容仅供参考，不能替代医生诊疗',
    },
  },
  floating_button: {
    enabled: true,
    icon: '✅',
    label: '健康打卡',
    show_label: true,
    target_path: '/health-plan',
    position: 'right_bottom',
  },
  banner: { visible: true },
  health_tips: { visible: true, interval_seconds: 4, show_indicator: true },
  func_grid: {
    visible: true,
    columns: 3,
    max_count: 6,
    items: [
      { id: 'g1', main_text: 'AI诊室', sub_text: '智能问诊', target_path: '/ai-doctor', icon: '🩺', gradient_start: '#5B6CFF', gradient_end: '#8B9AFF', badge: '', enabled: true, sort: 1 },
      { id: 'g2', main_text: '看报告', sub_text: '解读体检报告', target_path: '/checkup', icon: '📋', gradient_start: '#FF7E5F', gradient_end: '#FEB47B', badge: '', enabled: true, sort: 2 },
      { id: 'g3', main_text: '健康档案', sub_text: '查看个人档案', target_path: '/health-archive', icon: '📁', gradient_start: '#43E97B', gradient_end: '#38F9D7', badge: '', enabled: true, sort: 3 },
    ],
  },
  quick_tags: { visible: true, max_count: 8 },
  recommended_questions: [
    { id: 'r1', icon: '📋', title: '体检解读', question: '帮我解读最新体检报告', enabled: true, sort: 1 },
    { id: 'r2', icon: '💊', title: '用药咨询', question: '感冒了吃什么药比较好？', enabled: true, sort: 2 },
    { id: 'r3', icon: '🥗', title: '饮食建议', question: '高血压患者饮食注意什么？', enabled: true, sort: 3 },
    { id: 'r4', icon: '💚', title: '失眠', question: '最近总是失眠怎么办？', enabled: true, sort: 4 },
  ],
  empty_placeholder: { icon: '💬', main_title: '还没有对话记录' },
  global_switches: {
    welcome_visible: true,
    health_tips_visible: true,
    func_grid_visible: true,
    recommended_visible: true,
    empty_placeholder_visible: true,
    family_pill_visible: true,
    archive_link_visible: true,
    voice_input_visible: true,
    floating_button_visible: true,
  },
};

function pickRandom<T>(arr: T[], fallback: T): T {
  if (!Array.isArray(arr) || arr.length === 0) return fallback;
  return arr[Math.floor(Math.random() * arr.length)];
}

function getGreetingByConfig(cfg: AIHomeConfig): string {
  const h = new Date().getHours();
  let pool: string[];
  if (h >= 5 && h < 12) pool = cfg.welcome.greetings.morning;
  else if (h >= 12 && h < 18) pool = cfg.welcome.greetings.afternoon;
  else pool = cfg.welcome.greetings.evening;
  return pickRandom(pool, '您好');
}

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 6) return '夜深了，注意休息';
  if (h < 9) return '早上好';
  if (h < 12) return '上午好';
  if (h < 14) return '中午好';
  if (h < 18) return '下午好';
  return '晚上好';
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const hh = d.getHours().toString().padStart(2, '0');
  const mm = d.getMinutes().toString().padStart(2, '0');
  return `${hh}:${mm}`;
}

function shouldShowTime(prev: string | null, curr: string): boolean {
  if (!prev) return true;
  return new Date(curr).getTime() - new Date(prev).getTime() > 5 * 60 * 1000;
}

function renderMarkdown(text: string): string {
  let html = text
    .replace(/\r\n/g, '\n')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  html = html.replace(/^###\s+(.+?)\s*$/gm, '<h3 style="font-size:15px;font-weight:bold;margin-top:10px;margin-bottom:4px">$1</h3>');
  html = html.replace(/^##\s+(.+?)\s*$/gm, '<h2 style="font-size:16px;font-weight:bold;margin-top:12px;margin-bottom:4px">$1</h2>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/`(.+?)`/g, '<code style="background:#E8E8F0;padding:1px 4px;border-radius:3px;font-size:12px">$1</code>');
  html = html.replace(/^- (.+)$/gm, '<li style="margin-left:16px;list-style:disc">$1</li>');
  html = html.replace(/^(\d+)\. (.+)$/gm, '<li style="margin-left:16px;list-style:decimal">$2</li>');
  html = html.replace(/\n/g, '<br/>');
  return html;
}

export default function AiHomePage() {
  const router = useRouter();
  const { user } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

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
  const [idleTimeout, setIdleTimeout] = useState<number>(30 * 60 * 1000);
  const [lastMsgTime, setLastMsgTime] = useState<number>(0);
  const [voiceMode, setVoiceMode] = useState(false);
  const [recording, setRecording] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);
  const [recordStartY, setRecordStartY] = useState(0);
  const [recordCancelled, setRecordCancelled] = useState(false);
  const [volumeLevel, setVolumeLevel] = useState(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number>(0);

  // PRD-405：从后端读取 AI 首页配置（带 5 分钟本地缓存 + 内置兜底）
  const [aiHomeConfig, setAiHomeConfig] = useState<AIHomeConfig>(FALLBACK_CONFIG);
  // 同一会话期内固定的随机选择
  const [pickedGreeting, setPickedGreeting] = useState<string>('');
  const [pickedSubtitle, setPickedSubtitle] = useState<string>('');

  const recommendQuestions = (aiHomeConfig.recommended_questions || [])
    .filter((q) => q.enabled)
    .sort((a, b) => (a.sort || 0) - (b.sort || 0))
    .slice(0, 8)
    .map((q) => ({ tag: q.title || q.icon, text: q.question }));

  useEffect(() => {
    if (typeof window !== 'undefined' && navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function') {
      setVoiceSupported(true);
    }
  }, []);

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

    api.get('/api/app-settings/chat-idle-timeout').then((res: any) => {
      const data = res.data || res;
      if (data.timeout_ms) setIdleTimeout(data.timeout_ms);
      else if (data.timeout_minutes) setIdleTimeout(data.timeout_minutes * 60 * 1000);
    }).catch(() => {});

    // PRD-405：拉取 AI 对话首页配置（带 5 分钟本地缓存 + 内置兜底）
    // [Bug-419 H-5/H-8 2026-05-08] 把原来的浅合并 `{ ...FALLBACK, ...data }` 换成
    // 顶层 key 级深合并：避免后端任一模块返回 `{}`/缺字段时把 FALLBACK_CONFIG
    // 的整组默认值覆盖掉，从而读取 deep field（如 welcome.greetings.morning）抛
    // `Cannot read properties of undefined` → ai-home 整页白屏。
    (async () => {
      const CACHE_KEY = '__ai_home_config_cache__';
      const TTL = 5 * 60 * 1000;
      const mergeWithFallback = (data: any): AIHomeConfig => {
        const out: any = { ...FALLBACK_CONFIG };
        if (data && typeof data === 'object') {
          Object.keys(data).forEach((k) => {
            const v = (data as any)[k];
            const fb = (FALLBACK_CONFIG as any)[k];
            if (v && typeof v === 'object' && !Array.isArray(v) && fb && typeof fb === 'object' && !Array.isArray(fb)) {
              out[k] = { ...fb, ...v };
            } else if (v !== undefined && v !== null) {
              out[k] = v;
            }
          });
        }
        return out as AIHomeConfig;
      };
      try {
        let cached: { config: AIHomeConfig; ts: number } | null = null;
        if (typeof window !== 'undefined') {
          try {
            const raw = localStorage.getItem(CACHE_KEY);
            if (raw) cached = JSON.parse(raw);
          } catch {}
        }
        let cfg: AIHomeConfig | null = null;
        if (cached && Date.now() - cached.ts < TTL && cached.config) {
          // 缓存数据也走一遍兜底 merge，防止旧缓存缺字段（兼容线上历史脏缓存）
          cfg = mergeWithFallback(cached.config);
        }
        if (!cfg) {
          try {
            const res: any = await api.get('/api/ai-home-config');
            const data = res?.data?.config || res?.config || null;
            cfg = mergeWithFallback(data);
            try {
              localStorage.setItem(CACHE_KEY, JSON.stringify({ config: cfg, ts: Date.now() }));
            } catch {}
          } catch {
            // [Bug-419 H-8] 接口失败时直接使用内置完整默认配置，保持首页骨架完整
            cfg = { ...FALLBACK_CONFIG };
          }
        }
        setAiHomeConfig(cfg!);
      } catch {
        // 任何意外异常都不让首页崩塌：使用兜底配置
        setAiHomeConfig({ ...FALLBACK_CONFIG });
      }
    })();
  }, []);

  // 同一会话期内随机选定问候语和副标题（仅在配置加载完成后执行一次）
  useEffect(() => {
    if (!pickedGreeting) {
      setPickedGreeting(getGreetingByConfig(aiHomeConfig));
    }
    if (!pickedSubtitle) {
      setPickedSubtitle(pickRandom(aiHomeConfig.welcome?.subtitles || [], '我是您的AI健康助手'));
    }
    // 同步空闲超时（如果新配置下发更短/更长）
    const m = aiHomeConfig.session?.idle_timeout_minutes;
    if (m && m > 0) setIdleTimeout(m * 60 * 1000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aiHomeConfig]);

  // PRD-405 F-11：空会话引导（不入库，仅 UI 提示）
  useEffect(() => {
    const cfg = aiHomeConfig.session?.empty_session_welcome;
    if (
      cfg &&
      cfg.enabled &&
      Array.isArray(cfg.messages) &&
      cfg.messages.length > 0 &&
      !sessionId &&
      messages.length === 0
    ) {
      const text = pickRandom(cfg.messages, '');
      if (text) {
        setMessages([
          {
            id: `welcome-${Date.now()}`,
            role: 'assistant',
            content: text,
            time: new Date().toISOString(),
          },
        ]);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aiHomeConfig, sessionId]);

  useEffect(() => {
    loadLastSession();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadLastSession = async () => {
    try {
      const res: any = await api.get('/api/chat/sessions', { params: { limit: 1, sort: '-updated_at' } });
      const data = res.data || res;
      const list = Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : []);
      if (list.length > 0) {
        const session = list[0];
        const sid = String(session.id);
        setSessionId(sid);
        setLastMsgTime(new Date(session.updated_at || session.created_at).getTime());
        await loadSessionMessages(sid);
      }
    } catch {}
  };

  const loadSessionMessages = async (sid: string) => {
    try {
      const res: any = await api.get(`/api/chat/sessions/${sid}/messages`);
      const data = res.data || res;
      const list = Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : []);
      if (list.length > 0) {
        const mapped: ChatMessage[] = list.map((m: any) => ({
          id: String(m.id),
          role: m.role === 'user' ? 'user' as const : 'assistant' as const,
          content: m.content || '',
          time: m.created_at || new Date().toISOString(),
        }));
        setMessages(mapped);
      }
    } catch {}
  };

  const createNewSession = async (): Promise<string | null> => {
    // [Bug-419 H-1/H-2] 走统一 createChatSession 工具，自动补齐 session_type=health_qa
    // 并把字段名规范化为 family_member_id（修复历史 member_id 字段名错误导致的 422）。
    // 工具内部已 try/catch + Toast，不会向上抛异常，避免触发 ai-home 整页白屏。
    const res = await createChatSession({
      session_type: 'health_qa',
      family_member_id: selectedConsultant ? selectedConsultant.id : undefined,
    });
    if (!res.ok || !res.sessionId) return null;
    setSessionId(res.sessionId);
    return res.sessionId;
  };

  const checkIdleAndMaybeNewSession = async (): Promise<string> => {
    const now = Date.now();
    if (sessionId && lastMsgTime && (now - lastMsgTime) > idleTimeout) {
      setMessages([]);
      const newSid = await createNewSession();
      return newSid || sessionId;
    }
    if (!sessionId) {
      const newSid = await createNewSession();
      return newSid || '';
    }
    return sessionId;
  };

  const sendSSE = async (sid: string, message: string, retries = 3): Promise<boolean> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : '';
    const aiMsgId = `a-${Date.now()}`;
    const aiMsg: ChatMessage = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      time: new Date().toISOString(),
      isStreaming: true,
    };
    setMessages(prev => [...prev, aiMsg]);

    for (let attempt = 0; attempt < retries; attempt++) {
      try {
        const controller = new AbortController();
        abortRef.current = controller;

        const response = await fetch(`${basePath}/api/chat/sessions/${sid}/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({ content: message, message_type: 'text' }),
          signal: controller.signal,
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const reader = response.body?.getReader();
        if (!reader) throw new Error('No reader');

        const decoder = new TextDecoder();
        let accumulated = '';
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const payload = line.substring(6);
              if (payload === '[DONE]') break;
              try {
                const parsed = JSON.parse(payload);
                if (parsed.content) {
                  accumulated += parsed.content;
                  setMessages(prev => prev.map(m =>
                    m.id === aiMsgId ? { ...m, content: accumulated } : m
                  ));
                }
              } catch {}
            }
          }
        }

        setMessages(prev => prev.map(m =>
          m.id === aiMsgId ? { ...m, isStreaming: false } : m
        ));
        abortRef.current = null;
        return true;
      } catch (err: any) {
        if (err.name === 'AbortError') {
          setMessages(prev => prev.map(m =>
            m.id === aiMsgId ? { ...m, isStreaming: false } : m
          ));
          return true;
        }
        if (attempt === retries - 1) {
          setMessages(prev => prev.filter(m => m.id !== aiMsgId));
          return false;
        }
        await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
      }
    }
    return false;
  };

  const sendFallback = async (sid: string, message: string) => {
    try {
      const res: any = await api.post(`/api/chat/sessions/${sid}/messages`, {
        content: message,
        message_type: 'text',
      });
      const data = res.data || res;
      const aiMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: data.reply || data.content || data.message || '抱歉，我暂时无法回复',
        time: new Date().toISOString(),
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch {
      setMessages(prev => [...prev, {
        id: `e-${Date.now()}`,
        role: 'assistant',
        content: '网络异常，请稍后重试',
        time: new Date().toISOString(),
      }]);
    }
  };

  const handleSend = useCallback(async (text?: string) => {
    const msg = text || inputValue.trim();
    if (!msg || sending) return;

    setInputValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = '24px';
    }

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: msg,
      time: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);
    setSending(true);
    setLastMsgTime(Date.now());

    try {
      const sid = await checkIdleAndMaybeNewSession();
      if (!sid) {
        setMessages(prev => [...prev, {
          id: `e-${Date.now()}`,
          role: 'assistant',
          content: '创建会话失败，请重试',
          time: new Date().toISOString(),
        }]);
        setSending(false);
        return;
      }

      const sseOk = await sendSSE(sid, msg);
      if (!sseOk) {
        await sendFallback(sid, msg);
      }
    } catch {
      setMessages(prev => [...prev, {
        id: `e-${Date.now()}`,
        role: 'assistant',
        content: '网络异常，请稍后重试',
        time: new Date().toISOString(),
      }]);
    }
    setSending(false);
  }, [inputValue, sending, sessionId, selectedConsultant, idleTimeout, lastMsgTime]);

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

  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    const el = e.target;
    el.style.height = '24px';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  };

  const mimeTypeRef = useRef('');
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);

  const getPreferredMimeType = (): string => {
    if (typeof MediaRecorder !== 'undefined') {
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus';
      if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/mp4')) return 'audio/mp4';
      if (MediaRecorder.isTypeSupported('audio/mp3')) return 'audio/mp3';
    }
    return '';
  };

  const mimeToFormat = (mime: string): string => {
    if (!mime) return 'webm';
    if (mime.includes('webm')) return 'webm';
    if (mime.includes('mp4')) return 'm4a';
    if (mime.includes('mp3') || mime.includes('mpeg')) return 'mp3';
    return 'webm';
  };

  const checkMicPermission = useCallback(async (): Promise<boolean> => {
    if (!navigator.mediaDevices?.getUserMedia) {
      Toast.show({ content: '当前浏览器不支持语音输入', icon: 'fail' });
      return false;
    }
    try {
      if (navigator.permissions) {
        const permStatus = await navigator.permissions.query({ name: 'microphone' as PermissionName });
        if (permStatus.state === 'granted') return true;
        if (permStatus.state === 'denied') {
          Toast.show({ content: '麦克风权限已被禁止，请在系统设置中开启', icon: 'fail', duration: 2500 });
          return false;
        }
      }
      const result = await Dialog.confirm({
        title: '允许访问麦克风',
        content: '需要使用麦克风进行语音输入，请授权',
        confirmText: '去授权',
        cancelText: '取消',
      });
      if (!result) return false;
      const testStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      testStream.getTracks().forEach(t => t.stop());
      return true;
    } catch {
      Toast.show({ content: '请在系统设置中开启麦克风权限', icon: 'fail', duration: 2500 });
      return false;
    }
  }, []);

  const handleMicToggle = useCallback(async () => {
    if (voiceMode) {
      setVoiceMode(false);
      return;
    }
    const granted = await checkMicPermission();
    if (granted) setVoiceMode(true);
  }, [voiceMode, checkMicPermission]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const mime = getPreferredMimeType();
      mimeTypeRef.current = mime;
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      const updateVolume = () => {
        if (!analyserRef.current) return;
        const data = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(data);
        const avg = data.reduce((a, b) => a + b, 0) / data.length;
        setVolumeLevel(Math.min(avg / 128, 1));
        animFrameRef.current = requestAnimationFrame(updateVolume);
      };
      updateVolume();

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        cancelAnimationFrame(animFrameRef.current);
        analyserRef.current = null;
        setVolumeLevel(0);
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(t => t.stop());
          streamRef.current = null;
        }
        if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
          try { audioCtxRef.current.close(); } catch {}
        }
        audioCtxRef.current = null;

        if (recordCancelled) {
          setRecordCancelled(false);
          return;
        }

        const fmt = mimeToFormat(mimeTypeRef.current);
        const blob = new Blob(audioChunksRef.current, { type: mimeTypeRef.current || 'audio/webm' });
        if (blob.size < 1000) {
          Toast.show({ content: '录音时间太短' });
          return;
        }

        Toast.show({ content: '语音识别中...', icon: 'loading' });
        try {
          const fd = new FormData();
          fd.append('audio_file', blob, `recording.${fmt}`);
          fd.append('format', fmt);
          fd.append('sample_rate', '16000');
          const data: any = await api.post('/api/search/asr/recognize', fd, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 30000,
          });
          Toast.clear();
          const text = data?.data?.text || data?.text || '';
          if (text.trim()) {
            handleSend(text.trim());
          } else {
            Toast.show({ content: '未识别到语音内容，请重试' });
          }
        } catch {
          Toast.clear();
          Toast.show({ content: '语音识别失败，请重试' });
        }
      };

      recorder.start(250);
      setRecording(true);
      setRecordCancelled(false);
    } catch {
      Toast.show({ content: '无法访问麦克风，请检查权限设置' });
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setRecording(false);
  };

  const cancelRecording = () => {
    setRecordCancelled(true);
    stopRecording();
    Toast.show({ content: '已取消' });
  };

  const handleRecordTouchStart = (e: React.TouchEvent) => {
    setRecordStartY(e.touches[0].clientY);
    startRecording();
  };

  const handleRecordTouchMove = (e: React.TouchEvent) => {
    const dy = recordStartY - e.touches[0].clientY;
    if (dy > 80) {
      setRecordCancelled(true);
    } else {
      setRecordCancelled(false);
    }
  };

  const handleRecordTouchEnd = () => {
    if (recordCancelled) {
      cancelRecording();
    } else {
      stopRecording();
    }
  };

  const stopTts = useCallback(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (ttsAudioRef.current) {
      ttsAudioRef.current.pause();
      ttsAudioRef.current = null;
    }
    setTtsPlaying(false);
  }, []);

  const handleTTS = useCallback(async (text: string) => {
    if (ttsPlaying) {
      stopTts();
      return;
    }
    stopTts();

    const plainText = text.replace(/\*\*(.*?)\*\*/g, '$1').replace(/---disclaimer---[\s\S]*/g, '').trim();
    if (!plainText) return;

    setTtsPlaying(true);

    try {
      const configRes: any = await api.get('/api/settings/tts-config', { params: { platform: 'h5' } }).catch(() => null);
      const config = configRes?.data || configRes;
      const useCloudTts = config?.tts_provider === 'cloud' || config?.use_cloud_tts;

      if (useCloudTts) {
        const ttsRes: any = await api.post('/api/tts/synthesize', { text: plainText });
        const data = ttsRes.data || ttsRes;
        if (data.audio_url) {
          const audio = new Audio(data.audio_url);
          ttsAudioRef.current = audio;
          audio.onended = () => setTtsPlaying(false);
          audio.onerror = () => {
            setTtsPlaying(false);
            Toast.show({ content: '播放失败，请重试' });
          };
          audio.play();
          return;
        }
      }
    } catch {}

    if (typeof window !== 'undefined' && window.speechSynthesis) {
      const utterance = new SpeechSynthesisUtterance(plainText);
      utterance.lang = 'zh-CN';
      utterance.rate = 1.0;
      utterance.onend = () => setTtsPlaying(false);
      utterance.onerror = () => {
        setTtsPlaying(false);
        tryCloudTtsFallback(plainText);
      };
      window.speechSynthesis.speak(utterance);
    } else {
      tryCloudTtsFallback(plainText);
    }
  }, [ttsPlaying, stopTts]);

  const tryCloudTtsFallback = async (text: string) => {
    try {
      const ttsRes: any = await api.post('/api/tts/synthesize', { text });
      const data = ttsRes.data || ttsRes;
      if (data.audio_url) {
        const audio = new Audio(data.audio_url);
        ttsAudioRef.current = audio;
        audio.onended = () => setTtsPlaying(false);
        audio.onerror = () => {
          setTtsPlaying(false);
          Toast.show({ content: '当前浏览器不支持语音播报' });
        };
        audio.play();
        return;
      }
    } catch {}
    setTtsPlaying(false);
    Toast.show({ content: '当前浏览器不支持语音播报' });
  };

  const handleCopy = (text: string) => {
    navigator.clipboard?.writeText(text).then(() => {
      Toast.show({ content: '已复制', icon: 'success' });
    }).catch(() => {
      Toast.show({ content: '复制失败' });
    });
  };

  const handleNewConversation = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    setLastMsgTime(0);
    abortRef.current?.abort();
  }, []);

  const handleSelectSession = useCallback(async (sid: string) => {
    setMessages([]);
    setSessionId(sid);
    setSidebarOpen(false);
    await loadSessionMessages(sid);
  }, []);

  const hasConversation = messages.length > 0;
  const lastAiMsgIndex = messages.reduce((acc, m, i) => m.role === 'assistant' ? i : acc, -1);

  // v1.0 全局开关取并集
  // [Bug-419 H-5 2026-05-08] 全部使用安全字段读取（?. + ??），即使后端返回的
  // 配置缺失子字段，也不会触发 "Cannot read properties of undefined" → 保护首页
  // 不会因任何字段读取异常而整片塌陷。
  const sw = aiHomeConfig.global_switches || FALLBACK_CONFIG.global_switches;
  const welcomeVisible = sw?.welcome_visible ?? true;
  const healthTipsVisible = (sw?.health_tips_visible ?? true) && (aiHomeConfig.health_tips?.visible ?? true);
  const funcGridVisible = (sw?.func_grid_visible ?? true) && (aiHomeConfig.func_grid?.visible ?? true);
  const recommendedVisible = sw?.recommended_visible ?? true;
  const emptyPlaceholderVisible = sw?.empty_placeholder_visible ?? true;
  const familyPillVisible = (sw?.family_pill_visible ?? true) && (aiHomeConfig.input?.family_consult?.enabled ?? true);
  const archiveLinkVisible = (sw?.archive_link_visible ?? true) && (aiHomeConfig.input?.family_consult?.show_archive_link ?? true);
  const voiceInputVisible = (sw?.voice_input_visible ?? true) && (aiHomeConfig.input?.enable_voice ?? true);
  const floatingButtonVisible = (sw?.floating_button_visible ?? true) && (aiHomeConfig.floating_button?.enabled ?? true);

  // 主标题占位符替换（[Bug-419 H-5] 全部 ?. + 默认值兜底）
  const renderMainTitle = (): string => {
    const tpl = aiHomeConfig.welcome?.main_title || '早上好，{昵称}！';
    const nick = (aiHomeConfig.welcome?.show_nickname && user?.nickname) ? user.nickname : '';
    return tpl.replace('{昵称}', nick || '朋友');
  };
  const renderFamilyPillText = (): string => {
    const tpl = aiHomeConfig.input?.family_consult?.template || '为({name})咨询';
    const name = selectedConsultant?.nickname || '本人';
    return tpl.replace('{name}', name);
  };

  // 兜底功能宫格项：优先使用配置中的 items；若为空，使用 FALLBACK 3 项
  const configuredItems = (aiHomeConfig.func_grid?.items && aiHomeConfig.func_grid.items.length > 0)
    ? aiHomeConfig.func_grid.items
    : FALLBACK_CONFIG.func_grid.items;
  const gridItems = (configuredItems || [])
    .filter((g) => g && g.enabled)
    .slice(0, aiHomeConfig.func_grid?.max_count || 6);

  // [Bug-419 H-5] 顶栏字段安全读取，缺失时按 v1.0 设计图（无顶栏）兜底
  const topbarVisible = aiHomeConfig.topbar?.visible ?? false;
  const topbarShowSidebar = aiHomeConfig.topbar?.show_sidebar ?? true;
  const topbarShowMoreMenu = aiHomeConfig.topbar?.show_more_menu ?? true;

  return (
    <div className="flex flex-col h-screen" style={{ background: THEME.background, maxWidth: 750, margin: '0 auto' }}>
      {/* Top Bar (v1.0 设计图无顶栏，由 topbar.visible 控制) */}
      <SectionErrorBoundary name="topbar">
        {topbarVisible ? (
          <div
            className="flex items-center justify-between px-4 flex-shrink-0"
            style={{ height: 48, background: THEME.cardBg, borderBottom: `1px solid ${THEME.divider}` }}
          >
            <div className="flex items-center gap-3">
              {topbarShowSidebar && (
                <button className="text-xl" onClick={() => setSidebarOpen(true)}>☰</button>
              )}
              {aiHomeConfig.topbar?.logo?.type === 'image' && aiHomeConfig.topbar?.logo?.image_url ? (
                <img
                  src={aiHomeConfig.topbar.logo.image_url}
                  alt="logo"
                  style={{ width: 24, height: 24, borderRadius: 4, objectFit: 'cover' }}
                />
              ) : (
                <span className="text-base">{aiHomeConfig.topbar?.logo?.emoji || '🌿'}</span>
              )}
              <span className="font-bold text-base" style={{ color: THEME.textPrimary }}>
                {aiHomeConfig.topbar?.title || 'AI 健康助手'}
              </span>
            </div>
            {topbarShowMoreMenu && (
              <button className="text-xl tracking-widest" onClick={() => setMoreMenuOpen(true)}>···</button>
            )}
          </div>
        ) : (
          /* v1.0 设计图无顶栏时仍需提供入口（隐藏在欢迎区右上角的 ··· 按钮） */
          <div className="flex items-center justify-end px-4 pt-2" style={{ height: 32 }}>
            <button
              className="text-xl tracking-widest"
              style={{ color: THEME.textSecondary }}
              onClick={() => setSidebarOpen(true)}
              aria-label="历史记录"
            >
              ☰
            </button>
          </div>
        )}
      </SectionErrorBoundary>

      {/* Main Content */}
      {/* [Bug-419 H-4/H-7 2026-05-08] 各区块独立 ErrorBoundary，任何子组件
          异常仅降级该区块（默认占位 8px），绝不让顶部菜单/输入框/浮动按钮
          被牵连 unmount，杜绝"422 → 整页白屏"事故。 */}
      <div className="flex-1 overflow-y-auto">
        {!hasConversation ? (
          <div className="px-4 py-3">
            {/* v1.0 欢迎区：左头像 + 右文字 横向布局 */}
            <SectionErrorBoundary name="welcome">
              {welcomeVisible && (
                <div className="flex items-center gap-3 py-4">
                  {aiHomeConfig.welcome?.avatar?.type === 'image' && aiHomeConfig.welcome?.avatar?.image_url ? (
                    <img
                      src={aiHomeConfig.welcome.avatar.image_url}
                      alt="avatar"
                      className="rounded-full flex-shrink-0"
                      style={{ width: 56, height: 56, objectFit: 'cover' }}
                    />
                  ) : (
                    <div
                      className="flex items-center justify-center rounded-full text-3xl flex-shrink-0"
                      style={{ width: 56, height: 56, background: THEME.gradient, color: '#fff' }}
                    >
                      {aiHomeConfig.welcome?.avatar?.emoji || '🌿'}
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-lg font-bold truncate" style={{ color: THEME.textPrimary }}>
                      {renderMainTitle()}
                    </div>
                    <div className="text-sm mt-0.5 truncate" style={{ color: THEME.textSecondary }}>
                      {aiHomeConfig.welcome?.sub_title || pickedSubtitle || '我是您的AI健康顾问小康'}
                    </div>
                  </div>
                </div>
              )}
            </SectionErrorBoundary>

            {/* v1.0 紫色今日健康贴士轮播卡（图片做整张卡片背景） */}
            <SectionErrorBoundary name="health_tips">
              {healthTipsVisible && banners.length > 0 && (
                <div className="rounded-2xl overflow-hidden mb-4 shadow-lg" style={{ background: 'linear-gradient(135deg, #5B6CFF 0%, #8B5CF6 100%)' }}>
                  <Swiper
                    autoplay
                    autoplayInterval={(aiHomeConfig.health_tips?.interval_seconds || 4) * 1000}
                    loop
                    indicator={(aiHomeConfig.health_tips?.show_indicator ?? true) ? undefined : () => null}
                  >
                    {banners.map(banner => (
                      <Swiper.Item key={banner.id}>
                        <div
                          className="bg-cover bg-center cursor-pointer"
                          style={{
                            height: 130,
                            backgroundImage: `url(${banner.image_url})`,
                            backgroundColor: '#5B6CFF',
                          }}
                          onClick={() => banner.link_url && router.push(banner.link_url)}
                        />
                      </Swiper.Item>
                    ))}
                  </Swiper>
                </div>
              )}
            </SectionErrorBoundary>

            {/* v1.0 功能宫格 7 字段 */}
            <SectionErrorBoundary name="func_grid">
              {funcGridVisible && gridItems.length > 0 && (
                <div
                  className={`grid gap-3 mb-4`}
                  style={{ gridTemplateColumns: `repeat(${aiHomeConfig.func_grid?.columns || 3}, minmax(0, 1fr))` }}
                >
                  {gridItems.map(it => (
                    <div
                      key={it.id}
                      className="relative flex flex-col items-center justify-center gap-1.5 py-4 rounded-2xl cursor-pointer active:opacity-80"
                      style={{
                        background: `linear-gradient(135deg, ${it.gradient_start} 0%, ${it.gradient_end} 100%)`,
                        color: '#fff',
                        minHeight: 90,
                      }}
                      onClick={() => {
                        const p = it.target_path;
                        if (p && (p.startsWith('/') || p.startsWith('http'))) {
                          if (p.startsWith('http')) window.location.href = p;
                          else router.push(p);
                        }
                      }}
                    >
                      <span className="text-2xl">{it.icon || '📌'}</span>
                      <span className="text-sm font-semibold">{it.main_text}</span>
                      <span className="text-xs opacity-90 text-center px-1">{it.sub_text}</span>
                      {it.badge && (
                        <span
                          className="absolute top-1 right-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold"
                          style={{ background: '#FF4D4F', color: '#fff' }}
                        >
                          {it.badge}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </SectionErrorBoundary>

            {/* v1.0 推荐问横向滚动胶囊（位于功能宫格下方、空对话占位上方） */}
            <SectionErrorBoundary name="recommended">
              {recommendedVisible && recommendQuestions.length > 0 && (
                <div className="mb-4">
                  <div
                    className="flex gap-2 overflow-x-auto pb-2"
                    style={{ scrollbarWidth: 'none' as any, msOverflowStyle: 'none' as any }}
                  >
                    {recommendQuestions.map((q, i) => (
                      <div
                        key={i}
                        className="flex-shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-full cursor-pointer active:opacity-70"
                        style={{ background: '#fff', border: `1px solid ${THEME.divider}`, whiteSpace: 'nowrap' }}
                        onClick={() => handleSend(q.text)}
                      >
                        {q.tag && <span className="text-base">{q.tag}</span>}
                        <span className="text-sm" style={{ color: THEME.textPrimary }}>{q.text.length > 12 ? q.text.slice(0, 12) + '…' : q.text}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </SectionErrorBoundary>

            {/* v1.0 空对话占位（大图标 + 主标题 居中） */}
            <SectionErrorBoundary name="empty_placeholder">
              {emptyPlaceholderVisible && messages.length === 0 && (
                <div className="flex flex-col items-center py-8">
                  <div className="text-5xl mb-3 opacity-60">{aiHomeConfig.empty_placeholder?.icon || '💬'}</div>
                  <div className="text-base" style={{ color: THEME.textSecondary }}>
                    {aiHomeConfig.empty_placeholder?.main_title || '还没有对话记录'}
                  </div>
                </div>
              )}
            </SectionErrorBoundary>
          </div>
        ) : (
          <div className="px-4 py-3 space-y-1">
            {messages.map((msg, idx) => {
              const prevTime = idx > 0 ? messages[idx - 1].time : null;
              const showTime = shouldShowTime(prevTime, msg.time);
              const isLastAi = idx === lastAiMsgIndex && msg.role === 'assistant' && !msg.isStreaming;

              return (
                <div key={msg.id}>
                  {showTime && (
                    <div className="text-center py-2">
                      <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: THEME.divider, color: THEME.textSecondary }}>
                        {formatTimestamp(msg.time)}
                      </span>
                    </div>
                  )}
                  <div className={`flex mb-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {msg.role === 'assistant' && (
                      <div
                        className="flex-shrink-0 flex items-center justify-center rounded-full mr-2 text-sm mt-1"
                        style={{ width: 32, height: 32, background: THEME.gradient, color: '#fff' }}
                      >
                        🌿
                      </div>
                    )}
                    <div className="flex flex-col max-w-[75%]">
                      <div
                        className="px-4 py-3 rounded-2xl text-sm leading-relaxed"
                        style={{
                          background: msg.role === 'user' ? THEME.primary : '#F5F5F5',
                          color: msg.role === 'user' ? '#FFFFFF' : THEME.textPrimary,
                          borderTopRightRadius: msg.role === 'user' ? 4 : 16,
                          borderTopLeftRadius: msg.role === 'assistant' ? 4 : 16,
                        }}
                      >
                        {msg.role === 'assistant' ? (
                          <span>
                            <span dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
                            {msg.isStreaming && (
                              <span className="inline-block w-0.5 h-4 ml-0.5 align-middle" style={{
                                background: THEME.primary,
                                animation: 'blink 1s steps(2) infinite',
                              }} />
                            )}
                          </span>
                        ) : (
                          msg.content
                        )}
                      </div>

                      {isLastAi && (
                        <div className="flex gap-3 mt-1.5 ml-1">
                          <button
                            className="text-xs flex items-center gap-1 px-2 py-1 rounded-lg active:opacity-60"
                            style={{ color: THEME.textSecondary, background: THEME.cardBg, border: `1px solid ${THEME.divider}` }}
                            onClick={() => handleCopy(msg.content)}
                          >
                            📋 复制
                          </button>
                          <button
                            className="text-xs flex items-center gap-1 px-2 py-1 rounded-lg active:opacity-60"
                            style={{ color: ttsPlaying ? THEME.primary : THEME.textSecondary, background: THEME.cardBg, border: `1px solid ${ttsPlaying ? THEME.primary : THEME.divider}` }}
                            onClick={() => handleTTS(msg.content)}
                          >
                            {ttsPlaying ? '⏹ 停止播报' : '🔊 播报'}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            {sending && !messages.some(m => m.isStreaming) && (
              <div className="flex justify-start mb-2">
                <div
                  className="flex-shrink-0 flex items-center justify-center rounded-full mr-2 text-sm"
                  style={{ width: 32, height: 32, background: THEME.gradient, color: '#fff' }}
                >
                  🌿
                </div>
                <div className="px-4 py-3 rounded-2xl" style={{ background: '#F5F5F5' }}>
                  <div className="flex gap-1">
                    <span className="w-2 h-2 rounded-full" style={{ background: THEME.textSecondary, animation: 'bounce 1.4s infinite ease-in-out both', animationDelay: '0s' }} />
                    <span className="w-2 h-2 rounded-full" style={{ background: THEME.textSecondary, animation: 'bounce 1.4s infinite ease-in-out both', animationDelay: '0.2s' }} />
                    <span className="w-2 h-2 rounded-full" style={{ background: THEME.textSecondary, animation: 'bounce 1.4s infinite ease-in-out both', animationDelay: '0.4s' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Floating Check-in Button */}
      <SectionErrorBoundary name="floating_button">
        {floatingButtonVisible && (
          <div
            className={`fixed cursor-pointer active:scale-95 transition-transform z-30 ${
              aiHomeConfig.floating_button?.position === 'left_bottom' ? 'left-4' : 'right-4'
            }`}
            style={{ bottom: 120 }}
            onClick={() => {
              const path = aiHomeConfig.floating_button?.target_path || '/health-plan';
              if (path.startsWith('/')) router.push(path);
            }}
          >
            <div
              className="relative flex items-center justify-center rounded-full shadow-lg text-xl"
              style={{
                minWidth: 48,
                height: 48,
                padding: aiHomeConfig.floating_button?.show_label ? '0 12px' : 0,
                width: aiHomeConfig.floating_button?.show_label ? 'auto' : 48,
                background: THEME.gradient,
                color: '#fff',
              }}
            >
              <span>{aiHomeConfig.floating_button?.icon || '✅'}</span>
              {aiHomeConfig.floating_button?.show_label && aiHomeConfig.floating_button?.label && (
                <span className="ml-1 text-sm">{aiHomeConfig.floating_button.label}</span>
              )}
              {hasHealthTask && (
                <div
                  className="absolute -top-0.5 -right-0.5 rounded-full"
                  style={{ width: 10, height: 10, background: '#FF4D4F', border: '2px solid #fff' }}
                />
              )}
            </div>
          </div>
        )}
      </SectionErrorBoundary>

      {/* Bottom Quick Tags (兼容旧版本，仅在 quick_tags.visible 时显示) */}
      {false && !hasConversation && aiHomeConfig.quick_tags?.visible && funcButtons.length > 0 && (
        <div
          className="flex-shrink-0 overflow-x-auto px-4 py-2 flex gap-2"
          style={{ borderTop: `1px solid ${THEME.divider}`, background: THEME.cardBg, scrollbarWidth: 'none' }}
        >
          {funcButtons.slice(0, aiHomeConfig.quick_tags?.max_count || 8).map(btn => (
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
        {inputFocused && !inputValue && !hasConversation && (
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

        {voiceMode && voiceSupported ? (
          <div className="flex items-center gap-3">
            <button
              className="flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-full"
              style={{ background: THEME.primaryLight, color: THEME.primary }}
              onClick={handleMicToggle}
              aria-label="切换为键盘"
            >
              ⌨️
            </button>
            <div
              className="flex-1 flex items-center justify-center rounded-full py-3 select-none"
              style={{
                background: recording ? THEME.primaryLight : THEME.background,
                border: recording ? `2px solid ${THEME.primary}` : `2px solid transparent`,
                transition: 'all 0.2s',
              }}
              onTouchStart={handleRecordTouchStart}
              onTouchMove={handleRecordTouchMove}
              onTouchEnd={handleRecordTouchEnd}
              onMouseDown={() => startRecording()}
              onMouseUp={() => { if (recordCancelled) cancelRecording(); else stopRecording(); }}
            >
              {recording ? (
                <div className="flex items-center gap-2">
                  <div className="flex gap-0.5 items-end h-5">
                    {[0, 1, 2, 3, 4].map(i => (
                      <div
                        key={i}
                        className="w-1 rounded-full transition-all duration-100"
                        style={{
                          background: THEME.primary,
                          height: `${8 + volumeLevel * 12 * (1 + Math.sin(i * 1.2))}px`,
                        }}
                      />
                    ))}
                  </div>
                  <span className="text-sm" style={{ color: recordCancelled ? '#FF4D4F' : THEME.primary }}>
                    {recordCancelled ? '松开取消' : '松开发送'}
                  </span>
                </div>
              ) : (
                <span className="text-sm" style={{ color: THEME.textSecondary }}>按住说话</span>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-end gap-2">
            {voiceSupported && voiceInputVisible && (
              <button
                className="flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-full mb-0"
                style={{ background: THEME.primaryLight, color: THEME.primary }}
                onClick={handleMicToggle}
                aria-label="语音输入"
              >
                🎤
              </button>
            )}
            <div
              className="flex-1 flex items-end rounded-2xl px-3 py-2"
              style={{ background: THEME.background, minHeight: 40 }}
            >
              <textarea
                ref={textareaRef}
                className="flex-1 bg-transparent outline-none text-sm resize-none leading-6"
                placeholder={aiHomeConfig.input?.placeholder || '发消息或按住说话...'}
                value={inputValue}
                onChange={handleTextareaInput}
                onFocus={() => setInputFocused(true)}
                onBlur={() => setTimeout(() => setInputFocused(false), 200)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                rows={1}
                style={{ color: THEME.textPrimary, maxHeight: 120, height: 24 }}
              />
            </div>
            {/* v1.0 丁香派智能隐藏：键盘模式 + 输入框为空 → 灰显；有文字 → 亮起 */}
            <button
              className="flex-shrink-0 flex items-center justify-center rounded-full text-sm font-medium mb-0"
              style={{
                width: 40,
                height: 40,
                background: inputValue.trim() ? THEME.primary : THEME.divider,
                color: '#fff',
                transition: 'background 0.2s',
                opacity: inputValue.trim() ? 1 : 0.6,
                cursor: inputValue.trim() ? 'pointer' : 'not-allowed',
              }}
              onClick={() => handleSend()}
              disabled={!inputValue.trim() || sending}
              aria-label="发送"
            >
              ➤
            </button>
          </div>
        )}

        {/* v1.0 第二层：家庭成员快捷栏（家庭成员咨询胶囊 + 查看档案） */}
        {!voiceMode && (familyPillVisible || archiveLinkVisible) && (
          <div className="flex items-center justify-between gap-3 mt-2">
            {familyPillVisible ? (
              <button
                className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-full"
                style={{ background: THEME.primaryLight, color: THEME.primary, fontSize: 12 }}
                onClick={() => setConsultantOpen(true)}
                aria-label="切换咨询对象"
              >
                <span>{renderFamilyPillText()}</span>
                <span style={{ fontSize: 10 }}>⇆</span>
              </button>
            ) : <div />}
            {archiveLinkVisible && (
              <button
                className="flex-shrink-0 text-xs"
                style={{ color: THEME.textSecondary }}
                onClick={() => {
                  const p = aiHomeConfig.input?.family_consult?.archive_path || '/health-records';
                  if (p.startsWith('/')) router.push(p);
                }}
                aria-label="查看档案"
              >
                查看档案 ›
              </button>
            )}
          </div>
        )}
      </div>

      {/* Overlays */}
      <Sidebar
        visible={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewConversation={handleNewConversation}
      />
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

      <style jsx global>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0); }
          40% { transform: scale(1); }
        }
      `}</style>
    </div>
  );
}
