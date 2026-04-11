'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, TextArea, Button, SpinLoading, Toast, ImageViewer, Tabs, Dialog } from 'antd-mobile';
import api from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  image_urls?: string[];
  time: string;
  created_at?: string;
}

interface DrugInfo {
  name: string;
  ingredients?: string;
  specification?: string;
  indications?: string;
  dosage?: string;
  precautions?: string;
  ai_suggestion_general?: string;
  ai_suggestion_personal?: string | null;
}

interface DrugInteraction {
  drugs: string[];
  risk: string;
}

interface DrugAiResult {
  drugs: DrugInfo[];
  interactions?: DrugInteraction[];
}

interface DrugRecord {
  id: number;
  ai_result?: string | DrugAiResult;
  session_id?: string;
}

const welcomeMessage: Message = {
  id: 'welcome',
  role: 'assistant',
  content: '您好！我是宾尼小康AI用药助手。我已收到您的药品图片，正在为您分析用药信息。如有其他问题，请随时提问。',
  time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
};

const BASE_SHARE_URL =
  'https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/shared/drug';

function formatMsgTime(dateStr?: string) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function parseAiResult(raw: string | DrugAiResult | undefined): DrugAiResult | null {
  if (!raw) return null;
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }
  return raw;
}

function DrugInfoCard({ drug, recordId }: { drug: DrugInfo; recordId: number | null }) {
  const [activeTab, setActiveTab] = useState('general');
  const [personalSuggestion, setPersonalSuggestion] = useState<string>('');
  const [personalLoading, setPersonalLoading] = useState(false);
  const [personalFetched, setPersonalFetched] = useState(false);

  const fetchPersonal = async () => {
    if (!recordId || personalFetched) return;
    setPersonalLoading(true);
    try {
      const res: any = await api.get(`/api/drug-identify/${recordId}/personal-suggestion`);
      const data = res.data || res;
      setPersonalSuggestion(data.suggestion || data.content || data.personal_suggestion || '');
    } catch {
      setPersonalSuggestion('暂无个性化建议');
    } finally {
      setPersonalLoading(false);
      setPersonalFetched(true);
    }
  };

  const handleTabChange = (key: string) => {
    setActiveTab(key);
    if (key === 'personal') fetchPersonal();
  };

  return (
    <div className="rounded-xl bg-white overflow-hidden" style={{ border: '1px solid #f0f0f0', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
      {/* Drug name header */}
      <div className="px-4 py-3" style={{ background: 'linear-gradient(135deg, #52c41a18, #13c2c218)' }}>
        <h3 className="font-bold text-base text-gray-800">{drug.name}</h3>
        {drug.specification && (
          <p className="text-xs text-gray-400 mt-0.5">{drug.specification}</p>
        )}
      </div>

      {/* Info rows */}
      <div className="px-4 py-3 space-y-2.5">
        {drug.ingredients && (
          <InfoRow label="主要成分" value={drug.ingredients} />
        )}
        {drug.indications && (
          <InfoRow label="适应症" value={drug.indications} />
        )}
        {drug.dosage && (
          <InfoRow label="用法用量" value={drug.dosage} />
        )}
        {drug.precautions && (
          <InfoRow label="注意事项" value={drug.precautions} highlight />
        )}
      </div>

      {/* AI suggestion tabs */}
      {(drug.ai_suggestion_general || recordId) && (
        <div className="border-t" style={{ borderColor: '#f0f0f0' }}>
          <Tabs
            activeKey={activeTab}
            onChange={handleTabChange}
            style={{
              '--title-font-size': '13px',
              '--active-title-color': '#52c41a',
              '--active-line-color': '#52c41a',
            }}
          >
            <Tabs.Tab title="通用建议" key="general" />
            <Tabs.Tab title="个性化建议" key="personal" />
          </Tabs>
          <div className="px-4 pb-4 pt-2">
            {activeTab === 'general' ? (
              drug.ai_suggestion_general ? (
                <p className="text-sm text-gray-600 leading-relaxed">{drug.ai_suggestion_general}</p>
              ) : (
                <p className="text-sm text-gray-400">暂无通用建议</p>
              )
            ) : personalLoading ? (
              <div className="flex items-center gap-2 py-3">
                <SpinLoading style={{ '--size': '18px', '--color': '#52c41a' }} />
                <span className="text-sm text-gray-400">加载个性化建议...</span>
              </div>
            ) : personalSuggestion ? (
              <p className="text-sm text-gray-600 leading-relaxed">{personalSuggestion}</p>
            ) : (
              <p className="text-sm text-gray-400">暂无个性化建议</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <span
        className="text-xs font-medium mr-1"
        style={{ color: highlight ? '#FF4D4F' : '#52c41a' }}
      >
        {label}
      </span>
      <span className="text-xs text-gray-600 leading-relaxed">{value}</span>
    </div>
  );
}

function DrugResultPanel({
  aiResult,
  recordId,
  onShare,
  shareLoading,
}: {
  aiResult: DrugAiResult;
  recordId: number | null;
  onShare: () => void;
  shareLoading: boolean;
}) {
  const drugs = aiResult.drugs || [];
  const interactions = aiResult.interactions || [];
  const [expandedIdx, setExpandedIdx] = useState<number | null>(0);

  return (
    <div className="space-y-4">
      {/* Interaction warning */}
      {interactions.length > 0 && (
        <div
          className="rounded-xl px-4 py-3"
          style={{ background: '#FFFBE6', border: '1px solid #FFE58F' }}
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="text-base">⚠️</span>
            <span className="font-semibold text-sm" style={{ color: '#FAAD14' }}>
              药物相互作用提示
            </span>
          </div>
          <div className="space-y-2">
            {interactions.map((inter, idx) => (
              <div key={idx} className="text-xs text-gray-600">
                <span className="font-medium text-gray-700">
                  {inter.drugs.join(' + ')}：
                </span>
                {inter.risk}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Drug cards */}
      {drugs.length === 1 ? (
        <DrugInfoCard drug={drugs[0]} recordId={recordId} />
      ) : (
        <div className="space-y-3">
          {drugs.map((drug, idx) => (
            <div key={idx}>
              <button
                className="w-full text-left rounded-xl bg-white px-4 py-3 flex items-center justify-between"
                style={{ border: '1px solid #f0f0f0' }}
                onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
              >
                <div>
                  <span className="font-semibold text-sm text-gray-800">{drug.name}</span>
                  {drug.specification && (
                    <span className="text-xs text-gray-400 ml-2">{drug.specification}</span>
                  )}
                </div>
                <span className="text-gray-400 text-sm">{expandedIdx === idx ? '▲' : '▼'}</span>
              </button>
              {expandedIdx === idx && (
                <div className="mt-1">
                  <DrugInfoCard drug={drug} recordId={recordId} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Share button */}
      <button
        onClick={onShare}
        disabled={shareLoading}
        className="w-full py-2.5 rounded-xl text-sm font-medium"
        style={{
          background: '#f5f5f5',
          color: '#555',
          border: '1px solid #e8e8e8',
          opacity: shareLoading ? 0.7 : 1,
        }}
      >
        复制分享链接
      </button>
    </div>
  );
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
  const [drugRecord, setDrugRecord] = useState<DrugRecord | null>(null);
  const [drugResultVisible, setDrugResultVisible] = useState(false);
  const [shareLoading, setShareLoading] = useState(false);
  const [shareLink, setShareLink] = useState('');
  const [shareLinkVisible, setShareLinkVisible] = useState(false);

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
          time:
            formatMsgTime(m.created_at) ||
            new Date(m.created_at).toLocaleTimeString('zh-CN', {
              hour: '2-digit',
              minute: '2-digit',
            }),
          created_at: m.created_at,
        }));
        setMessages([welcomeMessage, ...historyMsgs]);
      }
    } catch {
      // first time, no history
    }
  }, [sessionId]);

  const fetchDrugRecord = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res: any = await api.get('/api/drug-identify/history', {
        params: { page: 1, page_size: 50 },
      });
      const data = res.data || res;
      const items = data.items || data.records || data || [];
      const record = Array.isArray(items)
        ? items.find(
            (r: any) =>
              r.session_id === sessionId || String(r.chat_session_id) === sessionId
          )
        : null;
      if (record) setDrugRecord(record);
    } catch {
      // no record found
    }
  }, [sessionId]);

  useEffect(() => {
    loadHistory();
    fetchDrugRecord();
  }, [loadHistory, fetchDrugRecord]);

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

      await fetchDrugRecord();
    } catch {
      Toast.show({ content: '识别失败，请重试', icon: 'fail' });
    } finally {
      setUploading(false);
      setLoading(false);
      if (cameraRef.current) cameraRef.current.value = '';
      if (albumRef.current) albumRef.current.value = '';
    }
  };

  const handleShare = async () => {
    if (!drugRecord?.id) {
      Toast.show({ content: '暂无可分享的药物识别记录' });
      return;
    }
    setShareLoading(true);
    try {
      const res: any = await api.post(`/api/drug-identify/${drugRecord.id}/share`);
      const data = res.data || res;
      const token = data.share_token || data.token;
      if (!token) {
        Toast.show({ content: '生成分享链接失败' });
        return;
      }
      const url = `${BASE_SHARE_URL}/${token}`;
      setShareLink(url);
      setShareLinkVisible(true);
    } catch {
      Toast.show({ content: '生成分享链接失败' });
    } finally {
      setShareLoading(false);
    }
  };

  const handleCopyFromDialog = async () => {
    try {
      await navigator.clipboard.writeText(shareLink);
      Toast.show({ icon: 'success', content: '链接已复制' });
    } catch {
      Toast.show({ content: '复制失败' });
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

  const aiResult = drugRecord ? parseAiResult(drugRecord.ai_result) : null;

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <NavBar
        onBack={() => router.push('/drug')}
        right={
          aiResult ? (
            <button
              className="text-sm font-medium"
              style={{ color: '#52c41a' }}
              onClick={() => setDrugResultVisible(true)}
            >
              查看解读
            </button>
          ) : null
        }
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

      {/* Drug result panel (inline, above messages) */}
      {aiResult && drugResultVisible && (
        <div
          className="overflow-y-auto border-b"
          style={{ maxHeight: '60vh', borderColor: '#e8e8e8', background: '#f9f9f9' }}
        >
          <div className="px-4 py-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-sm text-gray-700">药物识别解读</span>
              <button
                className="text-xs text-gray-400"
                onClick={() => setDrugResultVisible(false)}
              >
                收起 ▲
              </button>
            </div>
            <DrugResultPanel
              aiResult={aiResult}
              recordId={drugRecord?.id ?? null}
              onShare={handleShare}
              shareLoading={shareLoading}
            />
          </div>
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
        {aiResult && !drugResultVisible && (
          <button
            onClick={() => setDrugResultVisible(true)}
            className="w-full mb-2 py-2 rounded-xl text-xs font-medium flex items-center justify-center gap-1"
            style={{ background: '#F6FFED', color: '#52C41A', border: '1px solid #B7EB8F' }}
          >
            <span>💊</span>
            <span>查看药物识别解读结果</span>
          </button>
        )}
        <div className="flex items-end gap-2">
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

          <div className="flex-1 bg-gray-50 rounded-2xl px-4 py-2">
            <TextArea
              placeholder="输入用药问题..."
              value={inputVal}
              onChange={setInputVal}
              autoSize={{ minRows: 1, maxRows: 3 }}
              style={{ '--font-size': '14px' } as React.CSSProperties}
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
              flexShrink: 0,
            }}
          >
            ➤
          </Button>
        </div>
      </div>

      <ImageViewer.Multi
        images={viewerImages}
        visible={imageViewerVisible}
        defaultIndex={0}
        onClose={() => setImageViewerVisible(false)}
      />

      {/* Share link dialog */}
      <Dialog
        visible={shareLinkVisible}
        title="药物识别分享链接"
        content={
          <div>
            <div
              className="rounded-lg p-3 mt-2 break-all text-xs text-gray-600"
              style={{ background: '#f5f5f5' }}
            >
              {shareLink}
            </div>
            <button
              onClick={handleCopyFromDialog}
              className="mt-3 w-full py-2.5 rounded-xl text-sm font-medium text-white"
              style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
            >
              复制链接
            </button>
          </div>
        }
        closeOnMaskClick
        onClose={() => setShareLinkVisible(false)}
        actions={[]}
      />
    </div>
  );
}
