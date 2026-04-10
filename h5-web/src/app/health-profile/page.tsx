'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  NavBar,
  Toast,
  Popup,
  Dialog,
  DatePicker,
  Input,
  TextArea,
  Tag,
} from 'antd-mobile';
import api from '@/lib/api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface FamilyMember {
  id: number;
  user_id: number;
  is_self: boolean;
  nickname: string;
  relationship_type: string;
  relation_type_id: number | null;
  relation_type_name: string;
  birthday?: string;
  gender?: string;
  height?: number;
  weight?: number;
  status: number;
}

interface RelationType {
  id: number;
  name: string;
  sort_order: number;
}

interface HealthProfile {
  id: number;
  name: string;
  gender: string;
  birthday: string;
  height: number | null;
  weight: number | null;
  blood_type: string;
  chronic_diseases: string[];
  drug_allergies: string;
  food_allergies: string;
  other_allergies: string;
  genetic_diseases: string[];
  completeness: number;
}

interface DiseasePreset {
  id: number;
  name: string;
  category: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

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

const BLOOD_TYPES = ['A', 'B', 'O', 'AB'];

const ADD_MEDICAL_OPTIONS = ['高血压', '糖尿病', '心脏病', '哮喘', '甲状腺疾病', '肝病', '肾病', '痛风'];
const ADD_ALLERGY_OPTIONS = ['青霉素', '花粉', '海鲜', '牛奶', '尘螨', '坚果', '磺胺类', '头孢类'];

function calcAge(birthday: string): string {
  if (!birthday) return '';
  const birth = new Date(birthday);
  const now = new Date();
  const age = now.getFullYear() - birth.getFullYear();
  return `${age}岁`;
}

function formatDate(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

// ─── Debounce hook ────────────────────────────────────────────────────────────

function useDebounce<T extends (...args: any[]) => any>(fn: T, delay: number): T {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  return useCallback((...args: Parameters<T>) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => fn(...args), delay);
  }, [fn, delay]) as T;
}

// ─── Progress bar ─────────────────────────────────────────────────────────────

function ProgressBar({ value }: { value: number }) {
  const color = value < 30 ? '#f5222d' : value < 70 ? '#fa8c16' : '#52c41a';
  return (
    <div className="mt-3">
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs text-gray-500">档案完整度</span>
        <span className="text-xs font-semibold" style={{ color }}>{value}%</span>
      </div>
      <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${value}%`, background: color }}
        />
      </div>
    </div>
  );
}

// ─── Collapsible section ──────────────────────────────────────────────────────

function Section({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-2xl overflow-hidden mb-3 bg-white shadow-sm">
      <button
        className="w-full flex items-center justify-between px-4 py-3"
        onClick={() => setOpen(!open)}
      >
        <span className="font-semibold text-sm text-gray-800">{title}</span>
        <span className="text-gray-400 text-lg leading-none transition-transform duration-200" style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}>
          ›
        </span>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function HealthProfilePage() {
  const router = useRouter();

  // Guide banner
  const [showGuideBanner, setShowGuideBanner] = useState(false);

  // Members
  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(true);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);

  // Health profile
  const [profile, setProfile] = useState<HealthProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');

  // Presets
  const [chronicPresets, setChronicPresets] = useState<DiseasePreset[]>([]);
  const [geneticPresets, setGeneticPresets] = useState<DiseasePreset[]>([]);

  // Add member popup
  const [addPopupVisible, setAddPopupVisible] = useState(false);
  const [relationTypes, setRelationTypes] = useState<RelationType[]>([]);
  const [addStep, setAddStep] = useState<'relation' | 'info'>('relation');
  const [selectedRelation, setSelectedRelation] = useState<RelationType | null>(null);
  const [newNickname, setNewNickname] = useState('');
  const [newGender, setNewGender] = useState('');
  const [newBirthday, setNewBirthday] = useState('');
  const [newBirthdayPickerVisible, setNewBirthdayPickerVisible] = useState(false);
  const [newHeight, setNewHeight] = useState('');
  const [newWeight, setNewWeight] = useState('');
  const [newMedicalHistories, setNewMedicalHistories] = useState<string[]>([]);
  const [newMedicalOther, setNewMedicalOther] = useState('');
  const [newAllergies, setNewAllergies] = useState<string[]>([]);
  const [newAllergyOther, setNewAllergyOther] = useState('');
  const [addLoading, setAddLoading] = useState(false);

  // Delete member
  const [deletingMemberId, setDeletingMemberId] = useState<number | null>(null);
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // DatePicker for profile
  const [birthdayPickerVisible, setBirthdayPickerVisible] = useState(false);

  // ── Fetch members ────────────────────────────────────────────────────────────

  const fetchMembers = async () => {
    setMembersLoading(true);
    try {
      const res: any = await api.get('/api/family/members');
      const data = res.data || res;
      const items: FamilyMember[] = Array.isArray(data.items) ? data.items : [];
      setMembers(items);
      if (selectedMemberId === null && items.length > 0) {
        const self = items.find((m) => m.is_self) || items[0];
        setSelectedMemberId(self.id);
      }
    } catch {
      setMembers([]);
    }
    setMembersLoading(false);
  };

  // ── Fetch health profile ─────────────────────────────────────────────────────

  const fetchProfile = async (memberId: number) => {
    setProfileLoading(true);
    try {
      const res: any = await api.get(`/api/health/profile/member/${memberId}`);
      const data = res.data || res;
      setProfile(data);
    } catch {
      setProfile(null);
    }
    setProfileLoading(false);
  };

  // ── Fetch presets ────────────────────────────────────────────────────────────

  const fetchPresets = async () => {
    try {
      const [cRes, gRes]: any[] = await Promise.all([
        api.get('/api/disease-presets', { params: { category: 'chronic' } }),
        api.get('/api/disease-presets', { params: { category: 'genetic' } }),
      ]);
      const c = cRes.data || cRes;
      const g = gRes.data || gRes;
      setChronicPresets(Array.isArray(c.items) ? c.items : []);
      setGeneticPresets(Array.isArray(g.items) ? g.items : []);
    } catch {
      // ignore
    }
  };

  // ── Fetch relation types ─────────────────────────────────────────────────────

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

  useEffect(() => {
    fetchMembers();
    fetchPresets();
    const fetchGuideStatus = async () => {
      try {
        const res: any = await api.get('/api/health/guide-status');
        if (res.guide_count === 1 && res.profile_completeness < 1.0) {
          setShowGuideBanner(true);
        }
      } catch {
        // ignore
      }
    };
    fetchGuideStatus();
  }, []);

  useEffect(() => {
    if (selectedMemberId !== null) {
      fetchProfile(selectedMemberId);
    }
  }, [selectedMemberId]);

  // ── Auto-save (debounced) ────────────────────────────────────────────────────

  const saveProfile = useCallback(async (memberId: number, patch: Partial<HealthProfile>) => {
    setSaveStatus('saving');
    try {
      await api.put(`/api/health/profile/member/${memberId}`, patch);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 1200);
    } catch {
      setSaveStatus('idle');
    }
  }, []);

  const debouncedSave = useDebounce(saveProfile, 1500);

  const updateProfile = (patch: Partial<HealthProfile>) => {
    if (!profile || selectedMemberId === null) return;
    const updated = { ...profile, ...patch };
    setProfile(updated);
    debouncedSave(selectedMemberId, patch);
  };

  // ── Add member ───────────────────────────────────────────────────────────────

  const openAddPopup = async () => {
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
    setAddPopupVisible(true);
  };

  const handleAddConfirm = async () => {
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

      const createdRes: any = await api.post('/api/family/members', body);
      const created = createdRes.data || createdRes;
      setAddPopupVisible(false);
      await fetchMembers();
      if (created.id) setSelectedMemberId(created.id);
    } catch {
      Toast.show({ content: '添加失败，请重试', icon: 'fail' });
    }
    setAddLoading(false);
  };

  // ── Delete member ────────────────────────────────────────────────────────────

  const handleLongPressStart = (member: FamilyMember) => {
    if (member.is_self) return;
    longPressTimer.current = setTimeout(() => {
      setDeletingMemberId(member.id);
    }, 600);
  };

  const handleLongPressEnd = () => {
    if (longPressTimer.current) clearTimeout(longPressTimer.current);
  };

  const confirmDelete = async () => {
    if (deletingMemberId === null) return;
    try {
      await api.delete(`/api/family/members/${deletingMemberId}`);
      const selfMember = members.find((m) => m.is_self);
      setDeletingMemberId(null);
      await fetchMembers();
      if (selfMember) setSelectedMemberId(selfMember.id);
    } catch {
      Toast.show({ content: '删除失败', icon: 'fail' });
      setDeletingMemberId(null);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────────

  const selectedMember = members.find((m) => m.id === selectedMemberId);

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(160deg, #f0faf0 0%, #e8f4ff 100%)' }}>
      <NavBar
        onBack={() => router.back()}
        style={{ background: 'transparent' }}
        right={
          <div className="text-xs font-medium" style={{ color: saveStatus === 'saving' ? '#fa8c16' : saveStatus === 'saved' ? '#52c41a' : 'transparent' }}>
            {saveStatus === 'saving' ? '保存中…' : saveStatus === 'saved' ? '已保存 ✓' : '.'}
          </div>
        }
      >
        健康档案
      </NavBar>

      {/* ── Guide banner ───────────────────────────────────────────────────── */}
      {showGuideBanner && (
        <div className="px-4 pb-2">
          <div
            className="flex items-center justify-between cursor-pointer"
            style={{
              background: 'linear-gradient(135deg, #f6ffed, #e6fffb)',
              border: '1px solid #b7eb8f',
              borderRadius: 12,
              padding: '12px 16px',
            }}
            onClick={() => router.replace('/health-guide')}
          >
            <span className="text-sm text-gray-700 flex-1">您的健康档案还未完善，点击立即补充</span>
            <button
              className="ml-2 text-gray-400 text-lg leading-none flex-shrink-0"
              onClick={(e) => {
                e.stopPropagation();
                setShowGuideBanner(false);
              }}
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* ── Member switcher (Tab circle icons) ─────────────────────────── */}
      <div className="px-4 pb-2">
        <div
          className="flex items-center gap-3 overflow-x-auto pb-1"
          style={{ scrollbarWidth: 'none' }}
        >
          {membersLoading ? (
            <div className="text-sm text-gray-400 py-2">加载中...</div>
          ) : (
            members.map((m) => {
              const relationName = m.relation_type_name || m.relationship_type || '本人';
              const isSelected = m.id === selectedMemberId;
              const color = getRelationColor(relationName);
              return (
                <div
                  key={m.id}
                  className="flex flex-col items-center flex-shrink-0 cursor-pointer"
                  style={{ minWidth: 56 }}
                  onClick={() => setSelectedMemberId(m.id)}
                  onTouchStart={() => handleLongPressStart(m)}
                  onTouchEnd={handleLongPressEnd}
                  onMouseDown={() => handleLongPressStart(m)}
                  onMouseUp={handleLongPressEnd}
                  onMouseLeave={handleLongPressEnd}
                >
                  <div
                    className="flex items-center justify-center rounded-full transition-all"
                    style={{
                      width: 44,
                      height: 44,
                      background: isSelected ? color : '#f0f0f0',
                      boxShadow: isSelected ? `0 4px 12px ${color}55` : '0 1px 4px rgba(0,0,0,0.08)',
                      border: isSelected ? 'none' : '1.5px solid #e8e8e8',
                    }}
                  >
                    <span style={{
                      color: isSelected ? '#fff' : '#555',
                      fontSize: relationName.length > 2 ? 11 : 13,
                      fontWeight: 600,
                      lineHeight: 1.1,
                    }}>
                      {relationName.length > 2 ? relationName.slice(0, 2) : relationName}
                    </span>
                  </div>
                  {isSelected && (
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: color, marginTop: 4 }} />
                  )}
                  <span
                    className="text-xs font-medium"
                    style={{
                      color: isSelected ? color : '#888',
                      marginTop: isSelected ? 2 : 8,
                    }}
                  >
                    {relationName}
                  </span>
                </div>
              );
            })
          )}

          {/* Add button */}
          <div
            className="flex flex-col items-center flex-shrink-0 cursor-pointer"
            style={{ minWidth: 56 }}
            onClick={openAddPopup}
          >
            <div
              className="flex items-center justify-center rounded-full"
              style={{
                width: 44,
                height: 44,
                background: 'rgba(255,255,255,0.85)',
                border: '1.5px dashed #b7eb8f',
                color: '#52c41a',
                fontSize: 22,
              }}
            >
              +
            </div>
            <span className="text-xs mt-1 text-gray-400" style={{ marginTop: 8 }}>添加</span>
          </div>
        </div>
      </div>

      {/* ── Profile header card ────────────────────────────────────────────── */}
      {selectedMember && (
        <div className="px-4 mb-3">
          <div
            className="rounded-2xl p-4"
            style={{ background: 'linear-gradient(135deg, #52c41a22, #13c2c222)', border: '1px solid #b7eb8f40' }}
          >
            <div className="flex items-center gap-3">
              <div
                className="text-3xl flex items-center justify-center rounded-full"
                style={{ width: 56, height: 56, background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
              >
                {getMemberEmoji(selectedMember.relation_type_name || selectedMember.relationship_type)}
              </div>
              <div className="flex-1">
                <div className="font-bold text-base text-gray-800">
                  {profile?.name || selectedMember.nickname}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {selectedMember.relation_type_name || selectedMember.relationship_type}
                  {profile?.birthday ? ` · ${calcAge(profile.birthday)}` : ''}
                </div>
                {profile && <ProgressBar value={Math.round(profile.completeness * 100)} />}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Profile content ────────────────────────────────────────────────── */}
      <div className="px-4 pb-24">
        {profileLoading ? (
          <div className="text-center py-12 text-gray-400 text-sm">加载档案中...</div>
        ) : profile ? (
          <>
            {/* 基本信息 */}
            <Section title="📋 基本信息" defaultOpen={true}>
              <div className="space-y-3">
                <FieldRow label={<>姓名<span style={{color:'#ff4d4f'}}> *</span></>}>
                  <input
                    className="text-sm text-gray-700 text-right bg-transparent outline-none w-full"
                    placeholder="请输入姓名"
                    value={profile.name || ''}
                    onChange={(e) => updateProfile({ name: e.target.value })}
                  />
                </FieldRow>

                <FieldRow label={<>性别<span style={{color:'#ff4d4f'}}> *</span></>}>
                  <div className="flex gap-2">
                    {['male', 'female'].map((g) => (
                      <button
                        key={g}
                        className="px-4 py-1 rounded-full text-xs font-medium transition-all"
                        style={{
                          background: profile.gender === g ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#f5f5f5',
                          color: profile.gender === g ? '#fff' : '#888',
                        }}
                        onClick={() => updateProfile({ gender: g })}
                      >
                        {g === 'male' ? '男' : '女'}
                      </button>
                    ))}
                  </div>
                </FieldRow>

                <FieldRow label={<>出生日期<span style={{color:'#ff4d4f'}}> *</span></>}>
                  <button
                    className="text-sm text-gray-700 text-right"
                    onClick={() => setBirthdayPickerVisible(true)}
                  >
                    {profile.birthday ? (
                      <span>{profile.birthday} <span className="text-xs text-gray-400">({calcAge(profile.birthday)})</span></span>
                    ) : (
                      <span className="text-gray-300">请选择</span>
                    )}
                  </button>
                </FieldRow>

                <FieldRow label="身高 (cm)">
                  <input
                    type="number"
                    className="text-sm text-gray-700 text-right bg-transparent outline-none w-28"
                    placeholder="请输入"
                    value={profile.height ?? ''}
                    onChange={(e) => updateProfile({ height: e.target.value ? Number(e.target.value) : null })}
                  />
                </FieldRow>

                <FieldRow label="体重 (kg)">
                  <input
                    type="number"
                    className="text-sm text-gray-700 text-right bg-transparent outline-none w-28"
                    placeholder="请输入"
                    value={profile.weight ?? ''}
                    onChange={(e) => updateProfile({ weight: e.target.value ? Number(e.target.value) : null })}
                  />
                </FieldRow>

                <FieldRow label="血型">
                  <div className="flex gap-2">
                    {BLOOD_TYPES.map((bt) => (
                      <button
                        key={bt}
                        className="px-3 py-1 rounded-full text-xs font-medium transition-all"
                        style={{
                          background: profile.blood_type === bt ? 'linear-gradient(135deg, #f5222d, #fa8c16)' : '#f5f5f5',
                          color: profile.blood_type === bt ? '#fff' : '#888',
                        }}
                        onClick={() => updateProfile({ blood_type: bt })}
                      >
                        {bt}
                      </button>
                    ))}
                  </div>
                </FieldRow>
              </div>
            </Section>

            {/* 慢性病史 */}
            <Section title="🏥 慢性病史 / 既往病史">
              <div className="flex flex-wrap gap-2">
                {chronicPresets.map((p) => {
                  const selected = profile.chronic_diseases?.includes(p.name);
                  return (
                    <button
                      key={p.id}
                      className="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
                      style={{
                        background: selected ? 'linear-gradient(135deg, #fa8c16, #faad14)' : '#f5f5f5',
                        color: selected ? '#fff' : '#666',
                      }}
                      onClick={() => {
                        const list = profile.chronic_diseases || [];
                        updateProfile({
                          chronic_diseases: selected
                            ? list.filter((x) => x !== p.name)
                            : [...list, p.name],
                        });
                      }}
                    >
                      {p.name}
                    </button>
                  );
                })}
              </div>
              {chronicPresets.length === 0 && (
                <p className="text-xs text-gray-400 text-center py-3">暂无预设选项</p>
              )}
            </Section>

            {/* 过敏史 */}
            <Section title="⚠️ 过敏史">
              <div className="space-y-3">
                <div>
                  <div className="text-xs text-gray-500 mb-1">药物过敏</div>
                  <textarea
                    className="w-full text-sm text-gray-700 bg-gray-50 rounded-xl px-3 py-2 outline-none resize-none"
                    rows={2}
                    placeholder="请描述药物过敏情况（如无请留空）"
                    value={profile.drug_allergies || ''}
                    onChange={(e) => updateProfile({ drug_allergies: e.target.value })}
                  />
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">食物过敏</div>
                  <textarea
                    className="w-full text-sm text-gray-700 bg-gray-50 rounded-xl px-3 py-2 outline-none resize-none"
                    rows={2}
                    placeholder="请描述食物过敏情况（如无请留空）"
                    value={profile.food_allergies || ''}
                    onChange={(e) => updateProfile({ food_allergies: e.target.value })}
                  />
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">其他过敏</div>
                  <textarea
                    className="w-full text-sm text-gray-700 bg-gray-50 rounded-xl px-3 py-2 outline-none resize-none"
                    rows={2}
                    placeholder="请描述其他过敏情况（如无请留空）"
                    value={profile.other_allergies || ''}
                    onChange={(e) => updateProfile({ other_allergies: e.target.value })}
                  />
                </div>
              </div>
            </Section>

            {/* 家族遗传病史 */}
            <Section title="🧬 家族遗传病史">
              <div className="flex flex-wrap gap-2">
                {geneticPresets.map((p) => {
                  const selected = profile.genetic_diseases?.includes(p.name);
                  return (
                    <button
                      key={p.id}
                      className="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
                      style={{
                        background: selected ? 'linear-gradient(135deg, #722ed1, #1890ff)' : '#f5f5f5',
                        color: selected ? '#fff' : '#666',
                      }}
                      onClick={() => {
                        const list = profile.genetic_diseases || [];
                        updateProfile({
                          genetic_diseases: selected
                            ? list.filter((x) => x !== p.name)
                            : [...list, p.name],
                        });
                      }}
                    >
                      {p.name}
                    </button>
                  );
                })}
              </div>
              {geneticPresets.length === 0 && (
                <p className="text-xs text-gray-400 text-center py-3">暂无预设选项</p>
              )}
            </Section>
          </>
        ) : selectedMemberId !== null ? (
          <div className="text-center py-12 text-gray-400 text-sm">暂无档案数据</div>
        ) : null}
      </div>

      {/* ── Birthday DatePicker ────────────────────────────────────────────── */}
      <DatePicker
        visible={birthdayPickerVisible}
        onClose={() => setBirthdayPickerVisible(false)}
        precision="day"
        max={new Date()}
        min={new Date('1900-01-01')}
        title="选择出生日期"
        onConfirm={(val) => {
          updateProfile({ birthday: formatDate(val as Date) });
          setBirthdayPickerVisible(false);
        }}
      />

      {/* ── Add member Popup ───────────────────────────────────────────────── */}
      <Popup
        visible={addPopupVisible}
        onMaskClick={() => setAddPopupVisible(false)}
        position="bottom"
        bodyStyle={{ borderRadius: '20px 20px 0 0', maxHeight: '85vh', overflowY: 'auto' }}
      >
        <div className="px-4 pb-8">
          {/* Header */}
          <div className="flex items-center justify-between py-4 border-b border-gray-100">
            <span className="text-base font-bold text-gray-800">添加家庭成员</span>
            <button className="text-gray-400 text-2xl leading-none" onClick={() => setAddPopupVisible(false)}>×</button>
          </div>

          {/* Step 1: Choose relation */}
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

          {/* Step 2: Fill info */}
          {addStep === 'info' && selectedRelation && (
            <div className="mt-5 p-4 rounded-2xl" style={{ background: '#f6ffed', border: '1px solid #b7eb8f' }}>
              <div className="text-sm font-semibold mb-4" style={{ color: '#52c41a' }}>
                {getMemberEmoji(selectedRelation.name)} 填写{selectedRelation.name}信息
              </div>

              <div className="space-y-3">
                <div>
                  <div className="text-xs text-gray-500 mb-1">姓名 <span className="text-red-400">*</span></div>
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
                onClick={handleAddConfirm}
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
          setNewBirthday(formatDate(val as Date));
          setNewBirthdayPickerVisible(false);
        }}
      />

      {/* ── Delete confirm dialog ──────────────────────────────────────────── */}
      <Dialog
        visible={deletingMemberId !== null}
        title="删除成员"
        content="删除后该成员的健康档案数据也会一并删除，确认删除吗？"
        closeOnAction
        onClose={() => setDeletingMemberId(null)}
        actions={[
          [
            { key: 'cancel', text: '取消', onClick: () => setDeletingMemberId(null) },
            {
              key: 'confirm',
              text: '确认删除',
              bold: true,
              style: { color: '#f5222d' },
              onClick: confirmDelete,
            },
          ],
        ]}
      />
    </div>
  );
}

// ─── Helper: FieldRow ─────────────────────────────────────────────────────────

function FieldRow({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-50 last:border-b-0">
      <span className="text-sm text-gray-500 flex-shrink-0 w-24">{label}</span>
      <div className="flex-1 flex justify-end">{children}</div>
    </div>
  );
}
