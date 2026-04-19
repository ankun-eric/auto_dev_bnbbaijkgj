'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
  NavBar, Card, Button, Radio, Space, ProgressBar, Toast, Result,
  SpinLoading, Empty, Popup, ImageUploader, Tag, DatePicker,
} from 'antd-mobile';
import type { ImageUploadItem } from 'antd-mobile/es/components/image-uploader';
import api from '@/lib/api';
import { checkFileSize } from '@/lib/upload-utils';

const constitutionQuestions = [
  { id: 1, q: '您是否容易疲劳？', options: ['从不', '偶尔', '经常', '总是'] },
  { id: 2, q: '您是否容易气短？', options: ['从不', '偶尔', '经常', '总是'] },
  { id: 3, q: '您手脚是否容易冰凉？', options: ['从不', '偶尔', '经常', '总是'] },
  { id: 4, q: '您是否容易口干咽燥？', options: ['从不', '偶尔', '经常', '总是'] },
  { id: 5, q: '您是否容易烦躁焦虑？', options: ['从不', '偶尔', '经常', '总是'] },
  { id: 6, q: '您的睡眠质量如何？', options: ['很好', '一般', '较差', '很差'] },
  { id: 7, q: '您的食欲如何？', options: ['很好', '一般', '较差', '很差'] },
  { id: 8, q: '您是否容易感冒？', options: ['从不', '偶尔', '经常', '总是'] },
];

interface TcmConfig {
  tongue_diagnosis_enabled: boolean;
  face_diagnosis_enabled: boolean;
  constitution_test_enabled: boolean;
}

interface FeatureItem {
  key: string;
  title: string;
  desc: string;
  icon: string;
}

interface DiagnosisRecord {
  id: number;
  constitution_type: string;
  description: string;
  created_at: string;
  family_member?: { id: number; nickname: string; relationship_type: string; is_self?: boolean; relation_type_name?: string } | null;
}

interface FamilyMemberInfo {
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
  '本人': '👤', '爸爸': '👨', '妈妈': '👩', '老公': '👨‍❤️‍👨', '老婆': '👩‍❤️‍👩',
  '儿子': '👦', '女儿': '👧', '哥哥': '👱‍♂️', '弟弟': '🧑', '姐姐': '👱‍♀️', '妹妹': '👧',
  '爷爷': '👴', '奶奶': '👵', '外公': '👴', '外婆': '👵', '其他': '🧑',
  '父亲': '👨', '母亲': '👩', '配偶': '💑', '子女': '👧', '兄弟姐妹': '👫',
};

function getMemberEmoji(name: string): string {
  return RELATION_EMOJI[name] || '🧑';
}

function getMemberTagLabel(member: DiagnosisRecord['family_member']): string {
  if (!member) return '本人';
  if (member.is_self) return '本人';
  return member.nickname || member.relation_type_name || member.relationship_type || '本人';
}

function formatTime(dateStr: string) {
  const d = new Date(dateStr);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const CONSTITUTION_COLORS: Record<string, string> = {
  '气虚质': '#fa8c16',
  '阳虚质': '#1890ff',
  '阴虚质': '#eb2f96',
  '痰湿质': '#13c2c2',
  '湿热质': '#f5222d',
  '血瘀质': '#722ed1',
  '气郁质': '#2f54eb',
  '特禀质': '#faad14',
  '平和质': '#52c41a',
};

function getConstitutionColor(type: string): string {
  return CONSTITUTION_COLORS[type] || '#52c41a';
}

export default function TcmPage() {
  const router = useRouter();
  const [activeFeature, setActiveFeature] = useState('');
  const [tongueImages, setTongueImages] = useState<ImageUploadItem[]>([]);
  const [faceImages, setFaceImages] = useState<ImageUploadItem[]>([]);
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [showResult, setShowResult] = useState(false);
  const [constitutionResult, setConstitutionResult] = useState<{
    type: string;
    description: string;
    features: string;
    diet: string;
    exercise: string;
    lifestyle: string;
  } | null>(null);
  const [submittingTest, setSubmittingTest] = useState(false);

  // Dynamic config
  const [tcmConfig, setTcmConfig] = useState<TcmConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(true);

  // Diagnosis history
  const [diagnosisHistory, setDiagnosisHistory] = useState<DiagnosisRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  // Member selection popup
  const [memberPopupVisible, setMemberPopupVisible] = useState(false);
  const [familyMembers, setFamilyMembers] = useState<FamilyMemberInfo[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);
  const [pendingFlow, setPendingFlow] = useState<'constitution' | 'tongue' | 'face' | null>(null);

  // Add member popup
  const [addMemberPopupVisible, setAddMemberPopupVisible] = useState(false);
  const [relationTypes, setRelationTypes] = useState<RelationType[]>([]);
  const [addStep, setAddStep] = useState<'relation' | 'info'>('relation');
  const [selectedRelation, setSelectedRelation] = useState<RelationType | null>(null);
  const [newNickname, setNewNickname] = useState('');
  const [newGender, setNewGender] = useState('');
  const [newBirthday, setNewBirthday] = useState('');
  const [addLoading, setAddLoading] = useState(false);
  const [newBirthdayPickerVisible, setNewBirthdayPickerVisible] = useState(false);

  const fetchConfig = useCallback(async () => {
    setConfigLoading(true);
    try {
      const res: any = await api.get('/api/tcm/config');
      const data = res.data || res;
      setTcmConfig({
        tongue_diagnosis_enabled: data.tongue_diagnosis_enabled ?? true,
        face_diagnosis_enabled: data.face_diagnosis_enabled ?? true,
        constitution_test_enabled: data.constitution_test_enabled ?? true,
      });
    } catch {
      setTcmConfig({ tongue_diagnosis_enabled: true, face_diagnosis_enabled: true, constitution_test_enabled: true });
    } finally {
      setConfigLoading(false);
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res: any = await api.get('/api/tcm/diagnosis', { params: { page: 1, page_size: 20 } });
      const data = res.data || res;
      setDiagnosisHistory(data.items || []);
    } catch {
      setDiagnosisHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
    fetchHistory();
  }, [fetchConfig, fetchHistory]);

  const features: FeatureItem[] = [];
  if (tcmConfig) {
    if (tcmConfig.tongue_diagnosis_enabled) {
      features.push({ key: 'tongue', title: '舌诊', desc: '拍摄舌头照片，AI分析舌象', icon: '👅' });
    }
    if (tcmConfig.face_diagnosis_enabled) {
      features.push({ key: 'face', title: '面诊', desc: '拍摄面部照片，AI分析面色', icon: '🧑' });
    }
    if (tcmConfig.constitution_test_enabled) {
      features.push({ key: 'constitution', title: '体质测评', desc: '回答问卷，判断体质类型', icon: '📋' });
    }
  }

  const handleUpload = async (file: File) => {
    const sizeCheck = await checkFileSize(file, 'tcm_image');
    if (!sizeCheck.ok) {
      Toast.show({ content: `文件大小超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'fail' });
      throw new Error('file too large');
    }
    return { url: URL.createObjectURL(file) };
  };

  const handleTongueAnalyze = () => {
    if (tongueImages.length === 0) {
      Toast.show({ content: '请先上传舌头照片' });
      return;
    }
    Toast.show({ icon: 'loading', content: 'AI舌象分析中...', duration: 0 });
    setTimeout(() => {
      Toast.clear();
      const sessionId = `tcm-tongue-${Date.now()}`;
      router.push(`/chat/${sessionId}?type=tcm&msg=${encodeURIComponent('请根据我上传的舌象照片进行中医舌诊分析')}`);
    }, 1500);
  };

  const handleFaceAnalyze = () => {
    if (faceImages.length === 0) {
      Toast.show({ content: '请先上传面部照片' });
      return;
    }
    Toast.show({ icon: 'loading', content: 'AI面诊分析中...', duration: 0 });
    setTimeout(() => {
      Toast.clear();
      const sessionId = `tcm-face-${Date.now()}`;
      router.push(`/chat/${sessionId}?type=tcm&msg=${encodeURIComponent('请根据我上传的面部照片进行中医面诊分析')}`);
    }, 1500);
  };

  const answerQuestion = (value: string) => {
    const next = { ...answers, [constitutionQuestions[currentQ].id]: value };
    setAnswers(next);
    if (currentQ < constitutionQuestions.length - 1) {
      setTimeout(() => setCurrentQ(currentQ + 1), 300);
    } else {
      // 9 题答完 → 弹出咨询人选择，选定后再提交（最后一步必选咨询人）
      setTimeout(async () => {
        setPendingFlow('constitution');
        await fetchMemberList();
        setMemberPopupVisible(true);
      }, 300);
    }
  };

  const submitConstitutionTest = async (
    finalAnswers: Record<number, string>,
    memberId: number | null,
  ) => {
    const answersArr = Object.entries(finalAnswers).map(([qid, value]) => ({
      question_id: Number(qid),
      answer_value: String(value),
    }));
    if (answersArr.length === 0) {
      Toast.show({ content: '请先完成体质测评', icon: 'fail' });
      return;
    }
    setSubmittingTest(true);
    try {
      const payload: any = { answers: answersArr };
      if (memberId !== null && memberId !== -1) {
        payload.family_member_id = memberId;
      }
      const res: any = await api.post('/api/tcm/constitution-test', payload);
      const data = res.data || res;
      setConstitutionResult({
        type: data.constitution_type || '未知',
        description: data.constitution_description || data.description || '',
        features: data.syndrome_analysis || data.features || '',
        diet: data.health_plan || data.diet_suggestion || '',
        exercise: data.exercise_suggestion || '',
        lifestyle: data.lifestyle_suggestion || '',
      });
      setShowResult(true);
      fetchHistory();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '提交测评失败，请重试';
      Toast.show({ content: typeof detail === 'string' ? detail : '提交测评失败，请重试', icon: 'fail' });
    } finally {
      setSubmittingTest(false);
    }
  };

  const fetchMemberList = async () => {
    try {
      const res: any = await api.get('/api/family/members');
      const data = res.data || res;
      let items: FamilyMemberInfo[] = Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : [];
      if (!items.some((m) => m.is_self)) {
        items = [{ id: -1, nickname: '本人', relationship_type: 'self', is_self: true, relation_type_name: '本人' }, ...items];
      }
      setFamilyMembers(items);
      setSelectedMemberId(items[0]?.id ?? null);
    } catch {
      setFamilyMembers([{ id: -1, nickname: '本人', relationship_type: 'self', is_self: true, relation_type_name: '本人' }]);
      setSelectedMemberId(-1);
    }
  };

  const handleConstitutionConsult = async () => {
    await fetchMemberList();
    setMemberPopupVisible(true);
  };

  const handleMemberConfirmAndNavigate = async () => {
    setMemberPopupVisible(false);
    const memberId = selectedMemberId !== null && selectedMemberId !== -1 ? selectedMemberId : null;

    // 情形 1: 答完 9 题但还未提交（无 constitutionResult）→ 提交测评
    if (!constitutionResult) {
      await submitConstitutionTest(answers, memberId);
      return;
    }

    // 情形 2: 已得到测评结果，跳转 chat 咨询
    try {
      const res: any = await api.post('/api/chat/sessions', {
        session_type: 'constitution',
        title: `体质分析-${constitutionResult.type}`,
        family_member_id: memberId,
      });
      const data = res.data || res;
      router.push(`/chat/${data.id}?type=constitution`);
    } catch {
      Toast.show({ content: '创建会话失败', icon: 'fail' });
    }
  };

  const openAddMemberPopup = async () => {
    setAddStep('relation');
    setSelectedRelation(null);
    setNewNickname(''); setNewGender(''); setNewBirthday('');
    try {
      const res: any = await api.get('/api/relation-types');
      const data = res.data || res;
      const items = Array.isArray(data.items) ? data.items : [];
      setRelationTypes(items.filter((rt: any) => rt.name !== '本人'));
    } catch { setRelationTypes([]); }
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
        nickname: newNickname.trim(), name: newNickname.trim(),
        relationship_type: selectedRelation.name, relation_type_id: selectedRelation.id,
        gender: newGender, birthday: newBirthday,
      };
      const res: any = await api.post('/api/family/members', body);
      const created = res.data || res;
      setAddMemberPopupVisible(false);

      await fetchMemberList();
      if (created.id) setSelectedMemberId(created.id);
      Toast.show({ content: '成员添加成功', icon: 'success' });
    } catch {
      Toast.show({ content: '添加失败，请重试', icon: 'fail' });
    }
    setAddLoading(false);
  };

  const progress = Math.round(((currentQ + (answers[constitutionQuestions[currentQ]?.id] ? 1 : 0)) / constitutionQuestions.length) * 100);

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar
        onBack={() => {
          if (activeFeature) {
            setActiveFeature('');
            setShowResult(false);
            setCurrentQ(0);
            setAnswers({});
            setConstitutionResult(null);
          } else {
            router.back();
          }
        }}
        style={{ background: '#fff' }}
      >
        中医养生
      </NavBar>

      {!activeFeature && (
        <div className="px-4 pt-4 pb-6">
          <div
            className="rounded-xl p-6 mb-4 text-center"
            style={{ background: 'linear-gradient(135deg, #52c41a20, #13c2c220)' }}
          >
            <div className="text-3xl mb-2">🏥</div>
            <h2 className="font-bold text-lg text-gray-800">智能中医养生</h2>
            <p className="text-xs text-gray-500 mt-1">融合传统中医智慧与AI技术</p>
          </div>

          {configLoading ? (
            <div className="flex items-center justify-center py-10">
              <SpinLoading style={{ '--size': '24px', '--color': '#52c41a' }} />
            </div>
          ) : features.length === 0 ? (
            <div className="text-center py-10 text-gray-400 text-sm">暂无可用功能</div>
          ) : (
            features.map((f) => (
              <Card
                key={f.key}
                onClick={() => setActiveFeature(f.key)}
                style={{ marginBottom: 12, borderRadius: 12 }}
              >
                <div className="flex items-center">
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl mr-4"
                    style={{ background: '#52c41a15' }}
                  >
                    {f.icon}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium">{f.title}</div>
                    <div className="text-xs text-gray-400 mt-1">{f.desc}</div>
                  </div>
                  <span className="text-gray-300">›</span>
                </div>
              </Card>
            ))
          )}

          {/* History section */}
          <div className="mt-6">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-semibold text-gray-700">历史记录</span>
            </div>
            {historyLoading ? (
              <div className="flex items-center justify-center py-8">
                <SpinLoading style={{ '--size': '24px', '--color': '#52c41a' }} />
              </div>
            ) : diagnosisHistory.length === 0 ? (
              <div className="bg-white rounded-2xl py-8 text-center shadow-sm">
                <Empty
                  description="暂无诊断记录"
                  style={{ '--description-font-size': '13px' } as React.CSSProperties}
                />
              </div>
            ) : (
              <div className="space-y-2">
                {diagnosisHistory.map((item) => {
                  const color = getConstitutionColor(item.constitution_type);
                  const memberLabel = getMemberTagLabel(item.family_member);
                  return (
                    <div
                      key={item.id}
                      className="bg-white rounded-xl p-3 shadow-sm active:bg-gray-50 transition-colors cursor-pointer"
                      onClick={() => router.push(`/tcm/diagnosis/${item.id}`)}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className="w-11 h-11 rounded-full flex items-center justify-center flex-shrink-0"
                          style={{ background: `${color}15`, border: `1.5px solid ${color}` }}
                        >
                          <span className="text-xs font-bold" style={{ color }}>
                            {item.constitution_type.replace('质', '')}
                          </span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-sm text-gray-800">{item.constitution_type}</div>
                          <div className="text-xs text-gray-400 mt-0.5 truncate">{item.description || '点击查看详情'}</div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[11px] text-gray-300">{formatTime(item.created_at)}</span>
                            <span
                              className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0"
                              style={{ background: `${color}15`, color }}
                            >
                              {memberLabel}
                            </span>
                          </div>
                        </div>
                        <span className="text-gray-300 text-lg">›</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {activeFeature === 'tongue' && (
        <div className="px-4 pt-4">
          <div className="card">
            <div className="section-title">拍摄舌头照片</div>
            <p className="text-xs text-gray-400 mb-3">请在自然光下伸出舌头拍照，确保舌面清晰可见</p>
            <ImageUploader
              value={tongueImages}
              onChange={setTongueImages}
              upload={handleUpload}
              maxCount={3}
              style={{ '--cell-size': '100px' }}
            />
            <Button
              block
              onClick={handleTongueAnalyze}
              style={{
                marginTop: 16,
                background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                color: '#fff',
                border: 'none',
                borderRadius: 24,
                height: 44,
              }}
            >
              开始舌诊分析
            </Button>
          </div>
          <Card style={{ borderRadius: 12 }}>
            <div className="text-sm font-medium mb-2">拍摄提示</div>
            <ul className="text-xs text-gray-500 space-y-1">
              <li>• 选择自然光线充足的环境</li>
              <li>• 拍摄前避免进食有色食物</li>
              <li>• 自然伸出舌头，不要过分用力</li>
              <li>• 确保照片清晰，舌面完整</li>
            </ul>
          </Card>
        </div>
      )}

      {activeFeature === 'face' && (
        <div className="px-4 pt-4">
          <div className="card">
            <div className="section-title">拍摄面部照片</div>
            <p className="text-xs text-gray-400 mb-3">请在自然光下拍摄正面照片，不化妆效果更佳</p>
            <ImageUploader
              value={faceImages}
              onChange={setFaceImages}
              upload={handleUpload}
              maxCount={3}
              style={{ '--cell-size': '100px' }}
            />
            <Button
              block
              onClick={handleFaceAnalyze}
              style={{
                marginTop: 16,
                background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                color: '#fff',
                border: 'none',
                borderRadius: 24,
                height: 44,
              }}
            >
              开始面诊分析
            </Button>
          </div>
        </div>
      )}

      {activeFeature === 'constitution' && !showResult && (
        <div className="px-4 pt-4">
          {submittingTest ? (
            <div className="flex flex-col items-center justify-center py-20">
              <SpinLoading style={{ '--size': '36px', '--color': '#52c41a' }} />
              <span className="text-sm text-gray-500 mt-4">正在分析体质...</span>
            </div>
          ) : (
            <div className="card">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">
                  第 {currentQ + 1} / {constitutionQuestions.length} 题
                </span>
                <span className="text-xs text-primary">{progress}%</span>
              </div>
              <ProgressBar
                percent={progress}
                style={{
                  '--track-width': '6px',
                  '--fill-color': '#52c41a',
                  marginBottom: 20,
                }}
              />
              <div className="text-base font-medium mb-4">
                {constitutionQuestions[currentQ].q}
              </div>
              <Space direction="vertical" block>
                {constitutionQuestions[currentQ].options.map((opt) => (
                  <div
                    key={opt}
                    className={`p-3 rounded-xl border text-sm text-center cursor-pointer transition-all ${
                      answers[constitutionQuestions[currentQ].id] === opt
                        ? 'border-primary bg-green-50 text-primary'
                        : 'border-gray-200'
                    }`}
                    onClick={() => answerQuestion(opt)}
                  >
                    {opt}
                  </div>
                ))}
              </Space>
            </div>
          )}
        </div>
      )}

      {activeFeature === 'constitution' && showResult && constitutionResult && (
        <div className="px-4 pt-4 pb-6">
          <Result
            status="success"
            title="体质分析完成"
            description="根据您的回答，AI已完成体质辨识"
          />
          <Card style={{ borderRadius: 12, marginTop: 16 }}>
            <div className="text-center mb-4">
              <div className="text-3xl mb-2">🌿</div>
              <div className="text-lg font-bold" style={{ color: getConstitutionColor(constitutionResult.type) }}>
                {constitutionResult.type}
              </div>
              {constitutionResult.description && (
                <div className="text-xs text-gray-400 mt-1">{constitutionResult.description}</div>
              )}
            </div>
            <div className="space-y-2 text-sm text-gray-600">
              {constitutionResult.features && <p><strong>体质特征：</strong>{constitutionResult.features}</p>}
              {constitutionResult.diet && <p><strong>饮食建议：</strong>{constitutionResult.diet}</p>}
              {constitutionResult.exercise && <p><strong>运动建议：</strong>{constitutionResult.exercise}</p>}
              {constitutionResult.lifestyle && <p><strong>起居建议：</strong>{constitutionResult.lifestyle}</p>}
            </div>
          </Card>
          <Button
            block
            onClick={handleConstitutionConsult}
            style={{
              marginTop: 16,
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              color: '#fff',
              border: 'none',
              borderRadius: 24,
              height: 44,
            }}
          >
            获取详细调理方案
          </Button>
        </div>
      )}

      {/* Member selection popup */}
      <Popup
        visible={memberPopupVisible}
        onMaskClick={() => { setMemberPopupVisible(false); setPendingFlow(null); }}
        position="bottom"
        bodyStyle={{ borderRadius: '16px 16px 0 0', maxHeight: '70vh', overflowY: 'auto' }}
      >
        <div className="px-4 pb-6">
          <div className="flex items-center justify-between py-4 border-b border-gray-100">
            <span className="text-base font-semibold">
              {pendingFlow === 'tongue' ? '为谁做舌诊' : pendingFlow === 'face' ? '为谁做面诊' : '为谁咨询'}
            </span>
            <button onClick={() => { setMemberPopupVisible(false); setPendingFlow(null); }} className="text-gray-400 text-xl leading-none">×</button>
          </div>

          <div className="mt-3 space-y-2">
            {familyMembers.map((m) => {
              const relationLabel = m.relation_type_name || m.relationship_type;
              const emoji = m.is_self ? '👤' : getMemberEmoji(relationLabel);
              const displayName = m.is_self ? '本人' : `${relationLabel} · ${m.nickname}`;
              return (
                <div
                  key={m.id}
                  className="flex items-center justify-between px-3 py-3 rounded-xl cursor-pointer"
                  style={{
                    background: selectedMemberId === m.id ? '#f6ffed' : '#f9f9f9',
                    border: selectedMemberId === m.id ? '1px solid #52c41a' : '1px solid transparent',
                  }}
                  onClick={() => setSelectedMemberId(m.id)}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full flex items-center justify-center text-xl"
                      style={{ background: selectedMemberId === m.id ? 'linear-gradient(135deg,#52c41a,#13c2c2)' : '#f0f0f0' }}>
                      {m.is_self && selectedMemberId === m.id ? <span className="text-white text-sm">我</span> : emoji}
                    </div>
                    <div><div className="text-sm font-medium">{displayName}</div></div>
                  </div>
                  <Radio
                    checked={selectedMemberId === m.id}
                    onChange={() => setSelectedMemberId(m.id)}
                    style={{ '--icon-size': '18px', '--font-size': '14px', '--gap': '6px' }}
                  />
                </div>
              );
            })}

            <div
              className="flex items-center gap-2 px-3 py-3 rounded-xl cursor-pointer"
              style={{ background: '#f9f9f9', border: '1px solid transparent' }}
              onClick={openAddMemberPopup}
            >
              <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-lg" style={{ background: '#52c41a' }}>+</div>
              <span className="text-sm font-medium" style={{ color: '#52c41a' }}>添加家庭成员</span>
            </div>
          </div>

          <Button
            block
            disabled={selectedMemberId === null}
            loading={submittingTest}
            onClick={handleMemberConfirmAndNavigate}
            style={{
              marginTop: 20,
              background: selectedMemberId === null
                ? '#d9d9d9'
                : 'linear-gradient(135deg, #52c41a, #13c2c2)',
              color: '#fff',
              border: 'none',
              borderRadius: 24,
              height: 46,
              fontSize: 15,
            }}
          >
            {pendingFlow === 'tongue'
              ? '确认并开始舌诊分析'
              : pendingFlow === 'face'
              ? '确认并开始面诊分析'
              : !constitutionResult
              ? '确认咨询人并提交测评'
              : '确认并咨询'}
          </Button>
        </div>
      </Popup>

      {/* Add member popup */}
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
                  <button key={rt.id} className="flex flex-col items-center py-2 rounded-xl transition-all"
                    style={{ background: isSelected ? 'linear-gradient(135deg, #f6ffed, #e6fffb)' : '#f9f9f9', border: isSelected ? '1.5px solid #52c41a' : '1.5px solid transparent' }}
                    onClick={() => { setSelectedRelation(rt); setAddStep('info'); }}
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
                  <input className="w-full bg-white text-sm rounded-xl px-3 py-2 outline-none border border-gray-200" placeholder="请输入姓名" value={newNickname} onChange={(e) => setNewNickname(e.target.value)} />
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">性别 <span style={{color:'#ff4d4f'}}>*</span></div>
                  <div className="flex gap-3">
                    {['male', 'female'].map((g) => (
                      <button key={g} className="flex-1 py-2 rounded-xl text-sm font-medium transition-all"
                        style={{ background: newGender === g ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#fff', color: newGender === g ? '#fff' : '#666', border: `1px solid ${newGender === g ? '#52c41a' : '#e8e8e8'}` }}
                        onClick={() => setNewGender(g)}
                      >{g === 'male' ? '男' : '女'}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">出生日期 <span style={{color:'#ff4d4f'}}>*</span></div>
                  <button className="w-full bg-white text-sm rounded-xl px-3 py-2 text-left border border-gray-200 flex items-center justify-between" onClick={() => setNewBirthdayPickerVisible(true)}>
                    <span style={{ color: newBirthday ? '#333' : '#bbb' }}>{newBirthday || '请选择出生日期'}</span>
                    <span>📅</span>
                  </button>
                </div>
              </div>
              <button
                className="w-full mt-4 py-3 rounded-2xl text-white font-semibold text-sm"
                style={{ background: addLoading ? '#d9d9d9' : 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
                disabled={addLoading} onClick={handleAddMemberConfirm}
              >{addLoading ? '添加中...' : '确认添加'}</button>
            </div>
          )}
        </div>
      </Popup>

      <DatePicker
        visible={newBirthdayPickerVisible}
        onClose={() => setNewBirthdayPickerVisible(false)}
        precision="day" max={new Date()} min={new Date('1900-01-01')}
        onConfirm={(val) => {
          const d = val as Date;
          const str = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
          setNewBirthday(str);
          setNewBirthdayPickerVisible(false);
        }}
        title="选择出生日期"
      />
    </div>
  );
}
