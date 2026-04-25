'use client';

import { useState, useRef, useEffect, useCallback, Suspense } from 'react';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import { NavBar, Input, SpinLoading, Toast, Popup, Tag, DatePicker, Dialog, ActionSheet, ImageViewer } from 'antd-mobile';
import api from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { checkFileSize, uploadWithProgress } from '@/lib/upload-utils';
import ChatSidebar from '@/components/ChatSidebar';
import KnowledgeCard, { type KnowledgeHit } from '@/components/KnowledgeCard';

interface DrugInfoCardData {
  drug_name?: string;
  name?: string;
  indications?: string;
  dosage?: string;
  adverse_reactions?: string;
  precautions?: string;
  storage_conditions?: string;
  drug_category?: string;
  image_url?: string;
}

function DrugInfoCard({ drug }: { drug: DrugInfoCardData }) {
  const [expanded, setExpanded] = useState(false);
  const drugName = drug.drug_name || drug.name || '未知药品';
  return (
    <div className="rounded-xl bg-white overflow-hidden mt-2" style={{ border: '1px solid #f0f0f0', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
      <div
        className="flex items-center gap-3 px-3 py-3 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        {drug.image_url && (
          <img src={drug.image_url} alt={drugName} className="w-10 h-10 rounded-lg object-cover flex-shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="font-bold text-sm text-gray-800 truncate">{drugName}</div>
          {drug.indications && <div className="text-xs text-gray-500 mt-0.5 truncate">功能主治：{drug.indications}</div>}
          {drug.dosage && <div className="text-xs text-gray-500 mt-0.5 truncate">用法用量：{drug.dosage}</div>}
        </div>
        <span className="text-xs flex-shrink-0" style={{ color: '#52c41a' }}>{expanded ? '收起' : '查看详情'}</span>
      </div>
      <div
        style={{
          maxHeight: expanded ? 500 : 0,
          overflow: 'hidden',
          transition: 'max-height 0.3s ease-in-out',
        }}
      >
        <div className="px-3 pb-3 space-y-2 border-t" style={{ borderColor: '#f0f0f0' }}>
          {drug.adverse_reactions && (
            <div className="pt-2"><span className="text-xs font-medium" style={{ color: '#FF4D4F' }}>不良反应</span><span className="text-xs text-gray-600 ml-1">{drug.adverse_reactions}</span></div>
          )}
          {drug.precautions && (
            <div><span className="text-xs font-medium" style={{ color: '#fa8c16' }}>注意事项</span><span className="text-xs text-gray-600 ml-1">{drug.precautions}</span></div>
          )}
          {drug.storage_conditions && (
            <div><span className="text-xs font-medium" style={{ color: '#1890ff' }}>存储条件</span><span className="text-xs text-gray-600 ml-1">{drug.storage_conditions}</span></div>
          )}
          {drug.drug_category && (
            <div><span className="text-xs font-medium" style={{ color: '#722ed1' }}>药品分类</span><span className="text-xs text-gray-600 ml-1">{drug.drug_category}</span></div>
          )}
        </div>
      </div>
    </div>
  );
}

interface FunctionButton {
  id: string;
  name: string;
  button_type: 'digital_human_call' | 'photo_upload' | 'file_upload' | 'ai_dialog_trigger' | 'external_link' | 'drug_identify';
  params: Record<string, any>;
}

const BUTTON_EMOJI: Record<string, string> = {
  digital_human_call: '📞',
  photo_upload: '📷',
  file_upload: '📄',
  external_link: '🔗',
  drug_identify: '💊',
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

// [2026-04-23 公共页报告卡片迁移] 体检报告简要信息
interface ReportMini {
  id: number;
  title: string;
  file_url?: string | null;
  thumbnail_url?: string | null;
  file_urls?: string[] | null;
  thumbnail_urls?: string[] | null;
  created_at?: string | null;
  member_name?: string | null;
  member_relation?: string | null;
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

// [2026-04-23 公共页报告卡片迁移] 顶部报告卡片：解读（单张+九宫格缩略图）/ 对比（双卡 A/B + 时间跨度）
interface TopReportCardProps {
  reports: ReportMini[];
  isCompare: boolean;
  galleryExpanded: number | null;
  setGalleryExpanded: (v: number | null) => void;
  onPreview: (imgs: string[], idx: number) => void;
}

function TopReportCard({ reports, isCompare, galleryExpanded, setGalleryExpanded, onPreview }: TopReportCardProps) {
  if (!reports || reports.length === 0) return null;
  const mem = reports[0]
    ? `${reports[0].member_relation || ''} · ${reports[0].member_name || ''}`
    : '';

  if (isCompare && reports.length >= 2) {
    const a = reports[0];
    const b = reports[1];
    const imgsA = (a.file_urls && a.file_urls.length > 0) ? a.file_urls : (a.file_url ? [a.file_url] : []);
    const imgsB = (b.file_urls && b.file_urls.length > 0) ? b.file_urls : (b.file_url ? [b.file_url] : []);
    const spanText = (() => {
      try {
        const da = a.created_at ? new Date(a.created_at).getTime() : 0;
        const db = b.created_at ? new Date(b.created_at).getTime() : 0;
        if (!da || !db) return '';
        const months = Math.round(Math.abs(db - da) / (1000 * 60 * 60 * 24 * 30));
        if (months < 1) return '不足 1 个月';
        if (months < 12) return `${months} 个月`;
        const years = Math.floor(months / 12);
        return `${years} 年 ${months % 12} 个月`;
      } catch { return ''; }
    })();
    return (
      <div style={{ background: 'linear-gradient(135deg, #fffbe6, #fff)', border: '1px solid #ffe58f', borderRadius: 10, padding: 12, margin: 12 }}>
        <div style={{ fontSize: 15, fontWeight: 600 }}>🔄 报告对比</div>
        <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>咨询对象：{mem}</div>
        {/* [2026-04-25 Bug-03] 移除两个“查看 N 张原图”按钮，缩略图作为唯一预览入口 */}
        <div style={{ fontSize: 12, color: '#333', marginTop: 6 }}>
          <div>
            报告 A：<span style={{ color: '#1890ff' }}>{a.title}</span>
            {imgsA.length > 0 && (
              <span style={{ marginLeft: 6, color: '#999' }}>（{imgsA.length} 张）</span>
            )}
          </div>
          {imgsA.length > 0 && (
            <div style={{ marginTop: 4, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {imgsA.slice(0, 4).map((t, idx) => (
                <div
                  key={`a-${idx}`}
                  onClick={() => onPreview(imgsA, idx)}
                  style={{ width: 48, height: 48, borderRadius: 6, overflow: 'hidden', cursor: 'pointer', flexShrink: 0 }}
                >
                  <img src={t} alt={`a-${idx}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
              ))}
            </div>
          )}
          <div style={{ marginTop: 6 }}>
            报告 B：<span style={{ color: '#1890ff' }}>{b.title}</span>
            {imgsB.length > 0 && (
              <span style={{ marginLeft: 6, color: '#999' }}>（{imgsB.length} 张）</span>
            )}
          </div>
          {imgsB.length > 0 && (
            <div style={{ marginTop: 4, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {imgsB.slice(0, 4).map((t, idx) => (
                <div
                  key={`b-${idx}`}
                  onClick={() => onPreview(imgsB, idx)}
                  style={{ width: 48, height: 48, borderRadius: 6, overflow: 'hidden', cursor: 'pointer', flexShrink: 0 }}
                >
                  <img src={t} alt={`b-${idx}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
              ))}
            </div>
          )}
        </div>
        {spanText && <div style={{ fontSize: 12, color: '#999', marginTop: 6 }}>时间跨度：{spanText}</div>}
      </div>
    );
  }

  const r = reports[0];
  const allImgs = (r.file_urls && r.file_urls.length > 0) ? r.file_urls : (r.file_url ? [r.file_url] : []);
  const thumbs = (r.thumbnail_urls && r.thumbnail_urls.length > 0) ? r.thumbnail_urls : allImgs;
  return (
    <div style={{ background: 'linear-gradient(135deg, #e6f7ff, #fff)', border: '1px solid #91d5ff', borderRadius: 10, padding: 12, margin: 12 }}>
      <div style={{ fontSize: 15, fontWeight: 600 }}>🩺 报告解读</div>
      <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
        咨询对象：{mem} · {r.title}
        {allImgs.length > 1 ? <span style={{ marginLeft: 6, color: '#1890ff' }}>（共 {allImgs.length} 张）</span> : null}
      </div>
      {allImgs.length > 0 && (
        <>
          <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {thumbs.slice(0, galleryExpanded === 0 ? thumbs.length : Math.min(thumbs.length, 4)).map((t, idx) => (
              <div
                key={idx}
                onClick={() => onPreview(allImgs, idx)}
                style={{ width: 60, height: 60, borderRadius: 6, overflow: 'hidden', position: 'relative', cursor: 'pointer', flexShrink: 0 }}
              >
                <img src={t} alt={`img-${idx}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              </div>
            ))}
            {galleryExpanded !== 0 && thumbs.length > 4 && (
              <button
                onClick={() => setGalleryExpanded(0)}
                style={{ width: 60, height: 60, borderRadius: 6, border: '1px dashed #91d5ff', background: '#fafcff', color: '#1890ff', fontSize: 12 }}
              >
                +{thumbs.length - 4}
              </button>
            )}
          </div>
          {/* [2026-04-25 Bug-03] 移除冗余的“查看报告原图”按钮，缩略图本身即为预览入口 */}
        </>
      )}
    </div>
  );
}

function ChatPageInner() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const sessionId = params.sessionId as string;
  const { isLoggedIn } = useAuth();

  const urlType = searchParams.get('type') || '';
  const urlMsg = searchParams.get('msg') || '';
  const urlMember = searchParams.get('member') || '';
  const urlDrugName = searchParams.get('drug_name') || '';
  const isSymptom = urlType === 'symptom';
  const isDrugIdentify = urlType === 'drug_identify';
  const isConstitution = urlType === 'constitution';
  // [2026-04-23 公共页报告卡片迁移] 体检报告相关类型识别
  const isReportInterpret = urlType === 'report_interpret';
  const isReportCompare = urlType === 'report_compare';
  const isReportType = isReportInterpret || isReportCompare;
  const urlAutoStart = searchParams.get('auto_start') === '1';

  const [messages, setMessages] = useState<Message[]>([welcomeMessage]);
  const [inputVal, setInputVal] = useState('');
  const [loading, setLoading] = useState(false);
  const [sidebarVisible, setSidebarVisible] = useState(false);

  // [2026-04-23 公共页报告卡片迁移] 体检报告相关 state（仅 report_interpret/report_compare 场景使用）
  const [reportList, setReportList] = useState<ReportMini[]>([]);
  const [previewImages, setPreviewImages] = useState<string[]>([]);
  const [previewIndex, setPreviewIndex] = useState<number>(-1);
  const [galleryExpanded, setGalleryExpanded] = useState<number | null>(null);
  const reportAutoStartedRef = useRef(false);
  // [2026-04-25] 报告解读失败状态 + 重试触发
  const [interpretFailed, setInterpretFailed] = useState(false);
  const [streamRetryTick, setStreamRetryTick] = useState(0);

  // [2026-04-25 PRD F5] 报告解读 OCR 详情默认隐藏 + 兜底入口（按需加载）
  const [ocrDetailExpanded, setOcrDetailExpanded] = useState(false);
  const [ocrDetailText, setOcrDetailText] = useState<string>('');
  const [ocrDetailLoading, setOcrDetailLoading] = useState(false);
  const [ocrDetailLoaded, setOcrDetailLoaded] = useState(false);

  // [2026-04-25 PRD F5-3] 切换 OCR 详情展开/收起；首次展开时按需拉取
  const toggleOcrDetail = async () => {
    if (!isReportType || !sessionId) return;
    const next = !ocrDetailExpanded;
    setOcrDetailExpanded(next);
    try {
      api.post('/api/report/interpret/ocr-detail/click', {
        session_id: Number(sessionId),
        action: next ? 'view' : 'collapse',
      }).catch(() => {});
    } catch { /* ignore */ }
    if (next && !ocrDetailLoaded && !ocrDetailLoading) {
      setOcrDetailLoading(true);
      try {
        const r: any = await api.get(`/api/report/interpret/session/${sessionId}/ocr-detail`);
        const data = r.data || r;
        setOcrDetailText(String(data.ocr_text || ''));
        setOcrDetailLoaded(true);
      } catch {
        setOcrDetailText('');
      } finally {
        setOcrDetailLoading(false);
      }
    }
  };

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

  // Drug identify / constitution banner
  const [drugIdentifyBannerVisible, setDrugIdentifyBannerVisible] = useState(isDrugIdentify);
  const [drugIdentifyDrugNames, setDrugIdentifyDrugNames] = useState(isDrugIdentify ? urlDrugName : '');
  const [drugIdentifyMember, setDrugIdentifyMember] = useState(isDrugIdentify ? urlMember : '');
  const [constitutionBannerVisible, setConstitutionBannerVisible] = useState(isConstitution);
  const [constitutionType, setConstitutionType] = useState('');
  const [constitutionMember, setConstitutionMember] = useState('');

  // Switch member popup
  const [memberPopupVisible, setMemberPopupVisible] = useState(false);
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([]);
  const [switchingMember, setSwitchingMember] = useState(false);
  const [currentRelationLabel, setCurrentRelationLabel] = useState(() => {
    if (isSymptom && urlMember) {
      const relation = urlMember.split('·')[0].trim();
      return relation || '本人';
    }
    return '本人';
  });
  const [isSymptomLocked, setIsSymptomLocked] = useState(isSymptom || isDrugIdentify || isConstitution);

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
  const [uploadPercent, setUploadPercent] = useState(-1);

  // Module 5: Drug identify from chat
  const [drugActionSheetVisible, setDrugActionSheetVisible] = useState(false);
  const [drugIdentifyTip, setDrugIdentifyTip] = useState('');
  const [drugIdentifyMaxPhotos, setDrugIdentifyMaxPhotos] = useState(5);
  const drugCameraRef = useRef<HTMLInputElement>(null);
  const drugAlbumRef = useRef<HTMLInputElement>(null);
  const [drugRecognizing, setDrugRecognizing] = useState(false);

  // Module 6: SSE streaming
  const [streamingContent, setStreamingContent] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const streamAbortRef = useRef<AbortController | null>(null);

  // Module 7: AI reply action buttons
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);

  // Module 8: TTS
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const [ttsPlayingMsgId, setTtsPlayingMsgId] = useState<string | null>(null);
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);

  // Module 9: Share
  const [sharePopupVisible, setSharePopupVisible] = useState(false);
  const [shareMsgId, setShareMsgId] = useState<string | null>(null);
  const [shareLoading, setShareLoading] = useState(false);
  const [posterUrl, setPosterUrl] = useState('');
  const [posterPreviewVisible, setPosterPreviewVisible] = useState(false);

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
      case 'drug_identify':
        setDrugIdentifyTip(btn.params.photo_tip_text || '请拍摄或选择药品包装照片');
        setDrugIdentifyMaxPhotos(btn.params.max_photo_count || 5);
        setDrugActionSheetVisible(true);
        break;
    }
  };

  const handleFileUpload = async (file: File, type: 'photo' | 'file') => {
    const module = type === 'photo' ? 'chat_image' : 'chat_file';
    const sizeCheck = await checkFileSize(file, module);
    if (!sizeCheck.ok) {
      Toast.show({ content: `文件大小超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'fail' });
      return;
    }

    const fd = new FormData();
    fd.append('file', file);
    fd.append('message_type', type === 'photo' ? 'image' : 'file');
    try {
      setUploadPercent(0);
      const resData: any = await uploadWithProgress(
        `/api/chat/sessions/${sessionId}/messages`,
        fd,
        (pct) => setUploadPercent(pct),
        { timeout: 60000 },
      );
      setUploadPercent(-1);
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
      setUploadPercent(-1);
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

  // [2026-04-23 公共页报告卡片迁移] 加载 report 类型会话详情 -> reportList
  useEffect(() => {
    if (!isReportType || !sessionId) return;
    (async () => {
      try {
        const sess: any = await api.get(`/api/chat/sessions/${sessionId}`);
        const brief: any[] = Array.isArray(sess?.reports_brief) ? sess.reports_brief : [];
        const rs: ReportMini[] = brief.map((d: any) => {
          const urls: string[] = Array.isArray(d.file_urls) && d.file_urls.length > 0
            ? d.file_urls.filter(Boolean)
            : (d.file_url ? [d.file_url] : []);
          const thumbs: string[] = Array.isArray(d.thumbnail_urls) && d.thumbnail_urls.length > 0
            ? d.thumbnail_urls.filter(Boolean)
            : (d.thumbnail_url ? [d.thumbnail_url] : urls);
          return {
            id: d.id,
            title: d.title,
            file_url: urls[0] || null,
            thumbnail_url: thumbs[0] || urls[0] || null,
            file_urls: urls,
            thumbnail_urls: thumbs,
            created_at: d.report_date || null,
            member_name: sess?.family_member?.nickname || null,
            member_relation: sess?.family_member?.relationship || null,
          };
        });
        setReportList(rs);
      } catch { /* 忽略 */ }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isReportType, sessionId]);

  // [2026-04-25] 报告解读 SSE 订阅：进入页面即订阅后端 worker 推流（不再本地插入用户气泡，也不再调 /chat）
  useEffect(() => {
    if (!isReportType || !sessionId) return;
    if (reportAutoStartedRef.current) return;
    // 如果已有真正 assistant 消息则无需再订阅（已 done 状态）
    reportAutoStartedRef.current = true;

    const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const abortController = new AbortController();
    streamAbortRef.current = abortController;

    let accumulated = '';
    let msgId = '';
    let streaming = false;

    const subscribe = async () => {
      try {
        const resp = await fetch(
          `${basePath}/api/report/interpret/session/${sessionId}/stream?auto_start=1`,
          {
            method: 'GET',
            headers: {
              'Accept': 'text/event-stream',
              ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            },
            signal: abortController.signal,
          },
        );
        if (!resp.ok || !resp.body) {
          throw new Error(`stream http ${resp.status}`);
        }

        setIsStreaming(true);
        setStreamingContent('');
        streaming = true;

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let currentEvent = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7).trim();
              continue;
            }
            if (!line.startsWith('data:')) continue;
            const dataStr = line.startsWith('data: ') ? line.slice(6) : line.slice(5);
            let data: any = {};
            try { data = JSON.parse(dataStr); } catch { data = { raw: dataStr }; }

            // 兼容新旧事件
            if (currentEvent === 'message.delta' || data.type === 'delta') {
              const d = data.delta || data.content || '';
              if (d) {
                accumulated += d;
                setStreamingContent(accumulated);
              }
            } else if (currentEvent === 'message.done' || data.type === 'done') {
              const final = data.content || accumulated;
              accumulated = final;
              if (data.message_id) msgId = String(data.message_id);
              setStreamingContent(accumulated);
            } else if (currentEvent === 'status') {
              if (data.interpret_status === 'failed') {
                setInterpretFailed(true);
              } else if (data.interpret_status === 'done') {
                setInterpretFailed(false);
              }
            } else if (currentEvent === 'error' || data.type === 'error') {
              if (!accumulated) {
                Toast.show({ content: data.message || data.content || 'AI 解读失败' });
              }
              setInterpretFailed(true);
            } else if (currentEvent === 'done') {
              // 整体结束
            } else if (currentEvent === 'ping') {
              // 心跳
            }
            currentEvent = '';
          }
        }
      } catch (e: any) {
        if (e?.name === 'AbortError') return;
        // 网络断线 → 简单一次重试
        console.warn('[report SSE] error', e);
      } finally {
        if (streaming) {
          if (accumulated) {
            const aiMsg: Message = {
              id: msgId || `ai-${Date.now()}`,
              role: 'assistant',
              content: accumulated,
              time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
            };
            setMessages((prev) => {
              // 避免重复：若最后一条 assistant 消息内容已一致（loadHistory 并发拉取）则不重复追加
              const hasSame = prev.some((m) => m.role === 'assistant' && m.content === accumulated);
              return hasSame ? prev : [...prev, aiMsg];
            });
          }
          setIsStreaming(false);
          setStreamingContent('');
          streaming = false;
        }
      }
    };

    subscribe();

    return () => {
      try { abortController.abort(); } catch { /* ignore */ }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isReportType, sessionId, streamRetryTick]);

  // [2026-04-25] 报告解读失败状态 + 重新解读
  const retryInterpret = useCallback(async () => {
    if (!sessionId) return;
    try {
      await api.post(`/api/report/interpret/session/${sessionId}/retry`, {});
      setInterpretFailed(false);
      // 重新触发订阅
      reportAutoStartedRef.current = false;
      setMessages((prev) => prev.filter((m) => m.id === 'welcome' || m.role !== 'assistant' || !m.content.includes('AI_FAILED')));
      // trigger useEffect re-subscribe by toggling a state
      setStreamRetryTick((t) => t + 1);
    } catch (e: any) {
      Toast.show({ content: e?.message || '重新解读失败，请稍后再试' });
    }
  }, [sessionId]);

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

  // Load session info for drug_identify / constitution banners
  useEffect(() => {
    if (!isDrugIdentify && !isConstitution) return;
    const loadSessionInfo = async () => {
      try {
        const res: any = await api.get(`/api/chat-sessions/${sessionId}`);
        const data = res.data || res;
        if (isDrugIdentify) {
          if (!urlDrugName) {
            const apiDrugs = data.drug_names || data.title || '';
            if (apiDrugs) setDrugIdentifyDrugNames(apiDrugs);
          }
          if (!urlMember) {
            const memberInfo = data.family_member_relation || data.family_member?.nickname || '';
            if (memberInfo) setDrugIdentifyMember(memberInfo);
          }
          if (data.family_member_relation) setCurrentRelationLabel(data.family_member_relation);
        }
        if (isConstitution) {
          setConstitutionType(data.constitution_type || data.title || '');
          const memberInfo = data.family_member_relation || data.family_member?.nickname || '';
          setConstitutionMember(memberInfo);
          if (data.family_member_relation) setCurrentRelationLabel(data.family_member_relation);
        }
      } catch { /* ignore */ }
    };
    loadSessionInfo();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, isDrugIdentify, isConstitution]);

  // Drug identify / constitution banner stays persistent: do NOT collapse after AI replies.
  // The banner visibility is derived from URL `type` parameter once and never auto-hidden.
  // (Removed previous auto-collapse useEffect on AI reply to fix banner-disappearing bug.)

  useEffect(() => {
    if (isSymptom) return;
    const restoreSessionMember = async () => {
      try {
        const res = await api.get(`/api/chat-sessions/${sessionId}`);
        if (res) {
          const sessionType = (res as any).session_type;
          if (sessionType === 'symptom_check' || sessionType === 'symptom'
              || sessionType === 'drug_query' || sessionType === 'drug_identify'
              || sessionType === 'constitution') {
            setIsSymptomLocked(true);
            const relation = (res as any).family_member_relation;
            if (relation) {
              setCurrentRelationLabel(relation);
            }
          }
        }
      } catch (e) {
        console.log('restoreSessionMember error', e);
      }
    };
    restoreSessionMember();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    if (!isSymptom) return;
    const aiReplies = messages.filter((m) => m.role === 'assistant' && m.id !== 'welcome');
    if (aiReplies.length > 0 && bannerExpanded) {
      setBannerExpanded(false);
    }
  }, [messages, isSymptom]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

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

  // Stop TTS when user sends new message
  const stopTts = useCallback(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (ttsAudioRef.current) {
      ttsAudioRef.current.pause();
      ttsAudioRef.current = null;
    }
    setTtsPlaying(false);
    setTtsPlayingMsgId(null);
  }, []);

  const sendMessageText = async (text: string) => {
    if (loading) return;
    // [2026-04-25] 报告解读 auto_start 已改为独立订阅 SSE，这里不再接受空 text
    if (!text) return;

    stopTts();

    // [2026-04-23 公共页报告卡片迁移] report 场景首条触发无文字；其余场景照旧
    const shouldPushUserMsg = !!text;
    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    };

    if (shouldPushUserMsg && firstUserMsgIdRef.current === null) {
      firstUserMsgIdRef.current = userMsg.id;
    }

    if (shouldPushUserMsg) {
      setMessages((prev) => [...prev, userMsg]);
    }
    setInputVal('');
    setLoading(true);

    // Try SSE streaming first
    try {
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
      const abortController = new AbortController();
      streamAbortRef.current = abortController;

      // [2026-04-23 公共页报告卡片迁移] report 类型按体检专用 SSE 端点；其他类型走通用 /stream
      let sseUrl: string;
      let sseBody: string | undefined;
      if (isReportType) {
        if (!text) {
          sseUrl = `${basePath}/api/chat/sessions/${sessionId}/first-message-stream`;
          sseBody = undefined;
        } else {
          sseUrl = `${basePath}/api/chat/sessions/${sessionId}/messages-stream`;
          sseBody = JSON.stringify({ content: text });
        }
      } else {
        sseUrl = `${basePath}/api/chat/sessions/${sessionId}/stream`;
        sseBody = JSON.stringify({ content: text, message_type: 'text' });
      }

      const response = await fetch(sseUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: sseBody,
        signal: abortController.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error('SSE not available');
      }

      setIsStreaming(true);
      setStreamingContent('');
      setLoading(false);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';
      let messageId = '';
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            const eventType = line.slice(7).trim();
            if (eventType === 'done') {
              // next data line has message_id
            }
          } else if (line.startsWith('data: ') || line.startsWith('data:')) {
            const dataStr = line.startsWith('data: ') ? line.slice(6) : line.slice(5);
            try {
              const data = JSON.parse(dataStr);
              // [2026-04-23 公共页报告卡片迁移] 兼容体检 SSE：{type:'delta|done|error', content}
              if (data.type === 'delta' && data.content) {
                accumulated += data.content;
                setStreamingContent(accumulated);
              } else if (data.type === 'done') {
                if (data.content) {
                  accumulated = data.content;
                  setStreamingContent(accumulated);
                }
                if (data.message_id) messageId = String(data.message_id);
              } else if (data.type === 'error') {
                Toast.show({ content: data.content || 'AI 服务异常' });
              } else if (data.content || data.delta) {
                accumulated += (data.delta || data.content || '');
                setStreamingContent(accumulated);
              }
              if (data.message_id) {
                messageId = String(data.message_id);
              }
              if (data.done) {
                messageId = data.message_id ? String(data.message_id) : messageId;
              }
            } catch {
              accumulated += dataStr;
              setStreamingContent(accumulated);
            }
          }
        }
      }

      const aiMsg: Message = {
        id: messageId || `ai-${Date.now()}`,
        role: 'assistant',
        content: accumulated || '抱歉，我暂时无法回答这个问题。请稍后重试。',
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, aiMsg]);
      setIsStreaming(false);
      setStreamingContent('');
      streamAbortRef.current = null;
    } catch (streamErr: any) {
      // Fallback to non-streaming API
      setIsStreaming(false);
      setStreamingContent('');
      streamAbortRef.current = null;

      if (streamErr?.name === 'AbortError') {
        setLoading(false);
        return;
      }

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
        if (status === 401) errorContent = '登录已过期，请重新登录。';
        else if (status === 404) errorContent = '会话不存在，请返回重新创建对话。';
        else if (status === 422) errorContent = '请求参数异常，请返回重新创建对话。';

        const fallbackMsg: Message = {
          id: `ai-${Date.now()}`,
          role: 'assistant',
          content: errorContent,
          time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        };
        setMessages((prev) => [...prev, fallbackMsg]);
      }
    }
    setLoading(false);
  };

  // Module 5: Drug recognize from chat (multi-image batch)
  const handleDrugRecognize = async (files: File[]) => {
    if (!files.length || drugRecognizing) return;
    const validFiles: File[] = [];
    for (const file of files) {
      const sizeCheck = await checkFileSize(file, 'drug_identify');
      if (!sizeCheck.ok) {
        Toast.show({ content: `文件 ${file.name} 超过限制（最大 ${sizeCheck.maxMb} MB），已跳过` });
        continue;
      }
      validFiles.push(file);
    }
    if (validFiles.length === 0) return;

    setDrugRecognizing(true);

    const loadingMsg: Message = {
      id: `drug-loading-${Date.now()}`,
      role: 'assistant',
      content: `正在识别药品（${validFiles.length}张图片）...`,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages((prev) => [...prev, loadingMsg]);

    try {
      const ocrTexts: string[] = [];
      const drugCards: DrugInfoCardData[] = [];
      let failCount = 0;

      for (const file of validFiles) {
        try {
          const formData = new FormData();
          formData.append('file', file);
          formData.append('scene_name', '拍照识药');
          const ocrData: any = await uploadWithProgress('/api/ocr/batch-recognize', formData, undefined, { timeout: 120000 });

          const text = ocrData.ocr_text || ocrData.text || ocrData.result?.ocr_text || '';
          if (text) ocrTexts.push(text);

          const drugInfo: DrugInfoCardData = {
            drug_name: ocrData.drug_name || ocrData.result?.drug_name,
            indications: ocrData.indications || ocrData.result?.indications,
            dosage: ocrData.dosage || ocrData.result?.dosage,
            adverse_reactions: ocrData.adverse_reactions || ocrData.result?.adverse_reactions,
            precautions: ocrData.precautions || ocrData.result?.precautions,
            storage_conditions: ocrData.storage_conditions || ocrData.result?.storage_conditions,
            drug_category: ocrData.drug_category || ocrData.result?.drug_category,
            image_url: ocrData.image_url || ocrData.result?.image_url,
          };
          if (drugInfo.drug_name) drugCards.push(drugInfo);
        } catch {
          failCount++;
        }
      }

      setMessages((prev) => prev.filter((m) => m.id !== loadingMsg.id));

      if (failCount > 0 && failCount < validFiles.length) {
        Toast.show({ content: `${failCount}张图片识别失败，已跳过`, duration: 2000 });
      }

      if (drugCards.length === 0 && ocrTexts.length === 0) {
        const errorMsg: Message = {
          id: `drug-error-${Date.now()}`,
          role: 'assistant',
          content: '药品识别失败，请确认图片清晰后重试。',
          time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        };
        setMessages((prev) => [...prev, errorMsg]);
        return;
      }

      for (const card of drugCards) {
        const cardMsg: Message = {
          id: `drug-result-${Date.now()}-${Math.random()}`,
          role: 'assistant',
          content: `__DRUG_CARD__${JSON.stringify(card)}`,
          time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        };
        setMessages((prev) => [...prev, cardMsg]);
      }

      const drugNames = drugCards.map((c) => c.drug_name || '药品').filter(Boolean);
      let followUp = '';
      if (drugNames.length === 1) {
        followUp = `我刚识别了一种药品：${drugNames[0]}，请帮我分析这个药品的用药建议。`;
      } else if (drugNames.length > 1) {
        followUp = `我刚识别了以下药品：${drugNames.join('、')}，请帮我分析这些药品的用药建议及药物相互作用。`;
      }
      if (followUp) {
        await sendMessageText(followUp);
      }
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== loadingMsg.id));
      const errorMsg: Message = {
        id: `drug-error-${Date.now()}`,
        role: 'assistant',
        content: '药品识别失败，请确认图片清晰后重试。',
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setDrugRecognizing(false);
      if (drugCameraRef.current) drugCameraRef.current.value = '';
      if (drugAlbumRef.current) drugAlbumRef.current.value = '';
    }
  };

  // Module 8: TTS
  const handleTts = useCallback(async (msgId: string, text: string) => {
    if (ttsPlaying && ttsPlayingMsgId === msgId) {
      stopTts();
      return;
    }
    stopTts();

    const plainText = text.replace(/\*\*(.*?)\*\*/g, '$1').replace(/---disclaimer---[\s\S]*/g, '').trim();
    if (!plainText) return;

    setTtsPlaying(true);
    setTtsPlayingMsgId(msgId);

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
          audio.onended = () => { setTtsPlaying(false); setTtsPlayingMsgId(null); };
          audio.onerror = () => { setTtsPlaying(false); setTtsPlayingMsgId(null); };
          audio.play();
          return;
        }
      }
    } catch { /* fallback to Web Speech */ }

    if (typeof window !== 'undefined' && window.speechSynthesis) {
      const utterance = new SpeechSynthesisUtterance(plainText);
      utterance.lang = 'zh-CN';
      utterance.rate = 1.0;
      utterance.onend = () => { setTtsPlaying(false); setTtsPlayingMsgId(null); };
      utterance.onerror = () => { setTtsPlaying(false); setTtsPlayingMsgId(null); };
      window.speechSynthesis.speak(utterance);
    } else {
      Toast.show({ content: '当前浏览器不支持语音播报' });
      setTtsPlaying(false);
      setTtsPlayingMsgId(null);
    }
  }, [ttsPlaying, ttsPlayingMsgId, stopTts]);

  // Module 7: Copy
  const handleCopyMsg = useCallback(async (msgId: string, text: string) => {
    const plainText = text.replace(/\*\*(.*?)\*\*/g, '$1').replace(/---disclaimer---/g, '\n').trim();
    try {
      await navigator.clipboard.writeText(plainText);
      setCopiedMsgId(msgId);
      setTimeout(() => setCopiedMsgId(null), 1500);
    } catch {
      Toast.show({ content: '复制失败', icon: 'fail' });
    }
  }, []);

  // Module 9: Share
  const handleShareMsg = useCallback((msgId: string) => {
    setShareMsgId(msgId);
    setSharePopupVisible(true);
  }, []);

  const handleShareToWechat = useCallback(async () => {
    if (!shareMsgId) return;
    setShareLoading(true);
    try {
      const res: any = await api.post('/api/chat/share', { session_id: sessionId, message_id: shareMsgId });
      const data = res.data || res;
      const shareToken = data.share_token || data.token;
      if (shareToken) {
        const baseUrl = typeof window !== 'undefined' ? window.location.origin : '';
        const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
        const shareUrl = `${baseUrl}${basePath}/shared/chat/${shareToken}`;
        try {
          await navigator.clipboard.writeText(shareUrl);
          Toast.show({ content: '分享链接已复制到剪贴板', icon: 'success' });
        } catch {
          Toast.show({ content: shareUrl, duration: 5000 });
        }
      }
    } catch {
      Toast.show({ content: '生成分享链接失败', icon: 'fail' });
    }
    setShareLoading(false);
    setSharePopupVisible(false);
  }, [shareMsgId, sessionId]);

  const handleSharePoster = useCallback(async () => {
    if (!shareMsgId) return;
    setShareLoading(true);
    try {
      const res: any = await api.post('/api/chat/share/poster', { session_id: sessionId, message_id: shareMsgId });
      const data = res.data || res;
      if (data.poster_url || data.image_url) {
        setPosterUrl(data.poster_url || data.image_url);
        setPosterPreviewVisible(true);
      } else {
        Toast.show({ content: '生成海报失败', icon: 'fail' });
      }
    } catch {
      Toast.show({ content: '生成海报失败', icon: 'fail' });
    }
    setShareLoading(false);
    setSharePopupVisible(false);
  }, [shareMsgId, sessionId]);

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
    if (isSymptomLocked) {
      const lockMsg = isDrugIdentify
        ? '当前为用药识别专属咨询，咨询对象已锁定'
        : isConstitution
        ? '当前为体质分析专属咨询，咨询对象已锁定'
        : '当前为健康自查专属咨询，咨询对象已锁定，如需为其他人咨询请返回重新发起';
      Toast.show({ content: lockMsg, duration: 2500 });
      return;
    }
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

      {/* Drug identify banner */}
      {isDrugIdentify && drugIdentifyBannerVisible && (
        <div
          className="mx-3 mt-2 rounded-xl px-3 py-2 flex items-start gap-2"
          style={{ background: '#fff7e6', border: '1px solid #ffd591' }}
        >
          <span style={{ color: '#fa8c16', fontSize: 15, flexShrink: 0, marginTop: 1 }}>💊</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-1">
              <span className="text-xs font-medium" style={{ color: '#fa8c16' }}>用药识别</span>
              {drugIdentifyMember && (
                <span className="text-xs" style={{ color: '#fa8c16' }}>咨询对象：{drugIdentifyMember}</span>
              )}
            </div>
            {drugIdentifyDrugNames && (
              <div className="text-xs mt-1" style={{ color: '#555' }}>
                {drugIdentifyDrugNames}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Constitution banner */}
      {isConstitution && constitutionBannerVisible && (
        <div
          className="mx-3 mt-2 rounded-xl px-3 py-2 flex items-start gap-2"
          style={{ background: '#f9f0ff', border: '1px solid #d3adf7' }}
        >
          <span style={{ color: '#722ed1', fontSize: 15, flexShrink: 0, marginTop: 1 }}>🌿</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-1">
              <span className="text-xs font-medium" style={{ color: '#722ed1' }}>体质分析</span>
              {constitutionMember && (
                <span className="text-xs" style={{ color: '#722ed1' }}>咨询对象：{constitutionMember}</span>
              )}
            </div>
            {constitutionType && (
              <div className="text-xs mt-1" style={{ color: '#555' }}>
                体质类型：{constitutionType}
              </div>
            )}
          </div>
        </div>
      )}

      {/* [2026-04-23 公共页报告卡片迁移] 体检报告顶部卡片（解读 / 对比） */}
      {isReportType && reportList.length > 0 && (
        <TopReportCard
          reports={reportList}
          isCompare={isReportCompare}
          galleryExpanded={galleryExpanded}
          setGalleryExpanded={setGalleryExpanded}
          onPreview={(imgs, idx) => { setPreviewImages(imgs); setPreviewIndex(idx); }}
        />
      )}

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes cursor-blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        .streaming-cursor::after {
          content: '▌';
          color: #52c41a;
          animation: cursor-blink 1s ease-in-out infinite;
          margin-left: 1px;
        }
      `}} />

      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3">
        {messages.map((msg, msgIdx) => {
          const isDrugCard = msg.role === 'assistant' && msg.content.startsWith('__DRUG_CARD__');
          const isLatestAiReply = msg.role === 'assistant' && msg.id !== 'welcome' && !isStreaming &&
            msgIdx === messages.length - 1 - [...messages].reverse().findIndex((m) => m.role === 'assistant' && m.id !== 'welcome');
          const showActionButtons = isLatestAiReply && !isDrugCard && !loading;

          return (
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
                      <span className="ml-auto text-xs" style={{ color: '#52c41a' }}>{firstCardExpanded ? '▲' : '▼'}</span>
                    </div>
                    <div style={{ color: '#444', overflow: 'hidden', maxHeight: firstCardExpanded ? 'none' : '1.6em', whiteSpace: firstCardExpanded ? 'normal' : 'nowrap', textOverflow: firstCardExpanded ? 'unset' : 'ellipsis' }}>
                      {msg.content}
                    </div>
                  </div>
                ) : isDrugCard ? (
                  (() => {
                    try {
                      const drugData: DrugInfoCardData = JSON.parse(msg.content.replace('__DRUG_CARD__', ''));
                      return <DrugInfoCard drug={drugData} />;
                    } catch { return <div className="text-xs text-gray-400">药品信息解析失败</div>; }
                  })()
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
                {msg.role === 'assistant' && msg.knowledge_hits && msg.knowledge_hits.length > 0 && (
                  <div className="mt-2 space-y-2 w-full">
                    {msg.knowledge_hits.map((hit, idx) => (
                      <KnowledgeCard key={`${msg.id}-kb-${idx}`} hit={hit} hitLogId={hit.hit_log_id} onFeedback={handleKnowledgeFeedback} />
                    ))}
                  </div>
                )}
                <div className={`text-xs text-gray-300 mt-1 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                  {msg.time}
                </div>
                {/* [2026-04-25 PRD F5] 报告解读 OCR 详情兜底入口：只在报告解读会话的第一条 AI 解读消息底部显示 */}
                {isReportType && msg.role === 'assistant' && !isDrugCard && msg.id !== 'welcome'
                  && msgIdx === messages.findIndex((m) => m.role === 'assistant' && m.id !== 'welcome')
                  && !isStreaming && !interpretFailed && (
                  <div style={{ marginTop: 6, textAlign: 'right' }}>
                    <button
                      onClick={toggleOcrDetail}
                      disabled={ocrDetailLoading}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#999',
                        fontSize: Math.max(10, chatFontSize - 4),
                        cursor: 'pointer',
                        padding: 0,
                      }}
                    >
                      {ocrDetailLoading
                        ? '加载中…'
                        : ocrDetailExpanded
                          ? '收起 OCR 识别详情 ▴'
                          : '查看 OCR 识别详情 ▾'}
                    </button>
                    {ocrDetailExpanded && (
                      <div
                        style={{
                          marginTop: 6,
                          padding: '10px 12px',
                          background: '#fafafa',
                          border: '1px solid #f0f0f0',
                          borderRadius: 8,
                          color: '#666',
                          fontSize: Math.max(11, chatFontSize - 3),
                          lineHeight: 1.7,
                          textAlign: 'left',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          maxHeight: 360,
                          overflowY: 'auto',
                        }}
                      >
                        {ocrDetailText || (ocrDetailLoaded ? '（暂无 OCR 文本）' : '加载中…')}
                      </div>
                    )}
                  </div>
                )}
                {/* Module 7: Action buttons on latest AI reply */}
                {showActionButtons && (
                  <div className="flex items-center gap-3 mt-2">
                    <button
                      className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs"
                      style={{ background: '#f5f5f5', color: copiedMsgId === msg.id ? '#52c41a' : '#666', border: '1px solid #e8e8e8' }}
                      onClick={() => handleCopyMsg(msg.id, msg.content)}
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                      {copiedMsgId === msg.id ? '已复制' : '复制'}
                    </button>
                    <button
                      className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs"
                      style={{ background: '#f5f5f5', color: ttsPlayingMsgId === msg.id ? '#52c41a' : '#666', border: '1px solid #e8e8e8' }}
                      onClick={() => handleTts(msg.id, msg.content)}
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
                      {ttsPlayingMsgId === msg.id ? '停止播报' : '播报'}
                    </button>
                    <button
                      className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs"
                      style={{ background: '#f5f5f5', color: '#666', border: '1px solid #e8e8e8' }}
                      onClick={() => handleShareMsg(msg.id)}
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
                      分享
                    </button>
                  </div>
                )}
              </div>
              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-primary flex-shrink-0 flex items-center justify-center ml-2">
                  <span className="text-white text-xs">我</span>
                </div>
              )}
            </div>
          );
        })}

        {/* [2026-04-25] 报告解读失败：显示重新解读按钮 */}
        {isReportType && interpretFailed && !isStreaming && (
          <div className="flex mb-4 justify-start">
            <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mr-2"
              style={{ background: 'linear-gradient(135deg, #ff4d4f, #ff7875)' }}>
              <span className="text-white text-xs">!</span>
            </div>
            <div className="max-w-[75%]">
              <div className="rounded-2xl px-4 py-3 leading-relaxed bg-white text-red-500 rounded-tl-sm shadow-sm"
                style={{ fontSize: chatFontSize }}>
                抱歉，本次解读未能完成。
                <button
                  onClick={retryInterpret}
                  className="ml-2 px-3 py-1 rounded bg-red-500 text-white text-xs"
                >
                  重新解读
                </button>
              </div>
            </div>
          </div>
        )}

        {/* [2026-04-25] 报告解读进行中：首字节到达前显示"AI 正在解读..."骨架态 */}
        {isReportType && !isStreaming && !interpretFailed && !messages.some((m) => m.role === 'assistant' && m.id !== 'welcome') && (
          <div className="flex mb-4 justify-start">
            <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mr-2"
              style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
              <span className="text-white text-xs">AI</span>
            </div>
            <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm flex items-center gap-2">
              <SpinLoading style={{ '--size': '18px', '--color': '#52c41a' }} />
              <span className="text-gray-500 text-sm">AI 正在解读您的报告，请稍候…</span>
            </div>
          </div>
        )}

        {/* Streaming message */}
        {isStreaming && streamingContent && (
          <div className="flex mb-4 justify-start">
            <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mr-2"
              style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
              <span className="text-white text-xs">AI</span>
            </div>
            <div className="max-w-[75%]">
              <div className="rounded-2xl px-4 py-3 leading-relaxed bg-white text-gray-700 rounded-tl-sm shadow-sm streaming-cursor"
                style={{ fontSize: chatFontSize }}>
                {renderMarkdown(streamingContent)}
              </div>
            </div>
          </div>
        )}

        {loading && !isStreaming && (
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

      {/* Upload progress bar */}
      {uploadPercent >= 0 && (
        <div className="bg-white px-4 py-2 border-t border-gray-100">
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{ width: `${uploadPercent}%`, background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
              />
            </div>
            <span className="text-xs text-gray-500 w-10 text-right">{uploadPercent}%</span>
          </div>
        </div>
      )}

      {/* Function buttons bar */}
      {funcButtons.length > 0 && (
        <div className="bg-white border-t border-gray-100" style={{ position: 'relative' }}>
          <div
            ref={funcScrollRef}
            className="flex items-center gap-2 overflow-x-auto px-3 py-1 no-scrollbar"
            style={{ scrollBehavior: 'smooth', WebkitOverflowScrolling: 'touch', height: 44 }}
          >
            {funcButtons.map((btn) => {
              const isDrugBtn = btn.button_type === 'drug_identify';
              const isDisabled = isDrugBtn && drugRecognizing;
              return (
              <button
                key={btn.id}
                onClick={() => !isDisabled && handleFuncBtnClick(btn)}
                disabled={isDisabled}
                className="flex items-center gap-1 flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-all active:scale-95"
                style={{
                  background: '#f5f5f5',
                  border: '1px solid #e8e8e8',
                  color: '#333',
                  whiteSpace: 'nowrap',
                  opacity: isDisabled ? 0.5 : 1,
                }}
              >
                <span style={{ fontSize: 13 }}>{getFuncBtnEmoji(btn)}</span>
                <span>{isDrugBtn && drugRecognizing ? '识别中...' : btn.name}</span>
              </button>
              );
            })}
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

      {/* Hidden drug identify file inputs */}
      <input ref={drugCameraRef} type="file" accept="image/*" capture="environment" className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleDrugRecognize([f]); e.target.value = ''; }} />
      <input ref={drugAlbumRef} type="file" accept="image/*" multiple className="hidden"
        onChange={(e) => {
          const fileList = e.target.files;
          if (fileList && fileList.length > 0) {
            const files = Array.from(fileList).slice(0, drugIdentifyMaxPhotos);
            handleDrugRecognize(files);
          }
          e.target.value = '';
        }} />

      {/* Drug identify ActionSheet */}
      <ActionSheet
        visible={drugActionSheetVisible}
        extra={drugIdentifyTip ? <div className="text-center text-xs text-gray-500 py-2 px-4">{drugIdentifyTip}</div> : undefined}
        actions={[
          { text: '拍照', key: 'camera', disabled: drugRecognizing, onClick: () => { setDrugActionSheetVisible(false); drugCameraRef.current?.click(); } },
          { text: '从相册选择', key: 'album', disabled: drugRecognizing, onClick: () => { setDrugActionSheetVisible(false); drugAlbumRef.current?.click(); } },
        ]}
        cancelText="取消"
        onClose={() => setDrugActionSheetVisible(false)}
      />

      <div className="bg-white px-3 py-3 flex items-end gap-2 safe-area-bottom">
        {/* [2026-04-25] report_interpret/report_compare 会话：只读咨询人标签，禁止切换 */}
        {isReportType ? (
          <div
            className="w-10 h-10 flex-shrink-0 flex items-center justify-center rounded-full"
            style={{ background: getRelationColor(currentRelationLabel), border: 'none' }}
            title={`当前报告所属人：${currentRelationLabel}`}
            aria-label={`当前报告所属人：${currentRelationLabel}`}
          >
            <span style={{ color: '#fff', fontSize: 11, fontWeight: 600, lineHeight: 1.1, textAlign: 'center' }}>
              {currentRelationLabel.length > 2 ? currentRelationLabel.slice(0, 2) : currentRelationLabel}
            </span>
          </div>
        ) : (
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
          </div>
        )}

        <button
          onClick={sendMessage}
          disabled={!inputVal.trim() || loading}
          className="flex-shrink-0 flex items-center justify-center"
          style={{
            width: 36,
            height: 36,
            borderRadius: '50%',
            border: 'none',
            background: inputVal.trim() ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#e8e8e8',
            color: inputVal.trim() ? '#fff' : '#999',
            cursor: inputVal.trim() ? 'pointer' : 'default',
            fontSize: 14,
          }}
        >
          ➤
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

      {/* Module 9: Share popup */}
      <Popup
        visible={sharePopupVisible}
        onMaskClick={() => setSharePopupVisible(false)}
        position="bottom"
        bodyStyle={{ borderRadius: '16px 16px 0 0' }}
      >
        <div className="px-4 pb-6">
          <div className="flex items-center justify-between py-4 border-b border-gray-100">
            <span className="text-base font-semibold">将1轮对话分享至</span>
            <button onClick={() => setSharePopupVisible(false)} className="text-gray-400 text-xl leading-none">×</button>
          </div>
          <div className="flex gap-4 mt-4 justify-center">
            <button
              className="flex flex-col items-center gap-2 px-6 py-4 rounded-xl active:bg-gray-50"
              style={{ background: '#f9f9f9' }}
              onClick={handleShareToWechat}
              disabled={shareLoading}
            >
              <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ background: '#07c160' }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="#fff"><path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm3.297 2.594c-3.232 0-7.455 2.174-7.455 5.906 0 3.07 3.073 5.906 7.455 5.906.652 0 1.297-.082 1.848-.253a.73.73 0 0 1 .56.065l1.428.825a.27.27 0 0 0 .134.044c.11 0 .218-.1.218-.222 0-.055-.02-.108-.033-.16l-.3-1.123a.49.49 0 0 1 .167-.519c1.327-1.071 2.48-2.679 2.48-4.563-.003-3.732-3.27-5.906-6.502-5.906zm-1.896 2.857c.502 0 .91.414.91.923a.917.917 0 0 1-.91.923.917.917 0 0 1-.909-.923c0-.51.408-.923.91-.923zm3.995 0c.502 0 .91.414.91.923a.917.917 0 0 1-.91.923.917.917 0 0 1-.91-.923c0-.51.408-.923.91-.923z"/></svg>
              </div>
              <span className="text-xs text-gray-600">微信好友</span>
            </button>
            <button
              className="flex flex-col items-center gap-2 px-6 py-4 rounded-xl active:bg-gray-50"
              style={{ background: '#f9f9f9' }}
              onClick={handleSharePoster}
              disabled={shareLoading}
            >
              <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <polyline points="21 15 16 10 5 21" />
                </svg>
              </div>
              <span className="text-xs text-gray-600">生成图片</span>
            </button>
          </div>
          {shareLoading && (
            <div className="flex items-center justify-center mt-4 gap-2">
              <SpinLoading style={{ '--size': '18px', '--color': '#52c41a' }} />
              <span className="text-sm text-gray-400">生成中...</span>
            </div>
          )}
        </div>
      </Popup>

      {/* Poster preview */}
      {posterPreviewVisible && posterUrl && (
        <div
          className="fixed inset-0 z-50 bg-black/70 flex flex-col items-center justify-center px-6"
          onClick={() => setPosterPreviewVisible(false)}
        >
          <img src={posterUrl} alt="分享海报" className="max-w-full max-h-[70vh] rounded-xl shadow-lg" />
          <p className="text-white text-sm mt-4">长按图片保存到相册</p>
          <button
            className="mt-3 px-6 py-2 rounded-full text-sm font-medium text-white"
            style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
            onClick={(e) => { e.stopPropagation(); setPosterPreviewVisible(false); }}
          >
            关闭
          </button>
        </div>
      )}

      {/* [2026-04-23 公共页报告卡片迁移] 多图预览器（左右滑动 + 小圆点） */}
      <ImageViewer.Multi
        images={previewImages}
        visible={previewIndex >= 0}
        defaultIndex={Math.max(0, previewIndex)}
        onClose={() => { setPreviewIndex(-1); setPreviewImages([]); }}
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
