'use client';

/**
 * [2026-04-23] 报告解读/对比 AI 咨询页（SSE 流式）
 * 路由：/checkup/chat/[sessionId]?auto_start=1&type=report_interpret|report_compare
 */
import { useEffect, useMemo, useRef, useState, Suspense } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { NavBar, SpinLoading, Toast, ImageViewer } from 'antd-mobile';
import api from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at?: string;
}

interface ChatSession {
  id: number;
  title?: string | null;
  session_type?: string | null;
  family_member_id?: number | null;
  report_id?: number | null;
  compare_report_ids?: string | null;
  member_relation?: string | null;
}

interface ReportMini {
  id: number;
  title: string;
  file_url?: string | null;
  thumbnail_url?: string | null;
  created_at: string;
  member_name?: string | null;
  member_relation?: string | null;
}

function parseReportIdsFromSession(s: ChatSession): number[] {
  if (s.compare_report_ids) {
    return s.compare_report_ids
      .split(',')
      .map((v) => Number(v.trim()))
      .filter((n) => !!n);
  }
  if (s.report_id) return [s.report_id];
  return [];
}

function mdRender(text: string): string {
  // 简单 Markdown 渲染：标题、加粗、无序列表、换行
  if (!text) return '';
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  html = html.replace(/^## (.*)$/gm, '<h3 style="margin:14px 0 8px 0;font-size:15px;font-weight:600;color:#333">$1</h3>');
  html = html.replace(/^### (.*)$/gm, '<h4 style="margin:12px 0 6px 0;font-size:14px;font-weight:600;color:#555">$1</h4>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/(^|\n)[\-•] (.+)/g, '$1• $2');
  html = html.replace(/\n/g, '<br/>');
  return html;
}

function getBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || '';
}

function CheckupChatContent() {
  const router = useRouter();
  const params = useParams();
  const search = useSearchParams();
  const sessionId = Number(params?.sessionId);
  const autoStart = search.get('auto_start') === '1';
  const sessionType = search.get('type') || 'report_interpret';

  const [session, setSession] = useState<ChatSession | null>(null);
  const [reports, setReports] = useState<ReportMini[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [input, setInput] = useState('');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const streamingMsgRef = useRef<string>('');
  const streamedOnceRef = useRef<boolean>(false);
  const listRef = useRef<HTMLDivElement | null>(null);

  const isCompare = sessionType === 'report_compare';

  // 加载会话信息 + 消息 + 报告
  useEffect(() => {
    if (!sessionId) return;
    (async () => {
      try {
        const sess: any = await api.get(`/api/report/interpret/session/${sessionId}`);
        setSession(sess);

        // 历史消息：跳过首条 user prompt（那是我们塞的系统提示词）
        const msgResp: any = await api.get(`/api/report/interpret/session/${sessionId}/messages`);
        const raw: any[] = msgResp?.items || msgResp?.list || msgResp || [];
        // 过滤：隐藏首条 user 消息（内部提示词），仅展示 assistant 的流式结果 + 用户追问
        const mapped: Message[] = [];
        let skippedFirstUser = false;
        for (const m of raw) {
          if (!skippedFirstUser && m.role === 'user') {
            skippedFirstUser = true;
            continue;
          }
          mapped.push({
            id: String(m.id),
            role: m.role,
            content: m.content || '',
            created_at: m.created_at,
          });
        }
        setMessages(mapped);

        // 拉取报告信息
        const rids = parseReportIdsFromSession(sess);
        if (rids.length > 0) {
          const details = await Promise.all(
            rids.map((rid) =>
              api.get<any>(`/api/report/interpret/detail/${rid}`).catch(() => null)
            )
          );
          const rs: ReportMini[] = details
            .filter(Boolean)
            .map((d: any) => ({
              id: d.id,
              title: d.title,
              file_url: d.images?.[0] || null,
              thumbnail_url: d.images?.[0] || null,
              created_at: d.created_at,
              member_name: d.member_name,
              member_relation: d.member_relation,
            }));
          setReports(rs);
        }

        // 若没有 assistant 消息 && auto_start，则触发流式
        const hasAssistant = mapped.some((m) => m.role === 'assistant');
        if (autoStart && !hasAssistant && !streamedOnceRef.current) {
          streamedOnceRef.current = true;
          startStream('');
        }
      } catch (e: any) {
        Toast.show({ content: e?.message || '加载会话失败' });
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    // 滚动到底部
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, streaming]);

  async function startStream(userContent: string) {
    if (!sessionId || streaming) return;
    setStreaming(true);
    streamingMsgRef.current = '';

    // 构造 SSE 请求（fetch + ReadableStream）
    const basePath = getBasePath();
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : '';

    const headers: Record<string, string> = {
      Accept: 'text/event-stream',
    };
    if (token) headers.Authorization = `Bearer ${token}`;

    let url: string;
    let method: 'GET' | 'POST' = 'GET';
    let body: string | undefined;

    if (userContent) {
      url = `${basePath}/api/report/interpret/session/${sessionId}/chat`;
      method = 'POST';
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify({ content: userContent });
      // 同时先把用户消息加入 UI
      setMessages((prev) => [
        ...prev,
        { id: `u-${Date.now()}`, role: 'user', content: userContent },
      ]);
    } else {
      url = `${basePath}/api/report/interpret/session/${sessionId}/stream?auto_start=1`;
    }

    // UI 占位 assistant 消息
    const tmpId = `a-${Date.now()}`;
    setMessages((prev) => [...prev, { id: tmpId, role: 'assistant', content: '' }]);

    try {
      const resp = await fetch(url, { method, headers, body });
      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // 按 SSE 分片分隔符 \n\n 处理
        let idx;
        while ((idx = buffer.indexOf('\n\n')) >= 0) {
          const chunk = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          if (!chunk.startsWith('data:')) continue;
          const payload = chunk.slice(5).trim();
          try {
            const obj = JSON.parse(payload);
            if (obj.type === 'delta' && obj.content) {
              streamingMsgRef.current += obj.content;
              setMessages((prev) =>
                prev.map((m) => (m.id === tmpId ? { ...m, content: streamingMsgRef.current } : m))
              );
            } else if (obj.type === 'done') {
              const final = obj.content || streamingMsgRef.current;
              setMessages((prev) =>
                prev.map((m) => (m.id === tmpId ? { ...m, content: final } : m))
              );
            } else if (obj.type === 'error') {
              Toast.show({ content: obj.content || 'AI 服务异常' });
            }
          } catch {}
        }
      }
    } catch (e: any) {
      Toast.show({ content: e?.message || 'AI 服务请求失败' });
      setMessages((prev) =>
        prev.map((m) =>
          m.id === tmpId && !m.content
            ? { ...m, content: '抱歉，AI 服务暂时不可用，请稍后再试。' }
            : m
        )
      );
    } finally {
      setStreaming(false);
    }
  }

  const handleSend = () => {
    const text = input.trim();
    if (!text || streaming) return;
    setInput('');
    startStream(text);
  };

  // 顶部卡片数据
  const topCard = useMemo(() => {
    if (!session) return null;
    const mem = reports[0]
      ? `${reports[0].member_relation || ''} · ${reports[0].member_name || ''}`
      : '';
    if (isCompare && reports.length === 2) {
      const a = reports[0];
      const b = reports[1];
      const spanText = (() => {
        try {
          const da = new Date(a.created_at).getTime();
          const db = new Date(b.created_at).getTime();
          const months = Math.round(Math.abs(db - da) / (1000 * 60 * 60 * 24 * 30));
          if (months < 1) return '不足 1 个月';
          if (months < 12) return `${months} 个月`;
          const years = Math.floor(months / 12);
          return `${years} 年 ${months % 12} 个月`;
        } catch {
          return '';
        }
      })();
      return (
        <div style={{ background: 'linear-gradient(135deg, #fffbe6, #fff)', border: '1px solid #ffe58f', borderRadius: 10, padding: 12, margin: 12 }}>
          <div style={{ fontSize: 15, fontWeight: 600 }}>🔄 报告对比</div>
          <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>咨询对象：{mem}</div>
          <div style={{ fontSize: 12, color: '#333', marginTop: 6 }}>
            报告 A：<span style={{ color: '#1890ff' }}>{a.title}</span>
            <br />
            报告 B：<span style={{ color: '#1890ff' }}>{b.title}</span>
          </div>
          <div style={{ fontSize: 12, color: '#999', marginTop: 6 }}>时间跨度：{spanText}</div>
        </div>
      );
    }
    if (reports[0]) {
      const r = reports[0];
      return (
        <div style={{ background: 'linear-gradient(135deg, #e6f7ff, #fff)', border: '1px solid #91d5ff', borderRadius: 10, padding: 12, margin: 12 }}>
          <div style={{ fontSize: 15, fontWeight: 600 }}>🩺 报告解读</div>
          <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
            咨询对象：{mem} · {r.title}
          </div>
          {r.file_url && (
            <button
              onClick={() => r.file_url && setPreviewUrl(r.file_url)}
              style={{ marginTop: 6, padding: '4px 10px', border: '1px solid #1890ff', color: '#1890ff', background: '#fff', borderRadius: 14, fontSize: 12 }}
            >
              查看报告原图
            </button>
          )}
        </div>
      );
    }
    return null;
  }, [session, reports, isCompare]);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <SpinLoading color="primary" />
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#f6f7f9' }}>
      <NavBar onBack={() => router.back()}>
        {session?.title || (isCompare ? '报告对比' : '报告解读')}
      </NavBar>

      {topCard}

      <div ref={listRef} style={{ flex: 1, overflowY: 'auto', padding: '0 12px 12px' }}>
        {messages.length === 0 && !streaming && (
          <div style={{ padding: 40, textAlign: 'center', color: '#999', fontSize: 13 }}>
            等待 AI 开始生成解读...
          </div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            style={{
              display: 'flex',
              justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
              marginTop: 10,
            }}
          >
            <div
              style={{
                maxWidth: '85%',
                padding: '10px 12px',
                borderRadius: 12,
                background: m.role === 'user' ? '#1890ff' : '#fff',
                color: m.role === 'user' ? '#fff' : '#222',
                fontSize: 14,
                lineHeight: 1.75,
                boxShadow: m.role === 'assistant' ? '0 1px 4px rgba(0,0,0,0.05)' : 'none',
                wordBreak: 'break-word',
              }}
              dangerouslySetInnerHTML={{
                __html: m.role === 'assistant' ? mdRender(m.content) : m.content.replace(/\n/g, '<br/>'),
              }}
            />
          </div>
        ))}
        {streaming && (
          <div style={{ fontSize: 12, color: '#1890ff', marginTop: 4 }}>AI 正在输入...</div>
        )}
      </div>

      {/* 底部输入 */}
      <div
        style={{
          borderTop: '1px solid #eee',
          background: '#fff',
          padding: '10px 12px',
          display: 'flex',
          gap: 8,
          alignItems: 'center',
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSend();
          }}
          placeholder="继续追问..."
          disabled={streaming}
          style={{
            flex: 1,
            padding: '10px 12px',
            borderRadius: 20,
            border: '1px solid #e5e5e5',
            background: '#f9f9f9',
            fontSize: 14,
            outline: 'none',
          }}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || streaming}
          style={{
            padding: '10px 16px',
            borderRadius: 20,
            background: input.trim() && !streaming ? '#1890ff' : '#d9d9d9',
            color: '#fff',
            fontSize: 14,
            border: 0,
          }}
        >
          发送
        </button>
      </div>

      <ImageViewer
        image={previewUrl || ''}
        visible={!!previewUrl}
        onClose={() => setPreviewUrl(null)}
      />
    </div>
  );
}

export default function CheckupChatPage() {
  return (
    <Suspense
      fallback={
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <SpinLoading color="primary" />
        </div>
      }
    >
      <CheckupChatContent />
    </Suspense>
  );
}
