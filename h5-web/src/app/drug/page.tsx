'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Toast, Empty, SpinLoading, Tag, Button, Popup, Radio, Input, DatePicker } from 'antd-mobile';
import api from '@/lib/api';
import { checkFileSize, uploadWithProgress } from '@/lib/upload-utils';
import DiseaseTagSelector, { type DiseaseItem } from '@/components/DiseaseTagSelector';

const MAX_IMAGES = 5;
const MAX_SIZE = 20 * 1024 * 1024;

interface HistoryItem {
  id: number;
  session_id: number;
  drug_name: string;
  image_url: string;
  original_image_url?: string;
  image_count?: number;
  status: string;
  created_at: string;
  family_member?: { id: number; nickname: string; relationship_type: string; is_self?: boolean; relation_type_name?: string } | null;
}

interface SelectedFile {
  file: File;
  previewUrl: string;
  id: string;
}

interface FamilyMemberInfo {
  id: number;
  nickname: string;
  relationship_type: string;
  is_self?: boolean;
  relation_type_name?: string;
  birthday?: string;
  gender?: string;
  height?: number;
  weight?: number;
}

interface RelationType {
  id: number;
  name: string;
  sort_order: number;
}

interface DiseasePreset {
  id: number;
  name: string;
  category: string;
}

interface HealthProfile {
  nickname: string;
  birthday: string;
  gender: string;
  height: string;
  weight: string;
  chronic_diseases: DiseaseItem[];
  allergies: DiseaseItem[];
  genetic_diseases: DiseaseItem[];
}

const emptyProfile = (): HealthProfile => ({
  nickname: '', birthday: '', gender: '', height: '', weight: '',
  chronic_diseases: [], allergies: [], genetic_diseases: [],
});

const RELATION_EMOJI: Record<string, string> = {
  '本人': '👤', '爸爸': '👨', '妈妈': '👩', '老公': '👨‍❤️‍👨', '老婆': '👩‍❤️‍👩',
  '儿子': '👦', '女儿': '👧', '哥哥': '👱‍♂️', '弟弟': '🧑', '姐姐': '👱‍♀️', '妹妹': '👧',
  '爷爷': '👴', '奶奶': '👵', '外公': '👴', '外婆': '👵', '其他': '🧑',
  '父亲': '👨', '母亲': '👩', '配偶': '💑', '子女': '👧', '兄弟姐妹': '👫',
};

function getMemberEmoji(name: string): string {
  return RELATION_EMOJI[name] || '🧑';
}

function getMemberTagColor(relationshipType: string): string {
  const t = relationshipType || '';
  if (t === 'self' || t === '本人') return '#1677ff';
  if (['爸爸', '父亲'].includes(t)) return '#fa8c16';
  if (['妈妈', '母亲'].includes(t)) return '#eb2f96';
  if (['老公', '老婆', '配偶'].includes(t)) return '#722ed1';
  if (['儿子', '女儿', '子女'].includes(t)) return '#13c2c2';
  return '#8c8c8c';
}

function getMemberTagLabel(member: HistoryItem['family_member']): { label: string; color: string } {
  if (!member) return { label: '本人', color: '#1677ff' };
  const label = member.nickname || member.relation_type_name || member.relationship_type || '本人';
  const relType = member.is_self ? '本人' : (member.relation_type_name || member.relationship_type);
  return { label, color: getMemberTagColor(relType) };
}

function formatTime(dateStr: string) {
  const d = new Date(dateStr);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const STEP_ITEMS = [
  { title: '拍照/选图', desc: '最多5张' },
  { title: '选择对象', desc: '药品是谁的' },
  { title: 'AI 识别', desc: '智能分析药品' },
];

function StepBar({ current, onStepClick }: { current: number; onStepClick: (idx: number) => void }) {
  return (
    <div className="flex items-center justify-between px-2 py-3">
      {STEP_ITEMS.map((item, idx) => {
        const isActive = idx === current;
        const isDone = idx < current;
        const canClick = idx < current;
        return (
          <div key={idx} className="flex items-center flex-1">
            <button
              className="flex items-center gap-2 flex-1 min-w-0"
              disabled={!canClick}
              onClick={() => canClick && onStepClick(idx)}
            >
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold transition-all"
                style={{
                  background: isDone ? '#52c41a' : isActive ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#e8e8e8',
                  color: isDone || isActive ? '#fff' : '#999',
                }}
              >
                {isDone ? '✓' : idx + 1}
              </div>
              <div className="min-w-0">
                <div
                  className="text-xs font-medium truncate"
                  style={{ color: isActive ? '#52c41a' : isDone ? '#52c41a' : '#999' }}
                >
                  {item.title}
                </div>
              </div>
            </button>
            {idx < STEP_ITEMS.length - 1 && (
              <div
                className="h-px flex-shrink-0 mx-2"
                style={{ width: 20, background: idx < current ? '#52c41a' : '#e8e8e8' }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function DrugPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [recognizing, setRecognizing] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('AI识别中...');
  const [uploadPercent, setUploadPercent] = useState(-1);
  const [error, setError] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);

  const cameraInputRef = useRef<HTMLInputElement>(null);
  const albumInputRef = useRef<HTMLInputElement>(null);

  // Family member popup state
  const [memberPopupVisible, setMemberPopupVisible] = useState(false);
  const [familyMembers, setFamilyMembers] = useState<FamilyMemberInfo[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);
  const [profileEdits, setProfileEdits] = useState<HealthProfile>(emptyProfile());
  const [birthdayPickerVisible, setBirthdayPickerVisible] = useState(false);
  const [profileErrors, setProfileErrors] = useState<{nickname?: string; gender?: string; birthday?: string}>({});
  const [confirmLoading, setConfirmLoading] = useState(false);

  // Disease presets
  const [chronicPresets, setChronicPresets] = useState<DiseasePreset[]>([]);
  const [allergyPresets, setAllergyPresets] = useState<DiseasePreset[]>([]);
  const [geneticPresets, setGeneticPresets] = useState<DiseasePreset[]>([]);

  // Add member popup state
  const [addMemberPopupVisible, setAddMemberPopupVisible] = useState(false);
  const [relationTypes, setRelationTypes] = useState<RelationType[]>([]);
  const [addStep, setAddStep] = useState<'relation' | 'info'>('relation');
  const [selectedRelation, setSelectedRelation] = useState<RelationType | null>(null);
  const [newNickname, setNewNickname] = useState('');
  const [newGender, setNewGender] = useState('');
  const [newBirthday, setNewBirthday] = useState('');
  const [newHeight, setNewHeight] = useState('');
  const [newWeight, setNewWeight] = useState('');
  const [newMedicalHistories, setNewMedicalHistories] = useState<DiseaseItem[]>([]);
  const [newAllergies, setNewAllergies] = useState<DiseaseItem[]>([]);
  const [addLoading, setAddLoading] = useState(false);
  const [newBirthdayPickerVisible, setNewBirthdayPickerVisible] = useState(false);

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res: any = await api.get('/api/drug-identify/history', {
        params: { page: 1, page_size: 20 },
      });
      const data = res.data || res;
      setHistory(data.items || []);
    } catch {
      // ignore
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const addFiles = async (files: FileList | null) => {
    if (!files) return;
    const current = selectedFiles.length;
    const remaining = MAX_IMAGES - current;
    if (remaining <= 0) {
      Toast.show({ content: `最多只能选择${MAX_IMAGES}张图片` });
      return;
    }
    const toAdd = Array.from(files).slice(0, remaining);

    const valid: File[] = [];
    for (const f of toAdd) {
      const sizeCheck = await checkFileSize(f, 'drug_identify');
      if (!sizeCheck.ok) {
        Toast.show({ content: `文件 ${f.name} 超过限制（最大 ${sizeCheck.maxMb} MB），已跳过` });
        continue;
      }
      if (f.size > MAX_SIZE) {
        Toast.show({ content: '部分图片超过20MB，已跳过' });
        continue;
      }
      valid.push(f);
    }
    if (valid.length === 0) return;
    const newItems: SelectedFile[] = valid.map((file) => ({
      file,
      previewUrl: URL.createObjectURL(file),
      id: `${Date.now()}-${Math.random()}`,
    }));
    setSelectedFiles((prev) => [...prev, ...newItems]);
    setError('');
  };

  const removeFile = (id: string) => {
    setSelectedFiles((prev) => {
      const item = prev.find((f) => f.id === id);
      if (item) URL.revokeObjectURL(item.previewUrl);
      return prev.filter((f) => f.id !== id);
    });
  };

  const fetchDiseasePresets = async () => {
    try {
      const [cRes, aRes, gRes]: any[] = await Promise.all([
        api.get('/api/disease-presets', { params: { category: 'chronic' } }),
        api.get('/api/disease-presets', { params: { category: 'allergy' } }),
        api.get('/api/disease-presets', { params: { category: 'genetic' } }),
      ]);
      const c = cRes.data || cRes;
      const a = aRes.data || aRes;
      const g = gRes.data || gRes;
      setChronicPresets(Array.isArray(c.items) ? c.items : []);
      setAllergyPresets(Array.isArray(a.items) ? a.items : []);
      setGeneticPresets(Array.isArray(g.items) ? g.items : []);
    } catch { /* ignore */ }
  };

  const loadProfileFromMember = async (members: FamilyMemberInfo[], id: number | null) => {
    const m = id !== null ? members.find((x) => x.id === id) : undefined;
    if (m && m.id !== -1) {
      try {
        const res: any = await api.get(`/api/health/profile/member/${m.id}`);
        const p = res.data || res;
        setProfileEdits({
          nickname: p.nickname || m.nickname || '',
          birthday: p.birthday || m.birthday || '',
          gender: p.gender || m.gender || '',
          height: p.height != null ? String(p.height) : (m.height != null ? String(m.height) : ''),
          weight: p.weight != null ? String(p.weight) : (m.weight != null ? String(m.weight) : ''),
          chronic_diseases: p.chronic_diseases || [],
          allergies: p.allergies || [],
          genetic_diseases: p.genetic_diseases || [],
        });
      } catch {
        setProfileEdits({
          nickname: m.nickname || '', birthday: m.birthday || '', gender: m.gender || '',
          height: m.height != null ? String(m.height) : '',
          weight: m.weight != null ? String(m.weight) : '',
          chronic_diseases: [], allergies: [], genetic_diseases: [],
        });
      }
    } else {
      setProfileEdits(emptyProfile());
    }
  };

  const handleSelectMember = (id: number) => {
    setSelectedMemberId(id);
    setProfileErrors({});
    loadProfileFromMember(familyMembers, id);
  };

  const openMemberPopup = async () => {
    if (selectedFiles.length === 0) return;
    await fetchDiseasePresets();
    try {
      const res: any = await api.get('/api/family/members');
      const data = res.data || res;
      let items: FamilyMemberInfo[] = Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : [];
      if (!items.some((m) => m.is_self)) {
        items = [{ id: -1, nickname: '本人', relationship_type: 'self', is_self: true, relation_type_name: '本人' }, ...items];
      }
      setFamilyMembers(items);
      const defaultId = items[0]?.id ?? null;
      setSelectedMemberId(defaultId);
      loadProfileFromMember(items, defaultId);
    } catch {
      setFamilyMembers([{ id: -1, nickname: '本人', relationship_type: 'self', is_self: true, relation_type_name: '本人' }]);
      setSelectedMemberId(-1);
      setProfileEdits(emptyProfile());
    }
    setCurrentStep(1);
    setMemberPopupVisible(true);
  };

  const openAddMemberPopup = async () => {
    setAddStep('relation');
    setSelectedRelation(null);
    setNewNickname(''); setNewGender(''); setNewBirthday('');
    setNewHeight(''); setNewWeight('');
    setNewMedicalHistories([]); setNewAllergies([]);
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
      if (newHeight) body.height = Number(newHeight);
      if (newWeight) body.weight = Number(newWeight);
      if (newMedicalHistories.length) body.chronic_diseases = newMedicalHistories;
      if (newAllergies.length) body.allergies = newAllergies;

      const res: any = await api.post('/api/family/members', body);
      const created = res.data || res;
      setAddMemberPopupVisible(false);

      try {
        const membersRes: any = await api.get('/api/family/members');
        const mData = membersRes.data || membersRes;
        let items: FamilyMemberInfo[] = Array.isArray(mData.items) ? mData.items : Array.isArray(mData) ? mData : [];
        if (!items.some((m) => m.is_self)) {
          items = [{ id: -1, nickname: '本人', relationship_type: 'self', is_self: true, relation_type_name: '本人' }, ...items];
        }
        setFamilyMembers(items);
        if (created.id) {
          setSelectedMemberId(created.id);
          loadProfileFromMember(items, created.id);
        }
      } catch { /* keep existing */ }
    } catch {
      Toast.show({ content: '添加失败，请重试', icon: 'fail' });
    }
    setAddLoading(false);
  };

  const handleMemberConfirm = async () => {
    const errors: {nickname?: string; gender?: string; birthday?: string} = {};
    if (!profileEdits.nickname?.trim()) errors.nickname = '请输入姓名';
    if (!profileEdits.gender) errors.gender = '请选择性别';
    if (!profileEdits.birthday) errors.birthday = '请选择出生日期';
    if (Object.keys(errors).length > 0) {
      setProfileErrors(errors);
      Toast.show({ content: '请填写完整的必填信息' });
      return;
    }
    setProfileErrors({});
    setConfirmLoading(true);

    try {
      const memberId = selectedMemberId !== null && selectedMemberId !== -1 ? selectedMemberId : null;
      if (memberId !== null) {
        const updatePayload: any = {};
        if (profileEdits.nickname) updatePayload.nickname = profileEdits.nickname.trim();
        if (profileEdits.birthday) updatePayload.birthday = profileEdits.birthday;
        if (profileEdits.gender) updatePayload.gender = profileEdits.gender;
        if (profileEdits.height) updatePayload.height = Number(profileEdits.height);
        if (profileEdits.weight) updatePayload.weight = Number(profileEdits.weight);
        updatePayload.chronic_diseases = profileEdits.chronic_diseases;
        updatePayload.allergies = profileEdits.allergies;
        updatePayload.genetic_diseases = profileEdits.genetic_diseases;
        await api.put(`/api/health/profile/member/${memberId}`, updatePayload).catch(() => null);
      }
    } catch { /* ignore */ }

    setConfirmLoading(false);
    setMemberPopupVisible(false);
    setCurrentStep(2);
    handleSubmitWithMember();
  };

  const handleSubmitWithMember = async () => {
    if (selectedFiles.length === 0) return;
    setRecognizing(true);
    setError('');
    setUploadPercent(0);
    setUploadProgress(`正在上传 ${selectedFiles.length} 张图片...`);

    try {
      const formData = new FormData();
      selectedFiles.forEach((sf) => formData.append('files', sf.file));
      formData.append('scene_name', '拍照识药');

      const memberId = selectedMemberId !== null && selectedMemberId !== -1 ? selectedMemberId : null;
      if (memberId !== null) {
        formData.append('family_member_id', String(memberId));
      }

      const data: any = await uploadWithProgress(
        '/api/ocr/batch-recognize',
        formData,
        (pct) => {
          setUploadPercent(pct);
          if (pct >= 100) setUploadProgress('AI识别中...');
        },
        { timeout: 120000 },
      );

      if (data.session_id) {
        selectedFiles.forEach((sf) => URL.revokeObjectURL(sf.previewUrl));
        setSelectedFiles([]);
        router.push(`/drug/chat/${data.session_id}`);
      } else {
        setError('识别返回异常，请重试');
        setCurrentStep(0);
      }
    } catch {
      setError('识别失败，请重新拍照或选择图片');
      setCurrentStep(0);
    } finally {
      setRecognizing(false);
      setUploadPercent(-1);
      if (cameraInputRef.current) cameraInputRef.current.value = '';
      if (albumInputRef.current) albumInputRef.current.value = '';
    }
  };

  const handleStepClick = (idx: number) => {
    if (idx < currentStep && !recognizing) {
      setCurrentStep(idx);
    }
  };

  const selectedMember = familyMembers.find((m) => m.id === selectedMemberId);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <NavBar
        onBack={() => router.back()}
        style={{
          '--height': '48px',
          background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
          color: '#fff',
          '--border-bottom': 'none',
        } as React.CSSProperties}
      >
        <span className="text-white font-medium">拍照识药</span>
      </NavBar>

      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }}
      />
      <input
        ref={albumInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }}
      />

      {recognizing && (
        <div className="fixed inset-0 z-50 bg-black/50 flex flex-col items-center justify-center">
          <SpinLoading style={{ '--size': '48px', '--color': '#52c41a' }} />
          <span className="text-white text-base mt-4 font-medium">{uploadProgress}</span>
          {uploadPercent >= 0 && uploadPercent < 100 && (
            <div className="w-48 mt-3 flex items-center gap-2">
              <div className="flex-1 h-2 bg-white/20 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-300 bg-green-400"
                  style={{ width: `${uploadPercent}%` }}
                />
              </div>
              <span className="text-xs text-white/80 w-10 text-right">{uploadPercent}%</span>
            </div>
          )}
        </div>
      )}

      <div className="px-4 pt-2">
        <div className="bg-white rounded-2xl shadow-sm mb-3">
          <StepBar current={currentStep} onStepClick={handleStepClick} />
        </div>

        <div className="bg-white rounded-2xl p-6 flex flex-col items-center shadow-sm">
          <div
            className="w-20 h-20 rounded-full flex items-center justify-center mb-5"
            style={{ background: 'linear-gradient(135deg, #52c41a20, #13c2c220)' }}
          >
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#52c41a" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
              <circle cx="12" cy="13" r="4" />
            </svg>
          </div>

          <div className="flex gap-3 w-full mb-4">
            <button
              onClick={() => cameraInputRef.current?.click()}
              disabled={recognizing || selectedFiles.length >= MAX_IMAGES}
              className="flex-1 h-11 rounded-full text-white font-medium text-sm border-none"
              style={{
                background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                opacity: recognizing || selectedFiles.length >= MAX_IMAGES ? 0.6 : 1,
              }}
            >
              拍照识药
            </button>
            <button
              onClick={() => albumInputRef.current?.click()}
              disabled={recognizing || selectedFiles.length >= MAX_IMAGES}
              className="flex-1 h-11 rounded-full font-medium text-sm bg-white"
              style={{
                border: '1px solid #52c41a',
                color: '#52c41a',
                opacity: recognizing || selectedFiles.length >= MAX_IMAGES ? 0.6 : 1,
              }}
            >
              从相册选择
            </button>
          </div>

          <p className="text-xs text-gray-400 text-center">
            拍摄药品包装，AI 帮您解读用药信息，最多{MAX_IMAGES}张
          </p>

          {selectedFiles.length > 0 && (
            <div className="w-full mt-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-500">
                  已选 <span className="font-medium" style={{ color: '#52c41a' }}>{selectedFiles.length}</span>/{MAX_IMAGES} 张
                </span>
                {selectedFiles.length < MAX_IMAGES && (
                  <span className="text-xs text-gray-400">还可添加{MAX_IMAGES - selectedFiles.length}张</span>
                )}
              </div>
              <div className="grid grid-cols-4 gap-2">
                {selectedFiles.map((sf) => (
                  <div key={sf.id} className="relative aspect-square">
                    <img src={sf.previewUrl} alt="preview" className="w-full h-full object-cover rounded-lg" />
                    <button
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-gray-700 flex items-center justify-center"
                      onClick={() => removeFile(sf.id)}
                      disabled={recognizing}
                    >
                      <span className="text-white text-xs leading-none">×</span>
                    </button>
                  </div>
                ))}
              </div>

              <button
                className="w-full mt-3 py-2.5 rounded-full text-white text-sm font-medium border-none"
                style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
                onClick={openMemberPopup}
                disabled={recognizing}
              >
                下一步：选择咨询对象（{selectedFiles.length}张）
              </button>
            </div>
          )}

          {error && (
            <div className="mt-4 w-full text-center">
              <p className="text-sm text-red-500 mb-2">{error}</p>
              <Button
                size="small"
                onClick={() => { setError(''); cameraInputRef.current?.click(); }}
                style={{ color: '#52c41a', borderColor: '#52c41a', borderRadius: 20 }}
              >
                重新拍照
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* History section */}
      <div className="flex-1 px-4 pb-6 mt-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-gray-700">识别记录</span>
        </div>

        {historyLoading ? (
          <div className="flex items-center justify-center py-10">
            <SpinLoading style={{ '--size': '24px', '--color': '#52c41a' }} />
          </div>
        ) : history.length === 0 ? (
          <div className="bg-white rounded-2xl py-10 text-center shadow-sm">
            <Empty
              description="暂无识别记录，拍张药品照片试试吧"
              style={{ '--description-font-size': '13px' } as React.CSSProperties}
            />
          </div>
        ) : (
          <div className="space-y-2">
            {history.map((item) => {
              const memberTag = getMemberTagLabel(item.family_member);
              const imgUrl = item.original_image_url || item.image_url;
              return (
                <div
                  key={item.id}
                  className="bg-white rounded-xl p-3 shadow-sm active:bg-gray-50 transition-colors"
                  onClick={() => router.push(`/drug/chat/${item.session_id}`)}
                >
                  <div className="flex gap-3">
                    <div className="w-14 h-14 rounded-lg flex-shrink-0 bg-gray-100 overflow-hidden relative">
                      {imgUrl ? (
                        <>
                          <img src={imgUrl} alt={item.drug_name} className="w-full h-full object-cover" />
                          {item.image_count && item.image_count > 1 && (
                            <div
                              className="absolute bottom-0 left-0 right-0 text-center text-white text-[9px] py-0.5"
                              style={{ background: 'rgba(0,0,0,0.45)', borderRadius: '0 0 8px 8px' }}
                            >
                              共{item.image_count}张
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="1.5">
                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                            <circle cx="8.5" cy="8.5" r="1.5" />
                            <polyline points="21 15 16 10 5 21" />
                          </svg>
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm text-gray-800 truncate">
                        {item.drug_name || '未知药品'}
                      </div>
                      <div className="text-xs text-gray-400 mt-1">{formatTime(item.created_at)}</div>
                      <div className="flex items-center gap-1.5 mt-1.5">
                        <Tag
                          style={{
                            '--background-color': item.status === 'failed' ? '#f5222d15' : '#52c41a15',
                            '--text-color': item.status === 'failed' ? '#f5222d' : '#52c41a',
                            '--border-color': 'transparent',
                            fontSize: 10,
                          } as React.CSSProperties}
                        >
                          {item.status === 'failed' ? '识别失败' : '已识别'}
                        </Tag>
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0"
                          style={{ background: `${memberTag.color}15`, color: memberTag.color }}
                        >
                          {memberTag.label}
                        </span>
                      </div>
                    </div>
                    <div className="text-gray-300 text-lg self-center">›</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Family member selection popup */}
      <Popup
        visible={memberPopupVisible}
        onMaskClick={() => { setMemberPopupVisible(false); setCurrentStep(0); }}
        position="bottom"
        bodyStyle={{ borderRadius: '16px 16px 0 0', maxHeight: '90vh', overflowY: 'auto' }}
      >
        <div className="px-4 pb-6">
          <div className="flex items-center justify-between py-4 border-b border-gray-100">
            <span className="text-base font-semibold">选择咨询对象</span>
            <button onClick={() => { setMemberPopupVisible(false); setCurrentStep(0); }} className="text-gray-400 text-xl leading-none">×</button>
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
                  onClick={() => handleSelectMember(m.id)}
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
                    onChange={() => handleSelectMember(m.id)}
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
              <span className="text-sm text-primary font-medium" style={{ color: '#52c41a' }}>添加家庭成员</span>
            </div>
          </div>

          {/* Health profile editor */}
          <div className="mt-4 p-4 rounded-xl" style={{ background: '#f9f9f9', border: '1px solid #e8e8e8' }}>
            <div className="text-sm font-semibold mb-3 text-gray-600">
              {selectedMember?.is_self ? '我的' : (selectedMember ? `${selectedMember.nickname}的` : '')}健康档案
              <span className="text-xs text-gray-400 ml-2 font-normal">（可修改，点击确认后保存）</span>
            </div>
            <div className="space-y-3">
              <div>
                <div className="text-xs text-gray-500 mb-1">姓名 <span style={{color:'#ff4d4f'}}>*</span></div>
                <Input
                  placeholder="请输入姓名"
                  value={profileEdits.nickname}
                  onChange={(v) => { setProfileEdits((p) => ({ ...p, nickname: v })); if (v.trim()) setProfileErrors((e) => ({ ...e, nickname: undefined })); }}
                  style={{ '--font-size': '14px', background: '#fff', borderRadius: 8, padding: '6px 12px', border: '1px solid #d9d9d9' }}
                />
                {profileErrors.nickname && <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>{profileErrors.nickname}</div>}
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">出生日期 <span style={{color:'#ff4d4f'}}>*</span></div>
                <div className="bg-white rounded-lg px-3 py-2 text-sm cursor-pointer flex items-center justify-between" style={{ border: '1px solid #d9d9d9' }} onClick={() => setBirthdayPickerVisible(true)}>
                  <span style={{ color: profileEdits.birthday ? '#333' : '#bbb' }}>{profileEdits.birthday || '请选择出生日期'}</span>
                  <span className="text-gray-300">📅</span>
                </div>
                {profileErrors.birthday && <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>{profileErrors.birthday}</div>}
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">性别 <span style={{color:'#ff4d4f'}}>*</span></div>
                <div className="flex gap-3">
                  {['male', 'female'].map((g) => (
                    <div key={g} className="flex-1 text-center py-2 rounded-lg text-sm cursor-pointer"
                      style={{ background: profileEdits.gender === g ? '#52c41a' : '#fff', color: profileEdits.gender === g ? '#fff' : '#666', border: `1px solid ${profileEdits.gender === g ? '#52c41a' : '#d9d9d9'}` }}
                      onClick={() => { setProfileEdits((p) => ({ ...p, gender: g })); setProfileErrors((e) => ({ ...e, gender: undefined })); }}
                    >{g === 'male' ? '男' : '女'}</div>
                  ))}
                </div>
                {profileErrors.gender && <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>{profileErrors.gender}</div>}
              </div>
              <div className="flex gap-3">
                <div className="flex-1">
                  <div className="text-xs text-gray-500 mb-1">身高 (cm)</div>
                  <Input type="number" placeholder="如：170" value={profileEdits.height} onChange={(v) => setProfileEdits((p) => ({ ...p, height: v }))} style={{ '--font-size': '14px', background: '#fff', borderRadius: 8, padding: '6px 12px', border: '1px solid #d9d9d9' }} />
                </div>
                <div className="flex-1">
                  <div className="text-xs text-gray-500 mb-1">体重 (kg)</div>
                  <Input type="number" placeholder="如：65" value={profileEdits.weight} onChange={(v) => setProfileEdits((p) => ({ ...p, weight: v }))} style={{ '--font-size': '14px', background: '#fff', borderRadius: 8, padding: '6px 12px', border: '1px solid #d9d9d9' }} />
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">既往病史（慢性病史）</div>
                <DiseaseTagSelector items={profileEdits.chronic_diseases} presets={chronicPresets} onChange={(items) => setProfileEdits((p) => ({ ...p, chronic_diseases: items }))} activeColor="linear-gradient(135deg, #fa8c16, #faad14)" categoryLabel="慢性病史" />
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">过敏史</div>
                <DiseaseTagSelector items={profileEdits.allergies} presets={allergyPresets} onChange={(items) => setProfileEdits((p) => ({ ...p, allergies: items }))} activeColor="linear-gradient(135deg, #f5222d, #fa541c)" categoryLabel="过敏史" />
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">家族遗传病史</div>
                <DiseaseTagSelector items={profileEdits.genetic_diseases} presets={geneticPresets} onChange={(items) => setProfileEdits((p) => ({ ...p, genetic_diseases: items }))} activeColor="linear-gradient(135deg, #722ed1, #1890ff)" categoryLabel="遗传病史" />
              </div>
            </div>
          </div>

          <Button
            block loading={confirmLoading} onClick={handleMemberConfirm}
            style={{ marginTop: 20, background: 'linear-gradient(135deg, #52c41a, #13c2c2)', color: '#fff', border: 'none', borderRadius: 24, height: 46, fontSize: 15 }}
          >
            确认并开始识别
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
                <div className="flex gap-3">
                  <div className="flex-1">
                    <div className="text-xs text-gray-500 mb-1">身高 (cm)</div>
                    <input type="number" className="w-full bg-white text-sm rounded-xl px-3 py-2 outline-none border border-gray-200" placeholder="如：170" value={newHeight} onChange={(e) => setNewHeight(e.target.value)} />
                  </div>
                  <div className="flex-1">
                    <div className="text-xs text-gray-500 mb-1">体重 (kg)</div>
                    <input type="number" className="w-full bg-white text-sm rounded-xl px-3 py-2 outline-none border border-gray-200" placeholder="如：65" value={newWeight} onChange={(e) => setNewWeight(e.target.value)} />
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">既往病史</div>
                  <DiseaseTagSelector items={newMedicalHistories} presets={chronicPresets} onChange={(items) => setNewMedicalHistories(items)} activeColor="linear-gradient(135deg, #fa8c16, #faad14)" categoryLabel="慢性病史" />
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">过敏史</div>
                  <DiseaseTagSelector items={newAllergies} presets={allergyPresets} onChange={(items) => setNewAllergies(items)} activeColor="linear-gradient(135deg, #f5222d, #fa541c)" categoryLabel="过敏史" />
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
        visible={birthdayPickerVisible}
        onClose={() => setBirthdayPickerVisible(false)}
        precision="day" max={new Date()} min={new Date('1900-01-01')}
        onConfirm={(val) => {
          const d = val as Date;
          const str = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
          setProfileEdits((p) => ({ ...p, birthday: str }));
          setProfileErrors((e) => ({ ...e, birthday: undefined }));
          setBirthdayPickerVisible(false);
        }}
        title="选择出生日期"
      />
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
