'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Toast, Swiper, Dialog } from 'antd-mobile';
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
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  html = html.replace(/^### (.+)$/gm, '<h3 style="font-size:15px;font-weight:700;margin:8px 0 4px">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 style="font-size:16px;font-weight:700;margin:8px 0 4px">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 style="font-size:17px;font-weight:700;margin:8px 0 4px">$1</h1>');
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

  const [recommendQuestions] = useState<{ tag: string; text: string }[]>([
    { tag: '健康', text: '最近总是失眠怎么办？' },
    { tag: '体检', text: '帮我解读最新体检报告' },
    { tag: '用药', text: '感冒了吃什么药比较好？' },
    { tag: '饮食', text: '高血压患者饮食注意什么？' },
  ]);

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
  }, []);

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
    try {
      const body: any = {};
      if (selectedConsultant) body.member_id = selectedConsultant.id;
      const res: any = await api.post('/api/chat/sessions', body);
      const data = res.data || res;
      const newId = String(data.id || data.session_id);
      setSessionId(newId);
      return newId;
    } catch {
      return null;
    }
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

  // Voice recording
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      const audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

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
        stream.getTracks().forEach(t => t.stop());
        audioCtx.close();

        if (recordCancelled) {
          setRecordCancelled(false);
          return;
        }

        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        if (blob.size < 1000) {
          Toast.show({ content: '录音时间太短' });
          return;
        }

        Toast.show({ content: '语音识别中...', icon: 'loading' });
        try {
          const formData = new FormData();
          formData.append('audio', blob, 'voice.webm');
          const token = localStorage.getItem('token');
          const resp = await fetch(`${basePath}/api/tts/synthesize`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData,
          });
          const result = await resp.json();
          Toast.clear();
          if (result.text) {
            handleSend(result.text);
          } else {
            Toast.show({ content: '无法识别语音，请重试' });
          }
        } catch {
          Toast.clear();
          Toast.show({ content: '语音识别失败' });
        }
      };

      recorder.start();
      setRecording(true);
      setRecordCancelled(false);
    } catch {
      Toast.show({ content: '无法访问麦克风' });
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

  // TTS
  const handleTTS = async (text: string) => {
    if (ttsPlaying) {
      ttsAudioRef.current?.pause();
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      setTtsPlaying(false);
      return;
    }

    setTtsPlaying(true);
    try {
      const token = localStorage.getItem('token');
      const resp = await fetch(`${basePath}/api/tts/synthesize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ text }),
      });

      if (resp.ok && resp.headers.get('content-type')?.includes('audio')) {
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        ttsAudioRef.current = audio;
        audio.onended = () => {
          setTtsPlaying(false);
          URL.revokeObjectURL(url);
        };
        audio.onerror = () => {
          setTtsPlaying(false);
          fallbackTTS(text);
        };
        audio.play();
      } else {
        fallbackTTS(text);
      }
    } catch {
      fallbackTTS(text);
    }
  };

  const fallbackTTS = (text: string) => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = 'zh-CN';
      utter.onend = () => setTtsPlaying(false);
      utter.onerror = () => setTtsPlaying(false);
      window.speechSynthesis.speak(utter);
    } else {
      setTtsPlaying(false);
      Toast.show({ content: '当前浏览器不支持语音播报' });
    }
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

  return (
    <div className="flex flex-col h-screen" style={{ background: THEME.background, maxWidth: 750, margin: '0 auto' }}>
      {/* Top Bar */}
      <div
        className="flex items-center justify-between px-4 flex-shrink-0"
        style={{ height: 48, background: THEME.cardBg, borderBottom: `1px solid ${THEME.divider}` }}
      >
        <div className="flex items-center gap-3">
          <button className="text-xl" onClick={() => setSidebarOpen(true)}>☰</button>
          <span className="font-bold text-base" style={{ color: THEME.textPrimary }}>AI 健康助手</span>
        </div>
        <button className="text-xl tracking-widest" onClick={() => setMoreMenuOpen(true)}>···</button>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        {!hasConversation ? (
          <div className="px-4 py-6">
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
                我是您的AI健康助手
              </div>
            </div>

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

            <div className="grid grid-cols-3 gap-3 mb-5">
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

            <div className="mb-3">
              <div className="text-sm font-semibold mb-2" style={{ color: THEME.textPrimary }}>试着问我</div>
              <div className="space-y-2">
                {recommendQuestions.map((q, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 px-4 py-3 rounded-xl cursor-pointer active:opacity-70"
                    style={{ background: THEME.cardBg, border: `1px solid ${THEME.divider}` }}
                    onClick={() => handleSend(q.text)}
                  >
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: THEME.primaryLight, color: THEME.primary }}>
                      {q.tag}
                    </span>
                    <span className="text-sm" style={{ color: THEME.textPrimary }}>{q.text}</span>
                  </div>
                ))}
              </div>
            </div>
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

      {/* Bottom Quick Tags (only in guide state) */}
      {!hasConversation && funcButtons.length > 0 && (
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
              onClick={() => setVoiceMode(false)}
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
            {voiceSupported && (
              <button
                className="flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-full mb-0"
                style={{ background: THEME.primaryLight, color: THEME.primary }}
                onClick={() => setVoiceMode(true)}
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
                placeholder="问问健康助手..."
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
            <button
              className="flex-shrink-0 flex items-center justify-center rounded-full text-sm font-medium mb-0"
              style={{
                width: 40,
                height: 40,
                background: inputValue.trim() ? THEME.primary : THEME.divider,
                color: '#fff',
                transition: 'background 0.2s',
              }}
              onClick={() => handleSend()}
              disabled={!inputValue.trim() || sending}
            >
              ➤
            </button>
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
