'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Button, TextArea, Tag, Grid, Card, Steps, Toast } from 'antd-mobile';

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

export default function SymptomPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [selectedPart, setSelectedPart] = useState('');
  const [selectedSymptoms, setSelectedSymptoms] = useState<string[]>([]);
  const [description, setDescription] = useState('');
  const [duration, setDuration] = useState('');
  const [analyzing, setAnalyzing] = useState(false);

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
    else handleAnalyze();
  };

  const handleAnalyze = () => {
    setAnalyzing(true);
    Toast.show({ icon: 'loading', content: 'AI分析中...', duration: 0 });
    setTimeout(() => {
      Toast.clear();
      setAnalyzing(false);
      const sessionId = `symptom-${Date.now()}`;
      const msg = `我的${bodyParts.find((p) => p.key === selectedPart)?.label}不舒服，主要症状有：${selectedSymptoms.join('、')}。${description ? `补充描述：${description}。` : ''}${duration ? `持续时间：${duration}。` : ''}请帮我分析可能的原因。`;
      router.push(`/chat/${sessionId}?type=symptom&msg=${encodeURIComponent(msg)}`);
    }, 1500);
  };

  const durations = ['今天刚开始', '1-3天', '一周内', '一个月内', '超过一个月'];

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
    </div>
  );
}
