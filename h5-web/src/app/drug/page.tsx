'use client';

import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { NavBar, SearchBar, Card, List, Tag, Tabs, ImageUploader, Button, Toast, Empty } from 'antd-mobile';
import type { ImageUploadItem } from 'antd-mobile/es/components/image-uploader';

const mockDrugs = [
  {
    id: 1,
    name: '阿莫西林胶囊',
    type: '处方药',
    category: '抗生素',
    desc: '青霉素类抗生素，用于敏感菌感染',
    usage: '口服，一次0.5g，一日3次',
    caution: '青霉素过敏者禁用',
  },
  {
    id: 2,
    name: '布洛芬缓释胶囊',
    type: '非处方药',
    category: '解热镇痛',
    desc: '用于缓解轻至中度疼痛、退热',
    usage: '口服，一次1粒，一日2次',
    caution: '消化道溃疡患者慎用',
  },
  {
    id: 3,
    name: '六味地黄丸',
    type: '非处方药',
    category: '中成药',
    desc: '滋阴补肾，用于肾阴亏损',
    usage: '口服，一次8丸，一日3次',
    caution: '脾胃虚弱者不宜',
  },
  {
    id: 4,
    name: '阿司匹林肠溶片',
    type: '非处方药',
    category: '解热镇痛',
    desc: '用于退热、镇痛、抗炎、抗血小板聚集',
    usage: '口服，一次50-100mg，一日1次',
    caution: '有出血倾向者禁用',
  },
];

export default function DrugPageWrapper() {
  return (
    <Suspense fallback={<div />}>
      <DrugPage />
    </Suspense>
  );
}

function DrugPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [search, setSearch] = useState(searchParams.get('q') || '');
  const [activeTab, setActiveTab] = useState('search');
  const [drugImages, setDrugImages] = useState<ImageUploadItem[]>([]);
  const [selectedDrug, setSelectedDrug] = useState<typeof mockDrugs[0] | null>(null);
  const [interactionDrugs, setInteractionDrugs] = useState<string[]>([]);
  const [interactionInput, setInteractionInput] = useState('');

  const filteredDrugs = mockDrugs.filter(
    (d) => !search || d.name.includes(search) || d.category.includes(search)
  );

  const handleUpload = async (file: File) => {
    return { url: URL.createObjectURL(file) };
  };

  const handlePhotoSearch = () => {
    if (drugImages.length === 0) {
      Toast.show({ content: '请先拍摄药品照片' });
      return;
    }
    Toast.show({ icon: 'loading', content: 'AI识别中...', duration: 0 });
    setTimeout(() => {
      Toast.clear();
      setSelectedDrug(mockDrugs[0]);
    }, 1500);
  };

  const checkInteraction = () => {
    if (interactionDrugs.length < 2) {
      Toast.show({ content: '请至少添加两种药物' });
      return;
    }
    const sessionId = `drug-interaction-${Date.now()}`;
    const msg = `请分析以下药物的相互作用：${interactionDrugs.join('、')}`;
    router.push(`/chat/${sessionId}?type=drug&msg=${encodeURIComponent(msg)}`);
  };

  const addInteractionDrug = () => {
    if (interactionInput.trim()) {
      setInteractionDrugs([...interactionDrugs, interactionInput.trim()]);
      setInteractionInput('');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        药物查询
      </NavBar>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        style={{
          '--active-line-color': '#52c41a',
          '--active-title-color': '#52c41a',
          background: '#fff',
        }}
      >
        <Tabs.Tab key="search" title="搜索药品" />
        <Tabs.Tab key="photo" title="拍照识药" />
        <Tabs.Tab key="interaction" title="相互作用" />
      </Tabs>

      <div className="px-4 pt-3">
        {activeTab === 'search' && (
          <>
            <SearchBar
              placeholder="搜索药品名称"
              value={search}
              onChange={setSearch}
              style={{
                '--border-radius': '20px',
                '--height': '40px',
                marginBottom: 12,
              }}
            />
            {selectedDrug ? (
              <div>
                <Card style={{ borderRadius: 12 }}>
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-bold text-lg">{selectedDrug.name}</span>
                    <Tag
                      style={{
                        '--background-color': selectedDrug.type === '处方药' ? '#f5222d15' : '#52c41a15',
                        '--text-color': selectedDrug.type === '处方药' ? '#f5222d' : '#52c41a',
                        '--border-color': 'transparent',
                      }}
                    >
                      {selectedDrug.type}
                    </Tag>
                  </div>
                  <div className="space-y-3 text-sm">
                    <div>
                      <span className="text-gray-400">分类：</span>
                      <span>{selectedDrug.category}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">说明：</span>
                      <span>{selectedDrug.desc}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">用法：</span>
                      <span>{selectedDrug.usage}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">注意：</span>
                      <span className="text-red-500">{selectedDrug.caution}</span>
                    </div>
                  </div>
                </Card>
                <Button
                  block
                  onClick={() => {
                    const sessionId = `drug-${Date.now()}`;
                    router.push(`/chat/${sessionId}?type=drug&msg=${encodeURIComponent(`请详细介绍${selectedDrug.name}的用药指南`)}`);
                  }}
                  style={{
                    marginTop: 12,
                    background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 24,
                    height: 44,
                  }}
                >
                  AI详细咨询
                </Button>
                <Button
                  block
                  fill="none"
                  onClick={() => setSelectedDrug(null)}
                  style={{ marginTop: 8, color: '#999' }}
                >
                  返回列表
                </Button>
              </div>
            ) : filteredDrugs.length === 0 ? (
              <Empty description="未找到相关药品" />
            ) : (
              filteredDrugs.map((drug) => (
                <Card
                  key={drug.id}
                  onClick={() => setSelectedDrug(drug)}
                  style={{ marginBottom: 10, borderRadius: 12 }}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium text-sm">{drug.name}</div>
                      <div className="text-xs text-gray-400 mt-1">{drug.desc}</div>
                    </div>
                    <Tag
                      style={{
                        '--background-color': `${drug.type === '处方药' ? '#f5222d' : '#52c41a'}15`,
                        '--text-color': drug.type === '处方药' ? '#f5222d' : '#52c41a',
                        '--border-color': 'transparent',
                        fontSize: 10,
                      }}
                    >
                      {drug.type}
                    </Tag>
                  </div>
                </Card>
              ))
            )}
          </>
        )}

        {activeTab === 'photo' && (
          <div className="card">
            <div className="section-title">拍照识药</div>
            <p className="text-xs text-gray-400 mb-3">拍摄药品包装或药片照片，AI自动识别</p>
            <ImageUploader
              value={drugImages}
              onChange={setDrugImages}
              upload={handleUpload}
              maxCount={3}
              style={{ '--cell-size': '100px' }}
            />
            <Button
              block
              onClick={handlePhotoSearch}
              style={{
                marginTop: 16,
                background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                color: '#fff',
                border: 'none',
                borderRadius: 24,
                height: 44,
              }}
            >
              AI识别
            </Button>
          </div>
        )}

        {activeTab === 'interaction' && (
          <div className="card">
            <div className="section-title">药物相互作用检测</div>
            <p className="text-xs text-gray-400 mb-3">输入正在服用的药物，检测是否存在相互作用</p>
            <div className="flex gap-2 mb-3">
              <input
                className="flex-1 bg-gray-50 rounded-xl px-4 py-2 text-sm border-none outline-none"
                placeholder="输入药品名称"
                value={interactionInput}
                onChange={(e) => setInteractionInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addInteractionDrug()}
              />
              <Button
                size="small"
                onClick={addInteractionDrug}
                style={{ color: '#52c41a', borderColor: '#52c41a', borderRadius: 20 }}
              >
                添加
              </Button>
            </div>
            <div className="flex flex-wrap gap-2 mb-4">
              {interactionDrugs.map((d, i) => (
                <Tag
                  key={i}
                  style={{
                    '--background-color': '#52c41a15',
                    '--text-color': '#52c41a',
                    '--border-color': '#52c41a30',
                    padding: '4px 10px',
                    borderRadius: 16,
                  }}
                  onClick={() => setInteractionDrugs(interactionDrugs.filter((_, j) => j !== i))}
                >
                  {d} ×
                </Tag>
              ))}
            </div>
            <Button
              block
              onClick={checkInteraction}
              disabled={interactionDrugs.length < 2}
              style={{
                background: interactionDrugs.length >= 2 ? 'linear-gradient(135deg, #52c41a, #13c2c2)' : '#e8e8e8',
                color: interactionDrugs.length >= 2 ? '#fff' : '#999',
                border: 'none',
                borderRadius: 24,
                height: 44,
              }}
            >
              检测相互作用
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
