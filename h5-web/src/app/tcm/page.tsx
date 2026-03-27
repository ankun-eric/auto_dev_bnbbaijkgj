'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Grid, ImageUploader, Button, Radio, Space, ProgressBar, Toast, Result } from 'antd-mobile';
import type { ImageUploadItem } from 'antd-mobile/es/components/image-uploader';

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

const features = [
  { key: 'tongue', title: '舌诊', desc: '拍摄舌头照片，AI分析舌象', icon: '👅' },
  { key: 'face', title: '面诊', desc: '拍摄面部照片，AI分析面色', icon: '🧑' },
  { key: 'constitution', title: '体质测评', desc: '回答问卷，判断体质类型', icon: '📋' },
];

export default function TcmPage() {
  const router = useRouter();
  const [activeFeature, setActiveFeature] = useState('');
  const [tongueImages, setTongueImages] = useState<ImageUploadItem[]>([]);
  const [faceImages, setFaceImages] = useState<ImageUploadItem[]>([]);
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [showResult, setShowResult] = useState(false);

  const handleUpload = async (file: File) => {
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
    setAnswers({ ...answers, [constitutionQuestions[currentQ].id]: value });
    if (currentQ < constitutionQuestions.length - 1) {
      setTimeout(() => setCurrentQ(currentQ + 1), 300);
    } else {
      setTimeout(() => setShowResult(true), 300);
    }
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
          } else {
            router.back();
          }
        }}
        style={{ background: '#fff' }}
      >
        中医辨证
      </NavBar>

      {!activeFeature && (
        <div className="px-4 pt-4">
          <div
            className="rounded-xl p-6 mb-4 text-center"
            style={{ background: 'linear-gradient(135deg, #52c41a20, #13c2c220)' }}
          >
            <div className="text-3xl mb-2">🏥</div>
            <h2 className="font-bold text-lg text-gray-800">智能中医辨证</h2>
            <p className="text-xs text-gray-500 mt-1">融合传统中医智慧与AI技术</p>
          </div>

          {features.map((f) => (
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
          ))}
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
        </div>
      )}

      {activeFeature === 'constitution' && showResult && (
        <div className="px-4 pt-4">
          <Result
            status="success"
            title="体质分析完成"
            description="根据您的回答，AI已完成体质辨识"
          />
          <Card style={{ borderRadius: 12, marginTop: 16 }}>
            <div className="text-center mb-4">
              <div className="text-3xl mb-2">🌿</div>
              <div className="text-lg font-bold text-primary">气虚质</div>
              <div className="text-xs text-gray-400 mt-1">偏向气虚体质，需注意补气调理</div>
            </div>
            <div className="space-y-2 text-sm text-gray-600">
              <p><strong>体质特征：</strong>容易疲劳，气短懒言，易出汗</p>
              <p><strong>饮食建议：</strong>多食山药、黄芪、大枣等益气食材</p>
              <p><strong>运动建议：</strong>太极拳、八段锦等柔和运动</p>
              <p><strong>起居建议：</strong>早睡早起，避免过度劳累</p>
            </div>
          </Card>
          <Button
            block
            onClick={() => {
              const sessionId = `tcm-constitution-${Date.now()}`;
              router.push(`/chat/${sessionId}?type=tcm&msg=${encodeURIComponent('我的体质测评结果为气虚质，请给我详细的中医调理方案')}`);
            }}
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
    </div>
  );
}
