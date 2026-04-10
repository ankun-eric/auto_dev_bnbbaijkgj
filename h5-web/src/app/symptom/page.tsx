'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  NavBar,
  Button,
  TextArea,
  Tag,
  Grid,
  Card,
  Steps,
  Toast,
  Popup,
  Radio,
  Input,
  DatePicker,
} from 'antd-mobile';
import api from '@/lib/api';

const bodyParts = [
  { key: 'head', label: '头部', icon: '🧠' },
  { key: 'eye', label: '眼睛', icon: '👁️' },
  { key: 'ear', label: '耳鼻喉', icon: '👂' },
  { key: 'chest', label: '胸部', icon: '🫁' },
  { key: 'stomach', label: '腹部', icon: '🫃' },
  { key: 'back', label: '腰背', icon: '🦴' },
  { key: 'limbs', label: '四肢', icon: '💪' },
  { key: 'skin', label: '皮肤', icon: '🖐️' },
  { key: 'mental', label: '精神', icon: '😵' },
];

const commonSymptoms: Record<string, string[]> = {
  head: ['头痛', '头晕', '偏头痛', '头胀', '头重脚轻'],
  eye: ['眼睛干涩', '视力模糊', '眼睛红肿', '眼睛疲劳'],
  ear: ['耳鸣', '咽喉痛', '鼻塞', '流鼻涕', '打喷嚏'],
  chest: ['胸闷', '心悸', '气短', '咳嗽', '胸痛'],
  stomach: ['腹痛', '腹泻', '便秘', '恶心', '食欲不振', '胃胀'],
  back: ['腰痛', '背痛', '颈椎痛', '腰酸'],
  limbs: ['关节痛', '手脚麻木', '肌肉酸痛', '腿抽筋'],
  skin: ['皮疹', '瘙痒', '脱皮', '红斑'],
  mental: ['失眠', '焦虑', '疲劳', '注意力不集中'],
};

const medicalHistoryOptions = [
  '高血压', '糖尿病', '心脏病', '哮喘', '甲状腺疾病', '肝病', '肾病', '痛风',
];

const allergyOptions = [
  '青霉素', '花粉', '海鲜', '牛奶', '尘螨', '坚果', '磺胺类', '头孢类',
];

interface FamilyMember {
  id: number;
  nickname: string;
  relationship_type: string;
  is_self?: boolean;
  relation_type_name?: string;
  birthday?: string;
  gender?: string;
  height?: number;
  weight?: number;
  medical_histories?: string[];
  allergies?: string[];
}

interface RelationType {
  id: number;
  name: string;
  sort_order: number;
}

interface HealthProfile {
  birthday: string;
  gender: string;
  height: string;
  weight: string;
  medical_histories: string[];
  medical_other: string;
  allergies: string[];
  allergy_other: string;
}

const emptyProfile = (): HealthProfile => ({
  birthday: '',
  gender: '',
  height: '',
  weight: '',
  medical_histories: [],
  medical_other: '',
  allergies: [],
  allergy_other: '',
});

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

export default function SymptomPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [selectedPart, setSelectedPart] = useState('');
  const [selectedSymptoms, setSelectedSymptoms] = useState<string[]>([]);
  const [description, setDescription] = useState('');
  const [duration, setDuration] = useState('');
  const [analyzing, setAnalyzing] = useState(false);

  // Family member popup state
  const [memberPopupVisible, setMemberPopupVisible] = useState(false);
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);
  const [profileEdits, setProfileEdits] = useState<HealthProfile>(emptyProfile());
  const [birthdayPickerVisible, setBirthdayPickerVisible] = useState(false);

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

  const toggleSymptom = (s: string) => {
    setSelectedSymptoms((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );
  };

  const nextStep = () => {
    if (step === 0 && !selectedPart) {
      Toast.show({ content: '请选择不适部位' });
      return;
    }
    if (step === 1 && selectedSymptoms.length === 0) {
      Toast.show({ content: '请选择至少一个症状' });
      return;
    }
    if (step < 2) setStep(step + 1);
    else openMemberPopup();
  };

  const openMemberPopup = async () => {
    try {
      const res: any = await api.get('/api/family/members');
      const data = res.data || res;
      let items: FamilyMember[] = Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : [];
      if (!items.some((m) => m.is_self)) {
        items = [{ id: -1, nickname: '本人', relationship_type: 'self', is_self: true, relation_type_name: '本人' }, ...items];
      }
      setFamilyMembers(items);
      setSelectedMemberId(items[0]?.id ?? null);
    } catch {
      setFamilyMembers([{ id: -1, nickname: '本人', relationship_type: 'self', is_self: true, relation_type_name: '本人' }]);
      setSelectedMemberId(-1);
    }
    setProfileEdits(emptyProfile());
    setMemberPopupVisible(true);
  };

  const handleSelectMember = (id: number) => {
    setSelectedMemberId(id);
    const m = familyMembers.find((x) => x.id === id);
    if (m) {
      const allMedical = m.medical_histories || [];
      const knownMedical = allMedical.filter((h) => medicalHistoryOptions.includes(h));
      const otherMedical = allMedical.filter((h) => !medicalHistoryOptions.includes(h)).join('、');
      const allAllergy = m.allergies || [];
      const knownAllergy = allAllergy.filter((a) => allergyOptions.includes(a));
      const otherAllergy = allAllergy.filter((a) => !allergyOptions.includes(a)).join('、');
      setProfileEdits({
        birthday: m.birthday || '',
        gender: m.gender || '',
        height: m.height != null ? String(m.height) : '',
        weight: m.weight != null ? String(m.weight) : '',
        medical_histories: knownMedical,
        medical_other: otherMedical,
        allergies: knownAllergy,
        allergy_other: otherAllergy,
      });
    } else {
      setProfileEdits(emptyProfile());
    }
  };

  const toggleProfileTag = (field: 'medical_histories' | 'allergies', val: string) => {
    setProfileEdits((prev) => ({
      ...prev,
      [field]: prev[field].includes(val)
        ? prev[field].filter((x) => x !== val)
        : [...prev[field], val],
    }));
  };

  const buildMedicalHistories = (selected: string[], other: string): string[] => {
    const list = [...selected];
    if (other.trim()) list.push(other.trim());
    return list;
  };

  // Add member popup
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
    try {
      const res: any = await api.get('/api/relation-types');
      const data = res.data || res;
      const items = Array.isArray(data.items) ? data.items : [];
      setRelationTypes(items.filter((rt: any) => rt.name !== '本人'));
    } catch {
      setRelationTypes([]);
    }
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

      const res: any = await api.post('/api/family/members', body);
      const created = res.data || res;
      setAddMemberPopupVisible(false);

      // Refresh member list and auto-select the new member
      try {
        const membersRes: any = await api.get('/api/family/members');
        const mData = membersRes.data || membersRes;
        let items: FamilyMember[] = Array.isArray(mData.items) ? mData.items : Array.isArray(mData) ? mData : [];
        if (!items.some((m) => m.is_self)) {
          items = [{ id: -1, nickname: '本人', relationship_type: 'self', is_self: true, relation_type_name: '本人' }, ...items];
        }
        setFamilyMembers(items);
        if (created.id) {
          setSelectedMemberId(created.id);
          handleSelectMember(created.id);
        }
      } catch {
        // keep existing list
      }
    } catch {
      Toast.show({ content: '添加失败，请重试', icon: 'fail' });
    }
    setAddLoading(false);
  };

  const handleConfirm = async () => {
    setAnalyzing(true);
    try {
      let familyMemberId: number | null = null;
      let memberLabel = '自己';

      if (selectedMemberId !== null) {
        const m = familyMembers.find((x) => x.id === selectedMemberId);
        if (m?.is_self) {
          familyMemberId = m.id === -1 ? null : m.id;
          memberLabel = '本人';
        } else if (m) {
          familyMemberId = m.id;
          const relationLabel = m.relation_type_name || m.relationship_type;
          memberLabel = `${relationLabel}·${m.nickname}`;
        }

        // Update profile if it's a real member
        if (familyMemberId !== null) {
          const medical = buildMedicalHistories(profileEdits.medical_histories, profileEdits.medical_other);
          const allergies = buildMedicalHistories(profileEdits.allergies, profileEdits.allergy_other);
          const updatePayload: any = {};
          if (profileEdits.birthday) updatePayload.birthday = profileEdits.birthday;
          if (profileEdits.gender) updatePayload.gender = profileEdits.gender;
          if (profileEdits.height) updatePayload.height = Number(profileEdits.height);
          if (profileEdits.weight) updatePayload.weight = Number(profileEdits.weight);
          if (medical.length) updatePayload.medical_histories = medical;
          if (allergies.length) updatePayload.allergies = allergies;
          if (Object.keys(updatePayload).length > 0) {
            await api.put(`/api/family/members/${familyMemberId}`, updatePayload).catch(() => null);
          }
        }
      }

      const partLabel = bodyParts.find((p) => p.key === selectedPart)?.label || selectedPart;
      const title = `${partLabel}·${selectedSymptoms.slice(0, 3).join('/')}${duration ? `·${duration}` : ''}`;
      const msg = `我的${partLabel}不舒服，主要症状有：${selectedSymptoms.join('、')}。${description ? `补充描述：${description}。` : ''}${duration ? `持续时间：${duration}。` : ''}请帮我分析可能的原因。`;

      const sessionRes: any = await api.post('/api/chat/sessions', {
        session_type: 'symptom_check',
        family_member_id: familyMemberId,
        title,
        symptom_info: {
          body_part: selectedPart,
          body_part_label: partLabel,
          symptoms: selectedSymptoms,
          description,
          duration,
        },
      });
      const session = sessionRes.data || sessionRes;
      const sessionId = session.id;

      setMemberPopupVisible(false);
      router.push(
        `/chat/${sessionId}?type=symptom&msg=${encodeURIComponent(msg)}&member=${encodeURIComponent(memberLabel)}`
      );
    } catch (err: any) {
      Toast.show({ content: err?.response?.data?.detail || '操作失败，请重试', icon: 'fail' });
    }
    setAnalyzing(false);
  };

  const durations = ['今天刚开始', '1-3天', '一周内', '一个月内', '超过一个月'];

  const selectedMember = familyMembers.find((m) => m.id === selectedMemberId);

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => (step > 0 ? setStep(step - 1) : router.back())} style={{ background: '#fff' }}>
        健康自查
      </NavBar>

      <div className="px-4 pt-4">
        <Steps current={step} style={{ '--title-font-size': '12px', '--icon-size': '22px' }}>
          <Steps.Step title="选择部位" />
          <Steps.Step title="描述症状" />
          <Steps.Step title="补充信息" />
        </Steps>

        {step === 0 && (
          <div className="mt-4">
            <div className="section-title">请选择不适的身体部位</div>
            <Grid columns={3} gap={12}>
              {bodyParts.map((part) => (
                <Grid.Item key={part.key}>
                  <div
                    className={`card text-center cursor-pointer transition-all ${
                      selectedPart === part.key ? 'ring-2 ring-primary' : ''
                    }`}
                    onClick={() => setSelectedPart(part.key)}
                    style={selectedPart === part.key ? { background: '#f6ffed' } : {}}
                  >
                    <div className="text-2xl mb-1">{part.icon}</div>
                    <div className="text-xs">{part.label}</div>
                  </div>
                </Grid.Item>
              ))}
            </Grid>
          </div>
        )}

        {step === 1 && (
          <div className="mt-4">
            <div className="section-title">
              请选择您的症状（{bodyParts.find((p) => p.key === selectedPart)?.label}）
            </div>
            <div className="flex flex-wrap gap-2 mb-4">
              {(commonSymptoms[selectedPart] || []).map((s) => (
                <Tag
                  key={s}
                  onClick={() => toggleSymptom(s)}
                  style={{
                    '--background-color': selectedSymptoms.includes(s) ? '#52c41a' : '#f5f5f5',
                    '--text-color': selectedSymptoms.includes(s) ? '#fff' : '#666',
                    '--border-color': 'transparent',
                    padding: '6px 14px',
                    borderRadius: 20,
                    fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  {s}
                </Tag>
              ))}
            </div>
            <div className="section-title">症状描述（可选）</div>
            <TextArea
              placeholder="请详细描述您的症状，如：什么时候开始的，是否加重..."
              value={description}
              onChange={setDescription}
              rows={3}
              style={{ '--font-size': '14px' }}
            />
          </div>
        )}

        {step === 2 && (
          <div className="mt-4">
            <div className="section-title">症状持续时间</div>
            <div className="flex flex-wrap gap-2 mb-4">
              {durations.map((d) => (
                <Tag
                  key={d}
                  onClick={() => setDuration(d)}
                  style={{
                    '--background-color': duration === d ? '#52c41a' : '#f5f5f5',
                    '--text-color': duration === d ? '#fff' : '#666',
                    '--border-color': 'transparent',
                    padding: '6px 14px',
                    borderRadius: 20,
                    fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  {d}
                </Tag>
              ))}
            </div>

            <Card style={{ borderRadius: 12, marginTop: 16 }}>
              <div className="text-sm font-medium mb-2">症状摘要</div>
              <div className="text-xs text-gray-500">
                <p>部位：{bodyParts.find((p) => p.key === selectedPart)?.label}</p>
                <p className="mt-1">症状：{selectedSymptoms.join('、')}</p>
                {description && <p className="mt-1">描述：{description}</p>}
                {duration && <p className="mt-1">持续：{duration}</p>}
              </div>
            </Card>
          </div>
        )}

        <Button
          block
          loading={analyzing}
          onClick={nextStep}
          style={{
            marginTop: 24,
            background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
            color: '#fff',
            border: 'none',
            borderRadius: 24,
            height: 44,
          }}
        >
          {step < 2 ? '下一步' : 'AI智能分析'}
        </Button>
      </div>

      {/* Family member selection popup */}
      <Popup
        visible={memberPopupVisible}
        onMaskClick={() => setMemberPopupVisible(false)}
        position="bottom"
        bodyStyle={{ borderRadius: '16px 16px 0 0', maxHeight: '90vh', overflowY: 'auto' }}
      >
        <div className="px-4 pb-6">
          <div className="flex items-center justify-between py-4 border-b border-gray-100">
            <span className="text-base font-semibold">为谁咨询</span>
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
                    <div>
                      <div className="text-sm font-medium">{displayName}</div>
                    </div>
                  </div>
                  <Radio
                    checked={selectedMemberId === m.id}
                    onChange={() => handleSelectMember(m.id)}
                    style={{ '--icon-size': '18px', '--font-size': '14px', '--gap': '6px' }}
                  />
                </div>
              );
            })}

            {/* Add member button */}
            <div
              className="flex items-center gap-2 px-3 py-3 rounded-xl cursor-pointer"
              style={{ background: '#f9f9f9', border: '1px solid transparent' }}
              onClick={openAddMemberPopup}
            >
              <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-lg"
                style={{ background: '#52c41a' }}>
                +
              </div>
              <span className="text-sm text-primary font-medium" style={{ color: '#52c41a' }}>添加家庭成员</span>
            </div>
          </div>

          {/* Health profile for selected member */}
          <div className="mt-4 p-4 rounded-xl" style={{ background: '#f9f9f9', border: '1px solid #e8e8e8' }}>
            <div className="text-sm font-semibold mb-3 text-gray-600">
              {selectedMember?.is_self ? '我的' : (selectedMember ? `${selectedMember.nickname}的` : '')}健康档案
              <span className="text-xs text-gray-400 ml-2 font-normal">（可修改，点击确认后保存）</span>
            </div>

            <div className="space-y-3">
              <div>
                <div className="text-xs text-gray-500 mb-1">出生日期</div>
                <div
                  className="bg-white rounded-lg px-3 py-2 text-sm cursor-pointer flex items-center justify-between"
                  style={{ border: '1px solid #d9d9d9' }}
                  onClick={() => setBirthdayPickerVisible(true)}
                >
                  <span style={{ color: profileEdits.birthday ? '#333' : '#bbb' }}>
                    {profileEdits.birthday || '请选择出生日期'}
                  </span>
                  <span className="text-gray-300">📅</span>
                </div>
              </div>

              <div>
                <div className="text-xs text-gray-500 mb-1">性别</div>
                <div className="flex gap-3">
                  {['male', 'female'].map((g) => (
                    <div
                      key={g}
                      className="flex-1 text-center py-2 rounded-lg text-sm cursor-pointer"
                      style={{
                        background: profileEdits.gender === g ? '#52c41a' : '#fff',
                        color: profileEdits.gender === g ? '#fff' : '#666',
                        border: `1px solid ${profileEdits.gender === g ? '#52c41a' : '#d9d9d9'}`,
                      }}
                      onClick={() => setProfileEdits((p) => ({ ...p, gender: g }))}
                    >
                      {g === 'male' ? '男' : '女'}
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex gap-3">
                <div className="flex-1">
                  <div className="text-xs text-gray-500 mb-1">身高 (cm)</div>
                  <Input
                    type="number"
                    placeholder="如：170"
                    value={profileEdits.height}
                    onChange={(v) => setProfileEdits((p) => ({ ...p, height: v }))}
                    style={{ '--font-size': '14px', background: '#fff', borderRadius: 8, padding: '6px 12px', border: '1px solid #d9d9d9' }}
                  />
                </div>
                <div className="flex-1">
                  <div className="text-xs text-gray-500 mb-1">体重 (kg)</div>
                  <Input
                    type="number"
                    placeholder="如：65"
                    value={profileEdits.weight}
                    onChange={(v) => setProfileEdits((p) => ({ ...p, weight: v }))}
                    style={{ '--font-size': '14px', background: '#fff', borderRadius: 8, padding: '6px 12px', border: '1px solid #d9d9d9' }}
                  />
                </div>
              </div>

              <div>
                <div className="text-xs text-gray-500 mb-1">既往病史</div>
                <div className="flex flex-wrap gap-2">
                  {medicalHistoryOptions.map((opt) => (
                    <Tag
                      key={opt}
                      onClick={() => toggleProfileTag('medical_histories', opt)}
                      style={{
                        '--background-color': profileEdits.medical_histories.includes(opt) ? '#52c41a' : '#fff',
                        '--text-color': profileEdits.medical_histories.includes(opt) ? '#fff' : '#666',
                        '--border-color': profileEdits.medical_histories.includes(opt) ? '#52c41a' : '#d9d9d9',
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
                <Input
                  placeholder="其他病史（可选）"
                  value={profileEdits.medical_other}
                  onChange={(v) => setProfileEdits((p) => ({ ...p, medical_other: v }))}
                  style={{ '--font-size': '13px', marginTop: 6, background: '#fff', borderRadius: 8, padding: '5px 10px', border: '1px solid #d9d9d9' }}
                />
              </div>

              <div>
                <div className="text-xs text-gray-500 mb-1">过敏史</div>
                <div className="flex flex-wrap gap-2">
                  {allergyOptions.map((opt) => (
                    <Tag
                      key={opt}
                      onClick={() => toggleProfileTag('allergies', opt)}
                      style={{
                        '--background-color': profileEdits.allergies.includes(opt) ? '#52c41a' : '#fff',
                        '--text-color': profileEdits.allergies.includes(opt) ? '#fff' : '#666',
                        '--border-color': profileEdits.allergies.includes(opt) ? '#52c41a' : '#d9d9d9',
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
                <Input
                  placeholder="其他过敏史（可选）"
                  value={profileEdits.allergy_other}
                  onChange={(v) => setProfileEdits((p) => ({ ...p, allergy_other: v }))}
                  style={{ '--font-size': '13px', marginTop: 6, background: '#fff', borderRadius: 8, padding: '5px 10px', border: '1px solid #d9d9d9' }}
                />
              </div>
            </div>
          </div>

          <Button
            block
            loading={analyzing}
            onClick={handleConfirm}
            style={{
              marginTop: 20,
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              color: '#fff',
              border: 'none',
              borderRadius: 24,
              height: 46,
              fontSize: 15,
            }}
          >
            确认并开始分析
          </Button>
        </div>
      </Popup>

      {/* Add member popup (two-step, same as health-profile) */}
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
                    {medicalHistoryOptions.map((opt) => (
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
                    {allergyOptions.map((opt) => (
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

      {/* Birthday picker for existing member profile */}
      <DatePicker
        visible={birthdayPickerVisible}
        onClose={() => setBirthdayPickerVisible(false)}
        precision="day"
        max={new Date()}
        min={new Date('1900-01-01')}
        onConfirm={(val) => {
          const d = val as Date;
          const str = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
          setProfileEdits((p) => ({ ...p, birthday: str }));
          setBirthdayPickerVisible(false);
        }}
        title="选择出生日期"
      />

      {/* Birthday picker for new member */}
      <DatePicker
        visible={newBirthdayPickerVisible}
        onClose={() => setNewBirthdayPickerVisible(false)}
        precision="day"
        max={new Date()}
        min={new Date('1900-01-01')}
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
