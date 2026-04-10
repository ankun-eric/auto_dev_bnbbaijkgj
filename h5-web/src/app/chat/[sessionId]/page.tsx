'use client';

import { useState, useRef, useEffect, useCallback, Suspense } from 'react';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import { NavBar, Input, SpinLoading, Toast, Popup, Tag, DatePicker, Dialog } from 'antd-mobile';
import api from '@/lib/api';
import { useAuth } from '@/lib/auth';
import ChatSidebar from '@/components/ChatSidebar';
import KnowledgeCard, { type KnowledgeHit } from '@/components/KnowledgeCard';

interface FunctionButton {
  id: string;
  name: string;
  button_type: 'digital_human_call' | 'photo_upload' | 'file_upload' | 'ai_dialog_trigger' | 'external_link';
  params: Record<string, any>;
}

const BUTTON_EMOJI: Record<string, string> = {
  digital_human_call: '📞',
  photo_upload: '📷',
  file_upload: '📄',
  external_link: '🔗',
};

const AI_TRIGGER_EMOJI: Record<string, string> = {
  '症状自查': '🩺',
  '用药提醒': '💊',
  '健康日记': '📝',
  '预约挂号': '🏥',
  '急救指南': '🚑',
};

const AI_TRIGGER_MSG: Record<string, string> = {
  '症状自查': '我想进行症状自查',
  '用药提醒': '我要设置用药提醒',
  '健康日记': '我想写健康日记',
  '预约挂号': '我想预约挂号',
  '急救指南': '我需要急救指南',
};

let _btnCache: { data: FunctionButton[]; ts: number } | null = null;
const BTN_CACHE_TTL = 5 * 60 * 1000;

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
  is_self?: boolean;
  relation_type_name?: string;
}

interface RelationType {
  id: number;
  name: string;
  sort_order: number;
}

const RELATION_EMOJI: Record<string, string> = {
  '本人': '👤',
  '爸爸': '👨',
  '妈妈': '👩',
  '老公': '👨‍❤️‍👨',
  '老婆': '👩‍❤️‍👩',
  '儿子': '👦',
  '女儿': '👧',
  '哥哥': '👱‍♂️',
  '弟弟': '🧑',
  '姐姐': '👱‍♀️',
  '妹妹': '👧',
  '爷爷': '👴',
  '奶奶': '👵',
  '外公': '👴',
  '外婆': '👵',
  '其他': '🧑',
  '父亲': '👨',
  '母亲': '👩',
  '配偶': '💑',
  '子女': '👧',
  '兄弟姐妹': '👫',
  '祖父母': '👴',
  '外祖父母': '👵',
};

function getMemberEmoji(relationName: string): string {
  return RELATION_EMOJI[relationName] || '🧑';
}

function getRelationColor(relationName: string): string {
  if (relationName === '本人') return '#52c41a';
  if (['爸爸', '妈妈', '父亲', '母亲'].includes(relationName)) return '#1890ff';
  if (['儿子', '女儿', '子女'].includes(relationName)) return '#eb2f96';
  if (['爷爷', '奶奶', '外公', '外婆', '祖父母', '外祖父母'].includes(relationName)) return '#fa8c16';
  return '#8c8c8c';
}

const ADD_MEDICAL_OPTIONS = ['高血压', '糖尿病', '心脏病', '哮喘', '甲状腺疾病', '肝病', '肾病', '痛风'];
const ADD_ALLERGY_OPTIONS = ['青霉素', '花粉', '海鲜', '牛奶', '尘螨', '坚果', '磺胺类', '头孢类'];

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
  const [currentRelationLabel, setCurrentRelationLabel] = useState('本人');

  // Add member popup state (two-step)
  const [addMemberPopupVisible, setAddMemberPopupVisible] = useState(false);
  const [relationTypes, setRelationTypes] = useState<RelationType[]>([]);
  const [addStep, setAddStep] = useState<'relation' | 'info'>('relation');
  const [selectedRelation, setSelectedRelation] = useState<RelationType | null>(null);
  const [newNickname, setNewNickname] = useState('');
  const [newGender, setNewGender] = useState('');
  const [newBirthday, setNewBirthday] = useState('');
  const [newHeight, setNewHeight] = useState('');
  const [newWeight, setNewWeight] = useState('');
  const [newMedicalHistories, setNewMedicalHistories] = useState<string[]>([]);
  const [newMedicalOther, setNewMedicalOther] = useState('');
  const [newAllergies, setNewAllergies] = useState<string[]>([]);
  const [newAllergyOther, setNewAllergyOther] = useState('');
  const [addLoading, setAddLoading] = useState(false);
  const [newBirthdayPickerVisible, setNewBirthdayPickerVisible] = useState(false);

  // Function buttons
  const [funcButtons, setFuncButtons] = useState<FunctionButton[]>([]);
  const funcScrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const photoInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (_btnCache && Date.now() - _btnCache.ts < BTN_CACHE_TTL) {
      setFuncButtons(_btnCache.data);
      return;
    }
    api.get('/api/chat/function-buttons')
      .then((res: any) => {
        const data = res.data || res;
        const items: FunctionButton[] = Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : [];
        _btnCache = { data: items, ts: Date.now() };
        setFuncButtons(items);
      })
      .catch(() => {});
  }, []);

  const getFuncBtnEmoji = (btn: FunctionButton) => {
    if (btn.button_type === 'ai_dialog_trigger') {
      for (const key of Object.keys(AI_TRIGGER_EMOJI)) {
        if (btn.name.includes(key)) return AI_TRIGGER_EMOJI[key];
      }
      return '💬';
    }
    return BUTTON_EMOJI[btn.button_type] || '🔗';
  };

  const handleFuncBtnClick = (btn: FunctionButton) => {
    switch (btn.button_type) {
      case 'digital_human_call':
        router.push(`/digital-human-call?dhId=${btn.params.digital_human_id || ''}&sessionId=${sessionId}`);
        break;
      case 'photo_upload':
        photoInputRef.current?.click();
        break;
      case 'file_upload':
        fileInputRef.current?.click();
        break;
      case 'ai_dialog_trigger': {
        let triggerMsg = '';
        for (const key of Object.keys(AI_TRIGGER_MSG)) {
          if (btn.name.includes(key)) { triggerMsg = AI_TRIGGER_MSG[key]; break; }
        }
        if (!triggerMsg) triggerMsg = btn.name;
        sendMessageText(triggerMsg);
        break;
      }
      case 'external_link':
        if (btn.params.url) window.open(btn.params.url, '_blank');
        break;
    }
  };

  const handleFileUpload = async (file: File, type: 'photo' | 'file') => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('message_type', type === 'photo' ? 'image' : 'file');
    try {
      Toast.show({ icon: 'loading', content: '上传中...', duration: 0 });
      const res: any = await api.post(`/api/chat/sessions/${sessionId}/messages`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });
      Toast.clear();
      const resData = res.data || res;
      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: type === 'photo' ? `[图片] ${file.name}` : `[文件] ${file.name}`,
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      };
      const aiMsg: Message = {
        id: resData.id != null ? String(resData.id) : `ai-${Date.now()}`,
        role: 'assistant',
        content: resData.content || '已收到您上传的内容。',
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, userMsg, aiMsg]);
    } catch {
      Toast.clear();
      Toast.show({ content: '上传失败，请重试', icon: 'fail' });
    }
  };

  // Voice input state
  const [voiceMode, setVoiceMode] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingOverlayVisible, setRecordingOverlayVisible] = useState(false);
  const [isCancelZone, setIsCancelZone] = useState(false);
  const [volumeBars, setVolumeBars] = useState<number[]>([0, 0, 0, 0, 0]);
  const [isRecognizing, setIsRecognizing] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number>(0);
  const recordStartTimeRef = useRef<number>(0);
  const maxRecordTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const touchStartYRef = useRef<number>(0);
  const mimeTypeRef = useRef('');
  const cancelledRef = useRef(false);

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

  const cleanupRecording = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = 0;
    }
    if (maxRecordTimerRef.current) {
      clearTimeout(maxRecordTimerRef.current);
      maxRecordTimerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try { mediaRecorderRef.current.stop(); } catch { /* ignore */ }
    }
    mediaRecorderRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      try { audioCtxRef.current.close(); } catch { /* ignore */ }
    }
    audioCtxRef.current = null;
    analyserRef.current = null;
  }, []);

  useEffect(() => {
    return () => { cleanupRecording(); };
  }, [cleanupRecording]);

  const sendToAsr = useCallback(async (blob: Blob) => {
    setIsRecognizing(true);
    try {
      const fd = new FormData();
      const fmt = mimeToFormat(mimeTypeRef.current);
      fd.append('audio_file', blob, `recording.${fmt}`);
      fd.append('format', fmt);
      fd.append('sample_rate', '16000');
      const data: any = await api.post('/api/search/asr/recognize', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000,
      });
      setIsRecognizing(false);
      setRecordingOverlayVisible(false);
      const text = data?.data?.text || data?.text || '';
      const cleanText = text.replace(/[\u3002\uff1b\uff0c\uff1a\u201c\u201d\u2018\u2019\uff08\uff09\u3001\uff1f\u300a\u300b\uff01\u3010\u3011\u2026\u2014\uff5e\u00b7.,!?;:'"()\[\]{}\-_\/\\@#\$%\^&\*\+=~`<>]/g, '').trim();
      if (!cleanText) {
        Toast.show({ content: '未识别到语音内容，请重试', icon: 'fail', duration: 2000 });
        return;
      }
      sendMessageText(cleanText);
    } catch {
      setIsRecognizing(false);
      setRecordingOverlayVisible(false);
      Toast.show({ content: '语音服务暂不可用，已切换为键盘输入', icon: 'fail', duration: 2500 });
      setVoiceMode(false);
    }
  }, []);

  const startRecording = useCallback(async () => {
    audioChunksRef.current = [];
    cancelledRef.current = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const mime = getPreferredMimeType();
      mimeTypeRef.current = mime;
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        if (animFrameRef.current) {
          cancelAnimationFrame(animFrameRef.current);
          animFrameRef.current = 0;
        }
        if (maxRecordTimerRef.current) {
          clearTimeout(maxRecordTimerRef.current);
          maxRecordTimerRef.current = null;
        }
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(t => t.stop());
          streamRef.current = null;
        }

        setIsRecording(false);
        setVolumeBars([0, 0, 0, 0, 0]);

        if (cancelledRef.current) {
          setRecordingOverlayVisible(false);
          return;
        }

        const elapsed = (Date.now() - recordStartTimeRef.current) / 1000;
        if (elapsed < 0.5) {
          setRecordingOverlayVisible(false);
          Toast.show({ content: '录音时间太短', duration: 1500 });
          return;
        }

        const blob = new Blob(audioChunksRef.current, { type: mime || 'audio/webm' });
        sendToAsr(blob);
      };

      recorder.start(250);
      recordStartTimeRef.current = Date.now();
      setIsRecording(true);
      setRecordingOverlayVisible(true);
      setIsCancelZone(false);

      maxRecordTimerRef.current = setTimeout(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
          mediaRecorderRef.current.stop();
        }
      }, 30000);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const updateBars = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        const barCount = 5;
        const step = Math.floor(dataArray.length / barCount);
        const bars: number[] = [];
        for (let i = 0; i < barCount; i++) {
          let sum = 0;
          for (let j = 0; j < step; j++) sum += dataArray[i * step + j];
          bars.push(Math.min(1, (sum / step) / 180));
        }
        setVolumeBars(bars);
        animFrameRef.current = requestAnimationFrame(updateBars);
      };
      animFrameRef.current = requestAnimationFrame(updateBars);
    } catch {
      cleanupRecording();
      setIsRecording(false);
      setRecordingOverlayVisible(false);
      Toast.show({ content: '录音启动失败，请重试', icon: 'fail' });
    }
  }, [sendToAsr, cleanupRecording]);

  const handleVoiceTouchStart = useCallback((e: React.TouchEvent) => {
    e.preventDefault();
    touchStartYRef.current = e.touches[0].clientY;
    setIsCancelZone(false);
    startRecording();
  }, [startRecording]);

  const handleVoiceTouchMove = useCallback((e: React.TouchEvent) => {
    const diff = touchStartYRef.current - e.touches[0].clientY;
    setIsCancelZone(diff > 80);
  }, []);

  const handleVoiceTouchEnd = useCallback(() => {
    if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') return;
    if (isCancelZone) {
      cancelledRef.current = true;
    }
    mediaRecorderRef.current.stop();
  }, [isCancelZone]);

  const checkMicPermission = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      Toast.show({ content: '当前浏览器不支持语音输入', icon: 'fail' });
      return;
    }
    try {
      if (navigator.permissions) {
        const permStatus = await navigator.permissions.query({ name: 'microphone' as PermissionName });
        if (permStatus.state === 'granted') {
          setVoiceMode(true);
          return;
        }
        if (permStatus.state === 'denied') {
          Toast.show({ content: '麦克风权限已被禁止，请在系统设置中开启', icon: 'fail', duration: 2500 });
          return;
        }
      }
      const result = await Dialog.confirm({
        title: '允许访问麦克风',
        content: '请授权麦克风，以便AI发送语音消息',
        confirmText: '去授权',
        cancelText: '取消',
      });
      if (!result) return;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(t => t.stop());
      setVoiceMode(true);
    } catch {
      Toast.show({ content: '请在设置中开启麦克风权限', icon: 'fail', duration: 2500 });
    }
  }, []);

  const handleMicToggle = useCallback(() => {
    if (voiceMode) {
      setVoiceMode(false);
      return;
    }
    checkMicPermission();
  }, [voiceMode, checkMicPermission]);

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
    if (!isSymptom || !urlMsg || autoSentRef.current) return;
    const timer = setTimeout(() => {
      if (autoSentRef.current) return;
      autoSentRef.current = true;
      sendMessageText(urlMsg);
    }, 300);
    return () => clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSymptom, urlMsg]);

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

  const fetchMemberList = async () => {
    try {
      const res: any = await api.get('/api/family/members');
      const data = res.data || res;
      setFamilyMembers(Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : []);
    } catch {
      setFamilyMembers([]);
    }
  };

  const openMemberPopup = async () => {
    await fetchMemberList();
    setMemberPopupVisible(true);
  };

  const handleSwitchMember = async (memberId: number | null, label: string, relationName: string) => {
    setSwitchingMember(true);
    try {
      await api.post(`/api/chat/sessions/${sessionId}/switch-member`, {
        family_member_id: memberId,
      });
      setCurrentRelationLabel(relationName);
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

  // Add member popup functions
  const fetchRelationTypes = async () => {
    try {
      const res: any = await api.get('/api/relation-types');
      const data = res.data || res;
      const items = Array.isArray(data.items) ? data.items : [];
      setRelationTypes(items.filter((rt: any) => rt.name !== '本人'));
    } catch {
      setRelationTypes([]);
    }
  };

  const openAddMemberPopup = async () => {
    setAddStep('relation');
    setSelectedRelation(null);
    setNewNickname('');
    setNewGender('');
    setNewBirthday('');
    setNewHeight('');
    setNewWeight('');
    setNewMedicalHistories([]);
    setNewMedicalOther('');
    setNewAllergies([]);
    setNewAllergyOther('');
    await fetchRelationTypes();
    setAddMemberPopupVisible(true);
  };

  const handleAddMemberConfirm = async () => {
    if (!selectedRelation || !newNickname.trim() || !newGender || !newBirthday) {
      Toast.show({ content: '请填写完整的成员信息' });
      return;
    }
    setAddLoading(true);
    try {
      const body: any = {
        nickname: newNickname.trim(),
        name: newNickname.trim(),
        relationship_type: selectedRelation.name,
        relation_type_id: selectedRelation.id,
        gender: newGender,
        birthday: newBirthday,
      };
      if (newHeight) body.height = Number(newHeight);
      if (newWeight) body.weight = Number(newWeight);
      const medicals = [...newMedicalHistories];
      if (newMedicalOther.trim()) medicals.push(newMedicalOther.trim());
      if (medicals.length) body.medical_histories = medicals;
      const allergies = [...newAllergies];
      if (newAllergyOther.trim()) allergies.push(newAllergyOther.trim());
      if (allergies.length) body.allergies = allergies;

      await api.post('/api/family/members', body);
      setAddMemberPopupVisible(false);
      await fetchMemberList();
      Toast.show({ content: '成员添加成功', icon: 'success' });
    } catch {
      Toast.show({ content: '添加失败，请重试', icon: 'fail' });
    }
    setAddLoading(false);
  };

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

      {/* Hidden file inputs for photo/file upload */}
      <input
        ref={photoInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleFileUpload(f, 'photo');
          e.target.value = '';
        }}
      />
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,.pdf,.doc,.docx,.xls,.xlsx"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleFileUpload(f, 'file');
          e.target.value = '';
        }}
      />

      {/* Function buttons bar */}
      {funcButtons.length > 0 && (
        <div className="bg-white border-t border-gray-100" style={{ position: 'relative' }}>
          <div
            ref={funcScrollRef}
            className="flex items-center gap-3 overflow-x-auto px-3 py-2 no-scrollbar"
            style={{ scrollBehavior: 'smooth', WebkitOverflowScrolling: 'touch', height: 64 }}
          >
            {funcButtons.map((btn) => (
              <button
                key={btn.id}
                onClick={() => handleFuncBtnClick(btn)}
                className="flex items-center gap-1.5 flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-all active:scale-95"
                style={{
                  background: '#f5f5f5',
                  border: '1px solid #e8e8e8',
                  color: '#333',
                  whiteSpace: 'nowrap',
                }}
              >
                <span style={{ fontSize: 16 }}>{getFuncBtnEmoji(btn)}</span>
                <span>{btn.name}</span>
              </button>
            ))}
          </div>
          <div style={{
            position: 'absolute', right: 0, top: 0, bottom: 0, width: 32,
            background: 'linear-gradient(to right, transparent, white)',
            pointerEvents: 'none',
          }} />
          <div style={{
            position: 'absolute', left: 0, top: 0, bottom: 0, width: 32,
            background: 'linear-gradient(to left, transparent, white)',
            pointerEvents: 'none',
          }} />
        </div>
      )}

      <div className="bg-white border-t border-gray-100 px-3 py-3 flex items-end gap-2 safe-area-bottom">
        <button
          onClick={openMemberPopup}
          className="w-10 h-10 flex-shrink-0 flex items-center justify-center rounded-full"
          style={{ background: getRelationColor(currentRelationLabel), border: 'none' }}
          aria-label="切换咨询对象"
        >
          <span style={{ color: '#fff', fontSize: 11, fontWeight: 600, lineHeight: 1.1, textAlign: 'center' }}>
            {currentRelationLabel.length > 2 ? currentRelationLabel.slice(0, 2) : currentRelationLabel}
          </span>
        </button>

        {voiceMode ? (
          <div
            className="flex-1 rounded-2xl flex items-center justify-center select-none"
            style={{
              height: 40,
              background: isCancelZone && isRecording ? '#d32f2f' : '#52c41a',
              color: '#fff',
              fontSize: 14,
              fontWeight: 500,
              userSelect: 'none',
              WebkitUserSelect: 'none',
              touchAction: 'none',
            }}
            onTouchStart={handleVoiceTouchStart}
            onTouchMove={handleVoiceTouchMove}
            onTouchEnd={handleVoiceTouchEnd}
            onTouchCancel={handleVoiceTouchEnd}
          >
            {isRecording ? (isCancelZone ? '松开取消' : '松开结束') : '按住说话'}
          </div>
        ) : (
          <div className="flex-1 bg-gray-50 rounded-2xl px-3 py-1 flex items-center" style={{ position: 'relative' }}>
            <Input
              placeholder="发信息..."
              value={inputVal}
              onChange={setInputVal}
              onEnterPress={sendMessage}
              style={{ '--font-size': '14px', flex: 1 }}
            />
            <button
              onClick={sendMessage}
              disabled={!inputVal.trim() || loading}
              className="flex-shrink-0 flex items-center justify-center"
              style={{
                width: 32,
                height: 32,
                borderRadius: '50%',
                border: 'none',
                background: inputVal.trim() ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#e8e8e8',
                color: inputVal.trim() ? '#fff' : '#999',
                marginLeft: 4,
                cursor: inputVal.trim() ? 'pointer' : 'default',
                fontSize: 14,
              }}
            >
              ➤
            </button>
          </div>
        )}

        <button
          onClick={handleMicToggle}
          className="w-10 h-10 flex-shrink-0 flex items-center justify-center"
          aria-label={voiceMode ? '切换键盘' : '语音输入'}
        >
          {voiceMode ? (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#52c41a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="4" width="20" height="16" rx="3" ry="3" />
              <line x1="6" y1="8" x2="6" y2="8" />
              <line x1="10" y1="8" x2="10" y2="8" />
              <line x1="14" y1="8" x2="14" y2="8" />
              <line x1="18" y1="8" x2="18" y2="8" />
              <line x1="6" y1="12" x2="6" y2="12" />
              <line x1="18" y1="12" x2="18" y2="12" />
              <line x1="8" y1="16" x2="16" y2="16" />
            </svg>
          ) : (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#52c41a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          )}
        </button>
      </div>

      {/* Voice recording overlay */}
      {recordingOverlayVisible && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            background: isCancelZone ? 'rgba(180,30,30,0.6)' : 'rgba(0,0,0,0.5)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 0.2s ease',
          }}
        >
          <style dangerouslySetInnerHTML={{ __html: `
            @keyframes voice-wave-bar {
              0%, 100% { transform: scaleY(0.3); }
              50% { transform: scaleY(1); }
            }
          `}} />

          {isRecognizing ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
              <SpinLoading style={{ '--size': '40px', '--color': '#52c41a' } as React.CSSProperties} />
              <div style={{ fontSize: 16, color: '#fff', fontWeight: 500 }}>识别中...</div>
            </div>
          ) : (
            <>
              {/* Sound wave animation */}
              <div style={{
                width: 120,
                height: 120,
                borderRadius: '50%',
                background: isCancelZone ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 4,
                marginBottom: 32,
              }}>
                {volumeBars.map((v, i) => (
                  <div
                    key={i}
                    style={{
                      width: 6,
                      borderRadius: 3,
                      background: isCancelZone ? '#ff6b6b' : '#52c41a',
                      height: `${Math.max(12, v * 60)}px`,
                      transition: 'height 0.08s ease-out, background 0.2s ease',
                      animation: isRecording ? `voice-wave-bar ${0.6 + i * 0.15}s ease-in-out infinite` : 'none',
                      animationDelay: `${i * 0.1}s`,
                    }}
                  />
                ))}
              </div>

              {/* Hint text */}
              <div style={{
                fontSize: 15,
                color: '#fff',
                fontWeight: 400,
                textAlign: 'center',
              }}>
                {isCancelZone ? (
                  <span style={{ color: '#ff6b6b' }}>松开取消</span>
                ) : (
                  '松开发送，上滑取消'
                )}
              </div>
            </>
          )}
        </div>
      )}

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
            {familyMembers.map((m) => {
              const relationLabel = m.relation_type_name || m.relationship_type;
              const emoji = m.is_self ? '👤' : getMemberEmoji(relationLabel);
              const displayName = m.is_self ? '本人' : `${relationLabel} · ${m.nickname}`;
              const switchLabel = m.is_self ? '本人' : `${relationLabel}·${m.nickname}`;
              return (
                <div
                  key={m.id}
                  className="flex items-center gap-3 px-3 py-3 rounded-xl cursor-pointer"
                  style={{ background: '#f9f9f9' }}
                  onClick={() => handleSwitchMember(m.is_self ? null : m.id, switchLabel, m.is_self ? '本人' : relationLabel)}
                >
                  <div className="w-9 h-9 rounded-full flex items-center justify-center text-xl"
                    style={{ background: m.is_self ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#87d068' }}>
                    {m.is_self ? <span className="text-white text-sm">我</span> : emoji}
                  </div>
                  <div>
                    <div className="text-sm font-medium">{displayName}</div>
                  </div>
                </div>
              );
            })}

            <div
              className="flex items-center gap-3 px-3 py-3 rounded-xl cursor-pointer"
              style={{ background: '#f9f9f9' }}
              onClick={() => {
                setMemberPopupVisible(false);
                openAddMemberPopup();
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

      {/* Add member popup (two-step) */}
      <Popup
        visible={addMemberPopupVisible}
        onMaskClick={() => setAddMemberPopupVisible(false)}
        position="bottom"
        bodyStyle={{ borderRadius: '20px 20px 0 0', maxHeight: '85vh', overflowY: 'auto' }}
      >
        <div className="px-4 pb-8">
          <div className="flex items-center justify-between py-4 border-b border-gray-100">
            <span className="text-base font-bold text-gray-800">添加家庭成员</span>
            <button className="text-gray-400 text-2xl leading-none" onClick={() => setAddMemberPopupVisible(false)}>×</button>
          </div>

          <div className="mt-4">
            <div className="text-sm font-semibold text-gray-700 mb-3">选择关系</div>
            <div className="grid grid-cols-4 gap-3">
              {relationTypes.map((rt) => {
                const emoji = getMemberEmoji(rt.name);
                const isSelected = selectedRelation?.id === rt.id;
                return (
                  <button
                    key={rt.id}
                    className="flex flex-col items-center py-2 rounded-xl transition-all"
                    style={{
                      background: isSelected ? 'linear-gradient(135deg, #f6ffed, #e6fffb)' : '#f9f9f9',
                      border: isSelected ? '1.5px solid #52c41a' : '1.5px solid transparent',
                    }}
                    onClick={() => {
                      setSelectedRelation(rt);
                      setAddStep('info');
                    }}
                  >
                    <span className="text-2xl">{emoji}</span>
                    <span className="text-xs mt-1" style={{ color: isSelected ? '#52c41a' : '#555' }}>{rt.name}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {addStep === 'info' && selectedRelation && (
            <div className="mt-5 p-4 rounded-2xl" style={{ background: '#f6ffed', border: '1px solid #b7eb8f' }}>
              <div className="text-sm font-semibold mb-4" style={{ color: '#52c41a' }}>
                {getMemberEmoji(selectedRelation.name)} 填写{selectedRelation.name}信息
              </div>

              <div className="space-y-3">
                <div>
                  <div className="text-xs text-gray-500 mb-1">姓名 <span style={{color:'#ff4d4f'}}>*</span></div>
                  <input
                    className="w-full bg-white text-sm rounded-xl px-3 py-2 outline-none border border-gray-200"
                    placeholder="请输入姓名"
                    value={newNickname}
                    onChange={(e) => setNewNickname(e.target.value)}
                  />
                </div>

                <div>
                  <div className="text-xs text-gray-500 mb-1">性别 <span style={{color:'#ff4d4f'}}>*</span></div>
                  <div className="flex gap-3">
                    {['male', 'female'].map((g) => (
                      <button
                        key={g}
                        className="flex-1 py-2 rounded-xl text-sm font-medium transition-all"
                        style={{
                          background: newGender === g ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#fff',
                          color: newGender === g ? '#fff' : '#666',
                          border: `1px solid ${newGender === g ? '#52c41a' : '#e8e8e8'}`,
                        }}
                        onClick={() => setNewGender(g)}
                      >
                        {g === 'male' ? '男' : '女'}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="text-xs text-gray-500 mb-1">出生日期 <span style={{color:'#ff4d4f'}}>*</span></div>
                  <button
                    className="w-full bg-white text-sm rounded-xl px-3 py-2 text-left border border-gray-200 flex items-center justify-between"
                    onClick={() => setNewBirthdayPickerVisible(true)}
                  >
                    <span style={{ color: newBirthday ? '#333' : '#bbb' }}>{newBirthday || '请选择出生日期'}</span>
                    <span>📅</span>
                  </button>
                </div>

                <div className="flex gap-3">
                  <div className="flex-1">
                    <div className="text-xs text-gray-500 mb-1">身高 (cm)</div>
                    <input
                      type="number"
                      className="w-full bg-white text-sm rounded-xl px-3 py-2 outline-none border border-gray-200"
                      placeholder="如：170"
                      value={newHeight}
                      onChange={(e) => setNewHeight(e.target.value)}
                    />
                  </div>
                  <div className="flex-1">
                    <div className="text-xs text-gray-500 mb-1">体重 (kg)</div>
                    <input
                      type="number"
                      className="w-full bg-white text-sm rounded-xl px-3 py-2 outline-none border border-gray-200"
                      placeholder="如：65"
                      value={newWeight}
                      onChange={(e) => setNewWeight(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <div className="text-xs text-gray-500 mb-1">既往病史</div>
                  <div className="flex flex-wrap gap-2">
                    {ADD_MEDICAL_OPTIONS.map((opt) => (
                      <Tag
                        key={opt}
                        onClick={() => setNewMedicalHistories((prev) => prev.includes(opt) ? prev.filter((x) => x !== opt) : [...prev, opt])}
                        style={{
                          '--background-color': newMedicalHistories.includes(opt) ? '#52c41a' : '#fff',
                          '--text-color': newMedicalHistories.includes(opt) ? '#fff' : '#666',
                          '--border-color': newMedicalHistories.includes(opt) ? '#52c41a' : '#d9d9d9',
                          padding: '4px 10px',
                          borderRadius: 14,
                          fontSize: 12,
                          cursor: 'pointer',
                        }}
                      >
                        {opt}
                      </Tag>
                    ))}
                  </div>
                  <input
                    className="w-full bg-white text-sm rounded-xl px-3 py-2 outline-none border border-gray-200 mt-2"
                    placeholder="其他病史（可选）"
                    value={newMedicalOther}
                    onChange={(e) => setNewMedicalOther(e.target.value)}
                  />
                </div>

                <div>
                  <div className="text-xs text-gray-500 mb-1">过敏史</div>
                  <div className="flex flex-wrap gap-2">
                    {ADD_ALLERGY_OPTIONS.map((opt) => (
                      <Tag
                        key={opt}
                        onClick={() => setNewAllergies((prev) => prev.includes(opt) ? prev.filter((x) => x !== opt) : [...prev, opt])}
                        style={{
                          '--background-color': newAllergies.includes(opt) ? '#52c41a' : '#fff',
                          '--text-color': newAllergies.includes(opt) ? '#fff' : '#666',
                          '--border-color': newAllergies.includes(opt) ? '#52c41a' : '#d9d9d9',
                          padding: '4px 10px',
                          borderRadius: 14,
                          fontSize: 12,
                          cursor: 'pointer',
                        }}
                      >
                        {opt}
                      </Tag>
                    ))}
                  </div>
                  <input
                    className="w-full bg-white text-sm rounded-xl px-3 py-2 outline-none border border-gray-200 mt-2"
                    placeholder="其他过敏史（可选）"
                    value={newAllergyOther}
                    onChange={(e) => setNewAllergyOther(e.target.value)}
                  />
                </div>
              </div>

              <button
                className="w-full mt-4 py-3 rounded-2xl text-white font-semibold text-sm"
                style={{ background: addLoading ? '#d9d9d9' : 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
                disabled={addLoading}
                onClick={handleAddMemberConfirm}
              >
                {addLoading ? '添加中...' : '确认添加'}
              </button>
            </div>
          )}
        </div>
      </Popup>

      {/* New member birthday picker */}
      <DatePicker
        visible={newBirthdayPickerVisible}
        onClose={() => setNewBirthdayPickerVisible(false)}
        precision="day"
        max={new Date()}
        min={new Date('1900-01-01')}
        title="选择出生日期"
        onConfirm={(val) => {
          const d = val as Date;
          const str = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
          setNewBirthday(str);
          setNewBirthdayPickerVisible(false);
        }}
      />
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
