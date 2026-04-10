'use client';

import { useState, useRef, useEffect, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Toast, SpinLoading } from 'antd-mobile';
import api from '@/lib/api';

interface CallMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

interface VadConfig {
  silence_threshold: number;
  silence_duration_ms: number;
  min_speech_ms: number;
}

const DEFAULT_VAD: VadConfig = {
  silence_threshold: 30,
  silence_duration_ms: 1500,
  min_speech_ms: 500,
};

function DigitalHumanCallInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const dhId = searchParams.get('dhId') || '';
  const sessionId = searchParams.get('sessionId') || '';

  const [callId, setCallId] = useState<string | null>(null);
  const [messages, setMessages] = useState<CallMessage[]>([]);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [online, setOnline] = useState(true);
  const [micGranted, setMicGranted] = useState<boolean | null>(null);
  const [slideIn, setSlideIn] = useState(false);
  const [slideOut, setSlideOut] = useState(false);
  const [currentAiText, setCurrentAiText] = useState('');
  const [videoLoaded, setVideoLoaded] = useState(false);

  const silentVideoRef = useRef<HTMLVideoElement>(null);
  const speakVideoRef = useRef<HTMLVideoElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const vadTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const animFrameRef = useRef<number>(0);
  const audioChunksRef = useRef<Blob[]>([]);
  const vadConfigRef = useRef<VadConfig>(DEFAULT_VAD);
  const callIdRef = useRef<string | null>(null);
  const endedRef = useRef(false);
  const synthRef = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    requestAnimationFrame(() => setSlideIn(true));
  }, []);

  // Network monitoring
  useEffect(() => {
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    setOnline(navigator.onLine);
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);

  // Scroll chat to bottom
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, currentAiText]);

  // Fetch VAD config
  useEffect(() => {
    api.get('/api/chat/voice-service/vad-config')
      .then((res: any) => {
        const d = res.data || res;
        vadConfigRef.current = {
          silence_threshold: d.silence_threshold ?? DEFAULT_VAD.silence_threshold,
          silence_duration_ms: d.silence_duration_ms ?? DEFAULT_VAD.silence_duration_ms,
          min_speech_ms: d.min_speech_ms ?? DEFAULT_VAD.min_speech_ms,
        };
      })
      .catch(() => {});
  }, []);

  const cleanup = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = 0;
    }
    if (vadTimerRef.current) {
      clearTimeout(vadTimerRef.current);
      vadTimerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try { mediaRecorderRef.current.stop(); } catch {}
    }
    mediaRecorderRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      try { audioCtxRef.current.close(); } catch {}
    }
    audioCtxRef.current = null;
    analyserRef.current = null;
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  }, []);

  useEffect(() => {
    return () => { cleanup(); };
  }, [cleanup]);

  // Request mic permission and start call
  useEffect(() => {
    const init = async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        setMicGranted(false);
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(t => t.stop());
        setMicGranted(true);
      } catch {
        setMicGranted(false);
      }
    };
    init();
  }, []);

  // Start call once mic is granted
  useEffect(() => {
    if (micGranted !== true || callIdRef.current) return;
    const startCall = async () => {
      try {
        const res: any = await api.post('/api/chat/voice-call/start', {
          digital_human_id: dhId ? parseInt(dhId) : undefined,
          chat_session_id: sessionId ? parseInt(sessionId) : undefined,
        });
        const d = res.data || res;
        const id = String(d.id || d.call_id || '');
        setCallId(id);
        callIdRef.current = id;
        setMessages([{
          id: 'welcome',
          role: 'assistant',
          content: '您好，我是您的AI健康顾问，请问有什么可以帮您？',
        }]);
        startListening();
      } catch {
        Toast.show({ content: '通话连接失败，请重试', icon: 'fail' });
      }
    };
    startCall();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [micGranted]);

  const speakText = useCallback((text: string) => {
    if (!window.speechSynthesis) return;
    setIsSpeaking(true);

    // Typewriter effect
    let charIdx = 0;
    setCurrentAiText('');
    const typeInterval = setInterval(() => {
      charIdx++;
      setCurrentAiText(text.slice(0, charIdx));
      if (charIdx >= text.length) clearInterval(typeInterval);
    }, 50);

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'zh-CN';
    utterance.rate = 1;
    synthRef.current = utterance;

    utterance.onend = () => {
      clearInterval(typeInterval);
      setCurrentAiText('');
      setIsSpeaking(false);
      setMessages((prev) => [...prev, { id: `ai-${Date.now()}`, role: 'assistant', content: text }]);
      if (!endedRef.current) startListening();
    };
    utterance.onerror = () => {
      clearInterval(typeInterval);
      setCurrentAiText('');
      setIsSpeaking(false);
      setMessages((prev) => [...prev, { id: `ai-${Date.now()}`, role: 'assistant', content: text }]);
      if (!endedRef.current) startListening();
    };

    window.speechSynthesis.speak(utterance);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sendVoiceMessage = useCallback(async (text: string) => {
    if (!text.trim() || !callIdRef.current) return;
    setMessages((prev) => [...prev, { id: `user-${Date.now()}`, role: 'user', content: text }]);

    try {
      const res: any = await api.post(`/api/chat/voice-call/${callIdRef.current}/message`, {
        user_text: text,
      });
      const d = res.data || res;
      const reply = d.ai_text || d.content || '抱歉，我没有听清楚，请再说一次。';
      speakText(reply);
    } catch {
      speakText('网络异常，请稍后再试。');
    }
  }, [speakText]);

  const stopListening = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = 0;
    }
    if (vadTimerRef.current) {
      clearTimeout(vadTimerRef.current);
      vadTimerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try { mediaRecorderRef.current.stop(); } catch {}
    }
    setIsListening(false);
  }, []);

  const startListening = useCallback(async () => {
    if (endedRef.current) return;
    audioChunksRef.current = [];
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

      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(t => t.stop());
          streamRef.current = null;
        }
        setIsListening(false);
      };

      recorder.start(250);
      setIsListening(true);

      // VAD: detect silence
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      let speechDetected = false;
      let silenceStart = 0;
      const speechStartTime = Date.now();

      const checkVad = () => {
        if (!analyserRef.current || endedRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length;

        const cfg = vadConfigRef.current;
        if (avg > cfg.silence_threshold) {
          speechDetected = true;
          silenceStart = 0;
          if (vadTimerRef.current) {
            clearTimeout(vadTimerRef.current);
            vadTimerRef.current = null;
          }
        } else if (speechDetected) {
          if (!silenceStart) silenceStart = Date.now();
          const elapsed = Date.now() - speechStartTime;
          if (
            elapsed >= cfg.min_speech_ms &&
            Date.now() - silenceStart >= cfg.silence_duration_ms
          ) {
            // Speech ended – send to backend via text (simplified STT)
            stopListening();
            const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
            // Simplified: use ASR endpoint then send text
            const fd = new FormData();
            fd.append('audio_file', blob, 'recording.webm');
            fd.append('format', 'webm');
            fd.append('sample_rate', '16000');
            api.post('/api/search/asr/recognize', fd, {
              headers: { 'Content-Type': 'multipart/form-data' },
              timeout: 30000,
            })
              .then((asrRes: any) => {
                const text = asrRes?.data?.text || asrRes?.text || '';
                const clean = text.replace(/[^\u4e00-\u9fa5a-zA-Z0-9\s]/g, '').trim();
                if (clean) {
                  sendVoiceMessage(clean);
                } else {
                  if (!endedRef.current) startListening();
                }
              })
              .catch(() => {
                if (!endedRef.current) startListening();
              });
            return;
          }
        }
        animFrameRef.current = requestAnimationFrame(checkVad);
      };
      animFrameRef.current = requestAnimationFrame(checkVad);
    } catch {
      setIsListening(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sendVoiceMessage, stopListening]);

  const endCall = useCallback(async () => {
    endedRef.current = true;
    cleanup();
    if (callIdRef.current) {
      try {
        await api.post(`/api/chat/voice-call/${callIdRef.current}/end`, {
          dialog_content: messages.map(m => ({ role: m.role, content: m.content })),
        });
      } catch {}
    }
    setSlideOut(true);
    setTimeout(() => {
      if (sessionId) {
        router.push(`/chat/${sessionId}`);
      } else {
        router.back();
      }
    }, 350);
  }, [cleanup, router, sessionId]);

  // Mic permission denied screen
  if (micGranted === false) {
    return (
      <div className="fixed inset-0 bg-black flex flex-col items-center justify-center z-50 text-white">
        <div className="text-6xl mb-6">🎤</div>
        <div className="text-lg font-medium mb-2">需要麦克风权限</div>
        <div className="text-sm text-gray-400 mb-8 text-center px-8">
          数字人通话需要使用麦克风，请在浏览器设置中开启麦克风权限后重试。
        </div>
        <button
          onClick={() => router.back()}
          className="px-8 py-3 rounded-full text-white font-medium"
          style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
        >
          返回
        </button>
      </div>
    );
  }

  return (
    <div
      className="fixed inset-0 bg-black z-50 flex flex-col overflow-hidden"
      style={{
        transform: slideOut ? 'translateY(100%)' : slideIn ? 'translateY(0)' : 'translateY(100%)',
        transition: 'transform 0.35s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
    >
      {/* Full-screen video background */}
      <div className="absolute inset-0">
        <video
          ref={silentVideoRef}
          className="absolute inset-0 w-full h-full"
          style={{
            objectFit: 'cover',
            opacity: isSpeaking ? 0 : 1,
            transition: 'opacity 0.3s',
          }}
          src={`/videos/digital-human-silent.mp4`}
          autoPlay
          loop
          muted
          playsInline
          onLoadedData={() => setVideoLoaded(true)}
          onError={() => setVideoLoaded(true)}
        />
        <video
          ref={speakVideoRef}
          className="absolute inset-0 w-full h-full"
          style={{
            objectFit: 'cover',
            opacity: isSpeaking ? 1 : 0,
            transition: 'opacity 0.3s',
          }}
          src={`/videos/digital-human-speaking.mp4`}
          autoPlay
          loop
          muted
          playsInline
        />
        {!videoLoaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-black">
            <div className="text-white text-sm">加载中...</div>
          </div>
        )}
      </div>

      {/* Network offline toast */}
      {!online && (
        <div
          className="absolute top-12 left-1/2 -translate-x-1/2 z-30 px-5 py-2 rounded-full text-sm text-white font-medium"
          style={{ background: 'rgba(255,77,79,0.85)', backdropFilter: 'blur(8px)' }}
        >
          网络连接中...
        </div>
      )}

      {/* Listening indicator */}
      {isListening && (
        <div className="absolute top-12 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 px-4 py-2 rounded-full"
          style={{ background: 'rgba(82,196,26,0.8)', backdropFilter: 'blur(8px)' }}
        >
          <span className="inline-block w-2 h-2 rounded-full bg-white animate-pulse" />
          <span className="text-white text-sm">聆听中...</span>
        </div>
      )}

      {/* Chat bubble area - bottom 1/4 */}
      <div className="absolute bottom-28 left-0 right-0 z-10" style={{ height: '25vh' }}>
        <div
          className="h-full px-4 pt-4 pb-2 overflow-y-auto"
          ref={chatScrollRef}
          style={{
            background: 'linear-gradient(to bottom, transparent, rgba(0,0,0,0.6) 20%)',
            maskImage: 'linear-gradient(to bottom, transparent 0%, black 20%)',
            WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 20%)',
          }}
        >
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex mb-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className="max-w-[80%] px-3 py-2 rounded-2xl text-sm leading-relaxed"
                style={
                  msg.role === 'user'
                    ? { background: 'rgba(82,196,26,0.85)', color: '#fff', borderBottomRightRadius: 4 }
                    : { background: 'rgba(255,255,255,0.9)', color: '#333', borderBottomLeftRadius: 4 }
                }
              >
                {msg.content}
              </div>
            </div>
          ))}

          {/* AI typewriter text */}
          {currentAiText && (
            <div className="flex mb-3 justify-start">
              <div
                className="max-w-[80%] px-3 py-2 rounded-2xl text-sm leading-relaxed"
                style={{ background: 'rgba(255,255,255,0.9)', color: '#333', borderBottomLeftRadius: 4 }}
              >
                {currentAiText}
                <span className="inline-block w-0.5 h-4 bg-gray-500 ml-0.5 animate-pulse" />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Hang up button */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-20">
        <button
          onClick={endCall}
          className="flex items-center justify-center rounded-full shadow-lg active:scale-95 transition-transform"
          style={{
            width: 60,
            height: 60,
            background: '#ff4d4f',
            border: 'none',
          }}
          aria-label="挂断通话"
        >
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M23 16.92a3.07 3.07 0 0 1-3.07 3.07h-1.86a3.07 3.07 0 0 1-3.07-3.07v-1.86a9.9 9.9 0 0 0-6 0v1.86A3.07 3.07 0 0 1 5.93 20H4.07A3.07 3.07 0 0 1 1 16.92v-.93A14 14 0 0 1 12 2a14 14 0 0 1 11 14v.92z" />
            <line x1="1" y1="1" x2="23" y2="23" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export default function DigitalHumanCallPage() {
  return (
    <Suspense fallback={<div className="fixed inset-0 bg-black flex items-center justify-center"><SpinLoading style={{ '--color': '#fff' } as React.CSSProperties} /></div>}>
      <DigitalHumanCallInner />
    </Suspense>
  );
}
