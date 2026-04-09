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
  Picker,
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
  '高血压', '糖尿病（1型）', '糖尿病（2型）', '冠心病', '脑卒中',
  '哮喘', '慢性支气管炎', '甲状腺疾病', '肝病', '肾病', '痛风', '骨质疏松',
];

const allergyOptions = [
  '青霉素', '磺胺类', '头孢类', '阿司匹林', '碘造影剂',
  '海鲜', '花粉', '尘螨', '乳胶', '坚果',
];

const relationshipOptions = [
  [
    { label: '父亲', value: 'father' },
    { label: '母亲', value: 'mother' },
    { label: '配偶', value: 'spouse' },
    { label: '子女', value: 'child' },
    { label: '兄弟姐妹', value: 'sibling' },
    { label: '祖父母', value: 'grandparent' },
    { label: '外祖父母', value: 'maternal_grandparent' },
    { label: '其他', value: 'other' },
  ],
];

interface FamilyMember {
  id: number;
  nickname: string;
  relationship_type: string;
  birthday?: string;
  gender?: string;
  height?: number;
  weight?: number;
  medical_histories?: string[];
  allergies?: string[];
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

const relationshipLabelMap: Record<string, string> = {
  father: '父亲',
  mother: '母亲',
  spouse: '配偶',
  child: '子女',
  sibling: '兄弟姐妹',
  grandparent: '祖父母',
  maternal_grandparent: '外祖父母',
  other: '其他',
};

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
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null); // null = self
  const [profileEdits, setProfileEdits] = useState<HealthProfile>(emptyProfile());
  const [showAddForm, setShowAddForm] = useState(false);
  const [newMember, setNewMember] = useState<{
    relationship: string;
    nickname: string;
    birthday: string;
    gender: string;
    height: string;
    weight: string;
    medical_histories: string[];
    medical_other: string;
    allergies: string[];
    allergy_other: string;
  }>({
    relationship: '',
    nickname: '',
    birthday: '',
    gender: '',
    height: '',
    weight: '',
    medical_histories: [],
    medical_other: '',
    allergies: [],
    allergy_other: '',
  });
  const [relationPickerVisible, setRelationPickerVisible] = useState(false);
  const [birthdayPickerVisible, setBirthdayPickerVisible] = useState(false);
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
      setFamilyMembers(Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : []);
    } catch {
      setFamilyMembers([]);
    }
    setSelectedMemberId(null);
    setProfileEdits(emptyProfile());
    setShowAddForm(false);
    setMemberPopupVisible(true);
  };

  const handleSelectMember = (id: number | null) => {
    setSelectedMemberId(id);
    setShowAddForm(false);
    if (id === null) {
      setProfileEdits(emptyProfile());
    } else {
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
      }
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

  const toggleNewMemberTag = (field: 'medical_histories' | 'allergies', val: string) => {
    setNewMember((prev) => ({
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

  const handleConfirm = async () => {
    setAnalyzing(true);
    try {
      let familyMemberId: number | null = null;
      let memberLabel = '自己';

      if (showAddForm) {
        // Create new family member
        if (!newMember.nickname.trim()) {
          Toast.show({ content: '请填写昵称' });
          setAnalyzing(false);
          return;
        }
        if (!newMember.relationship) {
          Toast.show({ content: '请选择关系类型' });
          setAnalyzing(false);
          return;
        }
        const createPayload: any = {
          relationship_type: newMember.relationship,
          nickname: newMember.nickname.trim(),
        };
        if (newMember.birthday) createPayload.birthday = newMember.birthday;
        if (newMember.gender) createPayload.gender = newMember.gender;
        if (newMember.height) createPayload.height = Number(newMember.height);
        if (newMember.weight) createPayload.weight = Number(newMember.weight);
        const medical = buildMedicalHistories(newMember.medical_histories, newMember.medical_other);
        if (medical.length) createPayload.medical_histories = medical;
        const allergies = buildMedicalHistories(newMember.allergies, newMember.allergy_other);
        if (allergies.length) createPayload.allergies = allergies;

        const res: any = await api.post('/api/family/members', createPayload);
        const created = res.data || res;
        familyMemberId = created.id;
        memberLabel = `${relationshipLabelMap[newMember.relationship] || newMember.relationship}·${newMember.nickname.trim()}`;
      } else if (selectedMemberId !== null) {
        familyMemberId = selectedMemberId;
        const m = familyMembers.find((x) => x.id === selectedMemberId);
        memberLabel = m ? `${relationshipLabelMap[m.relationship_type] || m.relationship_type}·${m.nickname}` : '家庭成员';
        // Update profile if needed
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
          await api.put(`/api/family/members/${selectedMemberId}`, updatePayload).catch(() => null);
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
  const showProfile = selectedMemberId !== null || selectedMemberId === null;

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
          {/* Header */}
          <div className="flex items-center justify-between py-4 border-b border-gray-100">
            <span className="text-base font-semibold">为谁咨询</span>
            <button
              onClick={() => setMemberPopupVisible(false)}
              className="text-gray-400 text-xl leading-none"
            >
              ×
            </button>
          </div>

          {/* Member list */}
          <div className="mt-3 space-y-2">
            {/* Self */}
            <div
              className="flex items-center justify-between px-3 py-3 rounded-xl cursor-pointer"
              style={{
                background: selectedMemberId === null && !showAddForm ? '#f6ffed' : '#f9f9f9',
                border: selectedMemberId === null && !showAddForm ? '1px solid #52c41a' : '1px solid transparent',
              }}
              onClick={() => handleSelectMember(null)}
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm"
                  style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}>
                  我
                </div>
                <span className="text-sm font-medium">为自己</span>
              </div>
              <Radio
                checked={selectedMemberId === null && !showAddForm}
                onChange={() => handleSelectMember(null)}
                style={{ '--icon-size': '18px', '--font-size': '14px', '--gap': '6px' }}
              />
            </div>

            {/* Family members */}
            {familyMembers.map((m) => (
              <div
                key={m.id}
                className="flex items-center justify-between px-3 py-3 rounded-xl cursor-pointer"
                style={{
                  background: selectedMemberId === m.id && !showAddForm ? '#f6ffed' : '#f9f9f9',
                  border: selectedMemberId === m.id && !showAddForm ? '1px solid #52c41a' : '1px solid transparent',
                }}
                onClick={() => handleSelectMember(m.id)}
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm"
                    style={{ background: '#87d068' }}>
                    {m.nickname.charAt(0)}
                  </div>
                  <div>
                    <div className="text-sm font-medium">{m.nickname}</div>
                    <div className="text-xs text-gray-400">
                      {relationshipLabelMap[m.relationship_type] || m.relationship_type}
                    </div>
                  </div>
                </div>
                <Radio
                  checked={selectedMemberId === m.id && !showAddForm}
                  onChange={() => handleSelectMember(m.id)}
                  style={{ '--icon-size': '18px', '--font-size': '14px', '--gap': '6px' }}
                />
              </div>
            ))}

            {/* Add member button */}
            <div
              className="flex items-center gap-2 px-3 py-3 rounded-xl cursor-pointer"
              style={{ background: showAddForm ? '#f6ffed' : '#f9f9f9', border: showAddForm ? '1px solid #52c41a' : '1px solid transparent' }}
              onClick={() => { setShowAddForm(true); setSelectedMemberId(undefined as any); }}
            >
              <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-lg"
                style={{ background: '#52c41a' }}>
                +
              </div>
              <span className="text-sm text-primary font-medium" style={{ color: '#52c41a' }}>添加家庭成员</span>
            </div>
          </div>

          {/* Add new member form */}
          {showAddForm && (
            <div className="mt-4 p-4 rounded-xl" style={{ background: '#f6ffed', border: '1px solid #b7eb8f' }}>
              <div className="text-sm font-semibold mb-3" style={{ color: '#52c41a' }}>新建家庭成员</div>

              <div className="space-y-3">
                <div>
                  <div className="text-xs text-gray-500 mb-1">关系类型 *</div>
                  <div
                    className="bg-white rounded-lg px-3 py-2 text-sm cursor-pointer flex items-center justify-between"
                    style={{ border: '1px solid #d9d9d9' }}
                    onClick={() => setRelationPickerVisible(true)}
                  >
                    <span style={{ color: newMember.relationship ? '#333' : '#bbb' }}>
                      {newMember.relationship ? (relationshipLabelMap[newMember.relationship] || newMember.relationship) : '请选择关系'}
                    </span>
                    <span className="text-gray-300">▼</span>
                  </div>
                </div>

                <div>
                  <div className="text-xs text-gray-500 mb-1">昵称 *</div>
                  <Input
                    placeholder="请输入昵称"
                    value={newMember.nickname}
                    onChange={(v) => setNewMember((p) => ({ ...p, nickname: v }))}
                    style={{ '--font-size': '14px', background: '#fff', borderRadius: 8, padding: '6px 12px', border: '1px solid #d9d9d9' }}
                  />
                </div>

                <div>
                  <div className="text-xs text-gray-500 mb-1">出生日期</div>
                  <div
                    className="bg-white rounded-lg px-3 py-2 text-sm cursor-pointer flex items-center justify-between"
                    style={{ border: '1px solid #d9d9d9' }}
                    onClick={() => setNewBirthdayPickerVisible(true)}
                  >
                    <span style={{ color: newMember.birthday ? '#333' : '#bbb' }}>
                      {newMember.birthday || '请选择出生日期'}
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
                          background: newMember.gender === g ? '#52c41a' : '#fff',
                          color: newMember.gender === g ? '#fff' : '#666',
                          border: `1px solid ${newMember.gender === g ? '#52c41a' : '#d9d9d9'}`,
                        }}
                        onClick={() => setNewMember((p) => ({ ...p, gender: g }))}
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
                      value={newMember.height}
                      onChange={(v) => setNewMember((p) => ({ ...p, height: v }))}
                      style={{ '--font-size': '14px', background: '#fff', borderRadius: 8, padding: '6px 12px', border: '1px solid #d9d9d9' }}
                    />
                  </div>
                  <div className="flex-1">
                    <div className="text-xs text-gray-500 mb-1">体重 (kg)</div>
                    <Input
                      type="number"
                      placeholder="如：65"
                      value={newMember.weight}
                      onChange={(v) => setNewMember((p) => ({ ...p, weight: v }))}
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
                        onClick={() => toggleNewMemberTag('medical_histories', opt)}
                        style={{
                          '--background-color': newMember.medical_histories.includes(opt) ? '#52c41a' : '#fff',
                          '--text-color': newMember.medical_histories.includes(opt) ? '#fff' : '#666',
                          '--border-color': newMember.medical_histories.includes(opt) ? '#52c41a' : '#d9d9d9',
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
                    value={newMember.medical_other}
                    onChange={(v) => setNewMember((p) => ({ ...p, medical_other: v }))}
                    style={{ '--font-size': '13px', marginTop: 6, background: '#fff', borderRadius: 8, padding: '5px 10px', border: '1px solid #d9d9d9' }}
                  />
                </div>

                <div>
                  <div className="text-xs text-gray-500 mb-1">过敏史</div>
                  <div className="flex flex-wrap gap-2">
                    {allergyOptions.map((opt) => (
                      <Tag
                        key={opt}
                        onClick={() => toggleNewMemberTag('allergies', opt)}
                        style={{
                          '--background-color': newMember.allergies.includes(opt) ? '#52c41a' : '#fff',
                          '--text-color': newMember.allergies.includes(opt) ? '#fff' : '#666',
                          '--border-color': newMember.allergies.includes(opt) ? '#52c41a' : '#d9d9d9',
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
                    value={newMember.allergy_other}
                    onChange={(v) => setNewMember((p) => ({ ...p, allergy_other: v }))}
                    style={{ '--font-size': '13px', marginTop: 6, background: '#fff', borderRadius: 8, padding: '5px 10px', border: '1px solid #d9d9d9' }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Health profile for existing members */}
          {!showAddForm && (
            <div className="mt-4 p-4 rounded-xl" style={{ background: '#f9f9f9', border: '1px solid #e8e8e8' }}>
              <div className="text-sm font-semibold mb-3 text-gray-600">
                {selectedMemberId === null ? '我的' : (selectedMember ? `${selectedMember.nickname}的` : '')}健康档案
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
          )}

          {/* Confirm button */}
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

      {/* Relationship picker for new member */}
      <Picker
        columns={relationshipOptions}
        visible={relationPickerVisible}
        onClose={() => setRelationPickerVisible(false)}
        onConfirm={(val) => {
          setNewMember((p) => ({ ...p, relationship: String(val[0] || '') }));
          setRelationPickerVisible(false);
        }}
        title="选择关系类型"
      />

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
          setNewMember((p) => ({ ...p, birthday: str }));
          setNewBirthdayPickerVisible(false);
        }}
        title="选择出生日期"
      />
    </div>
  );
}
