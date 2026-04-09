'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Toast, DatePicker, Input, TextArea } from 'antd-mobile';
import api from '@/lib/api';

interface DiseasePreset {
  id: number;
  name: string;
  category: string;
}

interface Step1Data {
  name: string;
  gender: string;
  birthday: string;
  height: string;
  weight: string;
}

interface Step2Data {
  chronic_diseases: string[];
}

interface Step3Data {
  drug_allergies: string;
  food_allergies: string;
  other_allergies: string;
}

interface Step4Data {
  genetic_diseases: string[];
}

function formatDate(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export default function HealthGuidePage() {
  const router = useRouter();

  const [currentStep, setCurrentStep] = useState(1);
  const [memberId, setMemberId] = useState<number | null>(null);
  const [memberError, setMemberError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [chronicPresets, setChronicPresets] = useState<DiseasePreset[]>([]);
  const [geneticPresets, setGeneticPresets] = useState<DiseasePreset[]>([]);

  const [birthdayPickerVisible, setBirthdayPickerVisible] = useState(false);

  const [step1, setStep1] = useState<Step1Data>({
    name: '',
    gender: '',
    birthday: '',
    height: '',
    weight: '',
  });

  const [step2, setStep2] = useState<Step2Data>({ chronic_diseases: [] });
  const [step3, setStep3] = useState<Step3Data>({
    drug_allergies: '',
    food_allergies: '',
    other_allergies: '',
  });
  const [step4, setStep4] = useState<Step4Data>({ genetic_diseases: [] });

  useEffect(() => {
    const init = async () => {
      try {
        const membersRes: any = await api.get('/api/family/members');
        const items = Array.isArray(membersRes.items) ? membersRes.items : [];
        const self = items.find((m: any) => m.is_self);
        if (!self) {
          setMemberError(true);
          setLoading(false);
          return;
        }
        setMemberId(self.id);

        const [profileRes, chronicRes, geneticRes] = await Promise.allSettled([
          api.get(`/api/health/profile/member/${self.id}`),
          api.get('/api/disease-presets?category=chronic'),
          api.get('/api/disease-presets?category=genetic'),
        ]);

        if (profileRes.status === 'fulfilled') {
          const p: any = profileRes.value;
          setStep1({
            name: p.name || '',
            gender: p.gender || '',
            birthday: p.birthday || '',
            height: p.height != null ? String(p.height) : '',
            weight: p.weight != null ? String(p.weight) : '',
          });
          setStep2({ chronic_diseases: p.chronic_diseases || [] });
          setStep3({
            drug_allergies: p.drug_allergies || '',
            food_allergies: p.food_allergies || '',
            other_allergies: p.other_allergies || '',
          });
          setStep4({ genetic_diseases: p.genetic_diseases || [] });
        }

        if (chronicRes.status === 'fulfilled') {
          const c: any = chronicRes.value;
          setChronicPresets(Array.isArray(c.items) ? c.items : []);
        }
        if (geneticRes.status === 'fulfilled') {
          const g: any = geneticRes.value;
          setGeneticPresets(Array.isArray(g.items) ? g.items : []);
        }
      } catch {
        setMemberError(true);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const saveCurrentStep = async () => {
    if (!memberId) return;
    let patch: Record<string, any> = {};
    if (currentStep === 1) {
      patch = {
        name: step1.name,
        gender: step1.gender,
        birthday: step1.birthday || null,
        height: step1.height ? Number(step1.height) : null,
        weight: step1.weight ? Number(step1.weight) : null,
      };
    } else if (currentStep === 2) {
      patch = { chronic_diseases: step2.chronic_diseases };
    } else if (currentStep === 3) {
      patch = {
        drug_allergies: step3.drug_allergies,
        food_allergies: step3.food_allergies,
        other_allergies: step3.other_allergies,
      };
    } else if (currentStep === 4) {
      patch = { genetic_diseases: step4.genetic_diseases };
    }
    await api.put(`/api/health/profile/member/${memberId}`, patch);
  };

  const handleNext = async () => {
    setSubmitting(true);
    try {
      await saveCurrentStep();
      setCurrentStep((s) => s + 1);
    } catch {
      Toast.show({ content: '保存失败，请重试' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleFinish = async () => {
    setSubmitting(true);
    try {
      await saveCurrentStep();
      await api.post('/api/health/guide-status', { action: 'complete' });
      Toast.show({ content: '档案完善成功 ✓', duration: 2000 });
      setTimeout(() => router.replace('/home'), 1500);
    } catch {
      Toast.show({ content: '提交失败，请重试' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSkip = async () => {
    try {
      await api.post('/api/health/guide-status', { action: 'skip' });
    } catch {
      // ignore
    }
    router.replace('/home');
  };

  const handlePrev = () => {
    setCurrentStep((s) => s - 1);
  };

  if (loading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: 'linear-gradient(160deg, #f0faf0 0%, #e8f4ff 100%)' }}
      >
        <div className="text-sm text-gray-400">加载中...</div>
      </div>
    );
  }

  if (memberError) {
    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center gap-4 px-8"
        style={{ background: 'linear-gradient(160deg, #f0faf0 0%, #e8f4ff 100%)' }}
      >
        <div className="text-sm text-gray-500 text-center">获取成员信息失败，请返回首页重试</div>
        <Button
          style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)', color: '#fff', border: 'none', borderRadius: 24 }}
          onClick={() => router.replace('/home')}
        >
          返回首页
        </Button>
      </div>
    );
  }

  const totalSteps = 4;
  const progress = (currentStep / totalSteps) * 100;

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: 'linear-gradient(160deg, #f0faf0 0%, #e8f4ff 100%)' }}
    >
      {/* Skip button */}
      <div className="flex justify-end px-4 pt-4">
        <button
          className="text-sm px-3 py-1 rounded-full"
          style={{ color: '#999', background: 'rgba(255,255,255,0.7)' }}
          onClick={handleSkip}
        >
          跳过
        </button>
      </div>

      {/* Step indicator */}
      <div className="px-6 pt-2 pb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-base font-bold text-gray-800">完善健康档案</span>
          <span className="text-sm text-gray-400">第 {currentStep} 步 / 共 {totalSteps} 步</span>
        </div>
        <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${progress}%`,
              background: 'linear-gradient(90deg, #52c41a, #13c2c2)',
            }}
          />
        </div>
        <div className="flex justify-between mt-2">
          {[1, 2, 3, 4].map((s) => (
            <div key={s} className="flex flex-col items-center">
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-all"
                style={{
                  background: s <= currentStep ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#e8e8e8',
                  color: s <= currentStep ? '#fff' : '#bbb',
                }}
              >
                {s}
              </div>
              <span className="text-[10px] mt-1" style={{ color: s === currentStep ? '#52c41a' : '#bbb' }}>
                {s === 1 ? '基本信息' : s === 2 ? '慢性病史' : s === 3 ? '过敏史' : '遗传病史'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Step content */}
      <div className="flex-1 px-4 overflow-y-auto pb-4">
        {currentStep === 1 && (
          <Step1Form data={step1} onChange={setStep1} birthdayPickerVisible={birthdayPickerVisible} setBirthdayPickerVisible={setBirthdayPickerVisible} />
        )}
        {currentStep === 2 && (
          <Step2Form data={step2} onChange={setStep2} presets={chronicPresets} />
        )}
        {currentStep === 3 && (
          <Step3Form data={step3} onChange={setStep3} />
        )}
        {currentStep === 4 && (
          <Step4Form data={step4} onChange={setStep4} presets={geneticPresets} />
        )}
      </div>

      {/* Bottom buttons */}
      <div className="px-4 py-4 flex gap-3" style={{ background: 'rgba(255,255,255,0.8)', backdropFilter: 'blur(8px)' }}>
        {currentStep > 1 && (
          <Button
            style={{
              flex: 1,
              borderRadius: 24,
              height: 48,
              border: '1.5px solid #52c41a',
              color: '#52c41a',
              background: 'transparent',
              fontWeight: 600,
            }}
            onClick={handlePrev}
            disabled={submitting}
          >
            上一步
          </Button>
        )}
        <Button
          loading={submitting}
          style={{
            flex: currentStep > 1 ? 2 : 1,
            borderRadius: 24,
            height: 48,
            border: 'none',
            background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
            color: '#fff',
            fontWeight: 600,
            fontSize: 16,
          }}
          onClick={currentStep === totalSteps ? handleFinish : handleNext}
        >
          {currentStep === totalSteps ? '完成' : '下一步'}
        </Button>
      </div>
    </div>
  );
}

// ─── Step 1: Basic Info ────────────────────────────────────────────────────────

function Step1Form({
  data,
  onChange,
  birthdayPickerVisible,
  setBirthdayPickerVisible,
}: {
  data: Step1Data;
  onChange: (d: Step1Data) => void;
  birthdayPickerVisible: boolean;
  setBirthdayPickerVisible: (v: boolean) => void;
}) {
  return (
    <div className="rounded-2xl bg-white shadow-sm p-4 space-y-4">
      <div className="text-sm font-bold text-gray-700 mb-2">📋 基本信息</div>

      <FormRow label="姓名">
        <Input
          placeholder="请输入姓名"
          value={data.name}
          onChange={(v) => onChange({ ...data, name: v })}
          style={{ '--font-size': '14px', textAlign: 'right' }}
        />
      </FormRow>

      <FormRow label="性别">
        <div className="flex gap-2">
          {['male', 'female'].map((g) => (
            <button
              key={g}
              className="px-4 py-1 rounded-full text-xs font-medium transition-all"
              style={{
                background: data.gender === g ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#f5f5f5',
                color: data.gender === g ? '#fff' : '#888',
              }}
              onClick={() => onChange({ ...data, gender: g })}
            >
              {g === 'male' ? '男' : '女'}
            </button>
          ))}
        </div>
      </FormRow>

      <FormRow label="出生日期">
        <button
          className="text-sm text-right"
          style={{ color: data.birthday ? '#333' : '#bbb' }}
          onClick={() => setBirthdayPickerVisible(true)}
        >
          {data.birthday || '请选择'}
        </button>
      </FormRow>

      <FormRow label="身高 (cm)">
        <Input
          type="number"
          placeholder="请输入"
          value={data.height}
          onChange={(v) => onChange({ ...data, height: v })}
          style={{ '--font-size': '14px', textAlign: 'right', width: 100 }}
        />
      </FormRow>

      <FormRow label="体重 (kg)">
        <Input
          type="number"
          placeholder="请输入"
          value={data.weight}
          onChange={(v) => onChange({ ...data, weight: v })}
          style={{ '--font-size': '14px', textAlign: 'right', width: 100 }}
        />
      </FormRow>

      <DatePicker
        visible={birthdayPickerVisible}
        onClose={() => setBirthdayPickerVisible(false)}
        precision="day"
        max={new Date()}
        min={new Date('1900-01-01')}
        title="选择出生日期"
        onConfirm={(val) => {
          onChange({ ...data, birthday: formatDate(val as Date) });
          setBirthdayPickerVisible(false);
        }}
      />
    </div>
  );
}

// ─── Step 2: Chronic Diseases ─────────────────────────────────────────────────

function Step2Form({
  data,
  onChange,
  presets,
}: {
  data: Step2Data;
  onChange: (d: Step2Data) => void;
  presets: DiseasePreset[];
}) {
  const toggle = (name: string) => {
    const list = data.chronic_diseases;
    onChange({
      chronic_diseases: list.includes(name) ? list.filter((x) => x !== name) : [...list, name],
    });
  };

  return (
    <div className="rounded-2xl bg-white shadow-sm p-4">
      <div className="text-sm font-bold text-gray-700 mb-3">🏥 慢性病史</div>
      {presets.length === 0 ? (
        <p className="text-xs text-gray-400 text-center py-6">暂无预设选项，请在档案页手动填写</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {presets.map((p) => {
            const selected = data.chronic_diseases.includes(p.name);
            return (
              <button
                key={p.id}
                className="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
                style={{
                  background: selected ? 'linear-gradient(135deg, #fa8c16, #faad14)' : '#f5f5f5',
                  color: selected ? '#fff' : '#666',
                }}
                onClick={() => toggle(p.name)}
              >
                {p.name}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Step 3: Allergies ────────────────────────────────────────────────────────

function Step3Form({
  data,
  onChange,
}: {
  data: Step3Data;
  onChange: (d: Step3Data) => void;
}) {
  return (
    <div className="rounded-2xl bg-white shadow-sm p-4 space-y-4">
      <div className="text-sm font-bold text-gray-700 mb-2">⚠️ 过敏史</div>

      <div>
        <div className="text-xs text-gray-500 mb-1">药物过敏</div>
        <TextArea
          rows={2}
          placeholder="请描述药物过敏情况（如无请留空）"
          value={data.drug_allergies}
          onChange={(v) => onChange({ ...data, drug_allergies: v })}
          style={{ '--font-size': '14px', background: '#f9f9f9', borderRadius: 12, padding: '8px 12px' }}
        />
      </div>

      <div>
        <div className="text-xs text-gray-500 mb-1">食物过敏</div>
        <TextArea
          rows={2}
          placeholder="请描述食物过敏情况（如无请留空）"
          value={data.food_allergies}
          onChange={(v) => onChange({ ...data, food_allergies: v })}
          style={{ '--font-size': '14px', background: '#f9f9f9', borderRadius: 12, padding: '8px 12px' }}
        />
      </div>

      <div>
        <div className="text-xs text-gray-500 mb-1">其他过敏</div>
        <TextArea
          rows={2}
          placeholder="请描述其他过敏情况（如无请留空）"
          value={data.other_allergies}
          onChange={(v) => onChange({ ...data, other_allergies: v })}
          style={{ '--font-size': '14px', background: '#f9f9f9', borderRadius: 12, padding: '8px 12px' }}
        />
      </div>
    </div>
  );
}

// ─── Step 4: Genetic Diseases ─────────────────────────────────────────────────

function Step4Form({
  data,
  onChange,
  presets,
}: {
  data: Step4Data;
  onChange: (d: Step4Data) => void;
  presets: DiseasePreset[];
}) {
  const toggle = (name: string) => {
    const list = data.genetic_diseases;
    onChange({
      genetic_diseases: list.includes(name) ? list.filter((x) => x !== name) : [...list, name],
    });
  };

  return (
    <div className="rounded-2xl bg-white shadow-sm p-4">
      <div className="text-sm font-bold text-gray-700 mb-3">🧬 遗传病史</div>
      {presets.length === 0 ? (
        <p className="text-xs text-gray-400 text-center py-6">暂无预设选项，请在档案页手动填写</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {presets.map((p) => {
            const selected = data.genetic_diseases.includes(p.name);
            return (
              <button
                key={p.id}
                className="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
                style={{
                  background: selected ? 'linear-gradient(135deg, #722ed1, #1890ff)' : '#f5f5f5',
                  color: selected ? '#fff' : '#666',
                }}
                onClick={() => toggle(p.name)}
              >
                {p.name}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Helper: FormRow ──────────────────────────────────────────────────────────

function FormRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-50 last:border-b-0">
      <span className="text-sm text-gray-500 flex-shrink-0 w-28">{label}</span>
      <div className="flex-1 flex justify-end">{children}</div>
    </div>
  );
}
