'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Form, Input, Picker, Button, Card, List, Tag, TextArea, Toast } from 'antd-mobile';

const mockProfile = {
  name: '张三',
  gender: '男',
  age: '35',
  height: '175',
  weight: '70',
  bloodType: 'A型',
  allergies: ['青霉素', '花粉'],
  diseases: ['高血压'],
  medications: ['降压药'],
};

export default function HealthProfilePage() {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [profile, setProfile] = useState(mockProfile);
  const [allergyInput, setAllergyInput] = useState('');
  const [diseaseInput, setDiseaseInput] = useState('');
  const [medInput, setMedInput] = useState('');

  const handleSave = () => {
    Toast.show({ content: '保存成功' });
    setEditing(false);
  };

  const addTag = (type: 'allergies' | 'diseases' | 'medications', value: string) => {
    if (value.trim()) {
      setProfile({ ...profile, [type]: [...profile[type], value.trim()] });
      if (type === 'allergies') setAllergyInput('');
      if (type === 'diseases') setDiseaseInput('');
      if (type === 'medications') setMedInput('');
    }
  };

  const removeTag = (type: 'allergies' | 'diseases' | 'medications', index: number) => {
    setProfile({ ...profile, [type]: profile[type].filter((_, i) => i !== index) });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar
        onBack={() => router.back()}
        right={
          <span className="text-sm text-primary" onClick={() => editing ? handleSave() : setEditing(true)}>
            {editing ? '保存' : '编辑'}
          </span>
        }
        style={{ background: '#fff' }}
      >
        健康档案
      </NavBar>

      <div className="px-4 pt-4">
        <div
          className="rounded-xl p-4 mb-4 text-center"
          style={{ background: 'linear-gradient(135deg, #52c41a20, #13c2c220)' }}
        >
          <div className="text-3xl mb-2">📋</div>
          <h2 className="font-bold">{profile.name}的健康档案</h2>
          <p className="text-xs text-gray-500 mt-1">完善健康信息，获得更精准的AI建议</p>
        </div>

        <Card style={{ borderRadius: 12, marginBottom: 12 }} title="基础信息">
          <List style={{ '--border-top': 'none', '--border-bottom': 'none', '--padding-left': '0' }}>
            <List.Item extra={editing ? <Input value={profile.name} onChange={(v) => setProfile({ ...profile, name: v })} style={{ '--text-align': 'right' }} /> : profile.name}>
              姓名
            </List.Item>
            <List.Item extra={profile.gender}>性别</List.Item>
            <List.Item extra={editing ? <Input value={profile.age} onChange={(v) => setProfile({ ...profile, age: v })} style={{ '--text-align': 'right' }} /> : `${profile.age}岁`}>
              年龄
            </List.Item>
            <List.Item extra={editing ? <Input value={profile.height} onChange={(v) => setProfile({ ...profile, height: v })} style={{ '--text-align': 'right' }} /> : `${profile.height}cm`}>
              身高
            </List.Item>
            <List.Item extra={editing ? <Input value={profile.weight} onChange={(v) => setProfile({ ...profile, weight: v })} style={{ '--text-align': 'right' }} /> : `${profile.weight}kg`}>
              体重
            </List.Item>
            <List.Item extra={profile.bloodType}>血型</List.Item>
          </List>
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 12 }} title="过敏史">
          <div className="flex flex-wrap gap-2">
            {profile.allergies.map((a, i) => (
              <Tag
                key={i}
                style={{
                  '--background-color': '#f5222d15',
                  '--text-color': '#f5222d',
                  '--border-color': 'transparent',
                  padding: '4px 10px',
                  borderRadius: 16,
                }}
                onClick={() => editing && removeTag('allergies', i)}
              >
                {a} {editing && '×'}
              </Tag>
            ))}
          </div>
          {editing && (
            <div className="flex gap-2 mt-3">
              <input
                className="flex-1 bg-gray-50 rounded-lg px-3 py-2 text-sm outline-none"
                placeholder="添加过敏源"
                value={allergyInput}
                onChange={(e) => setAllergyInput(e.target.value)}
              />
              <Button size="small" onClick={() => addTag('allergies', allergyInput)}
                style={{ color: '#52c41a', borderColor: '#52c41a', borderRadius: 16 }}>
                添加
              </Button>
            </div>
          )}
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 12 }} title="既往病史">
          <div className="flex flex-wrap gap-2">
            {profile.diseases.map((d, i) => (
              <Tag
                key={i}
                style={{
                  '--background-color': '#fa8c1615',
                  '--text-color': '#fa8c16',
                  '--border-color': 'transparent',
                  padding: '4px 10px',
                  borderRadius: 16,
                }}
                onClick={() => editing && removeTag('diseases', i)}
              >
                {d} {editing && '×'}
              </Tag>
            ))}
          </div>
          {editing && (
            <div className="flex gap-2 mt-3">
              <input
                className="flex-1 bg-gray-50 rounded-lg px-3 py-2 text-sm outline-none"
                placeholder="添加病史"
                value={diseaseInput}
                onChange={(e) => setDiseaseInput(e.target.value)}
              />
              <Button size="small" onClick={() => addTag('diseases', diseaseInput)}
                style={{ color: '#52c41a', borderColor: '#52c41a', borderRadius: 16 }}>
                添加
              </Button>
            </div>
          )}
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 12 }} title="用药记录">
          <div className="flex flex-wrap gap-2">
            {profile.medications.map((m, i) => (
              <Tag
                key={i}
                style={{
                  '--background-color': '#1890ff15',
                  '--text-color': '#1890ff',
                  '--border-color': 'transparent',
                  padding: '4px 10px',
                  borderRadius: 16,
                }}
                onClick={() => editing && removeTag('medications', i)}
              >
                {m} {editing && '×'}
              </Tag>
            ))}
          </div>
          {editing && (
            <div className="flex gap-2 mt-3">
              <input
                className="flex-1 bg-gray-50 rounded-lg px-3 py-2 text-sm outline-none"
                placeholder="添加用药"
                value={medInput}
                onChange={(e) => setMedInput(e.target.value)}
              />
              <Button size="small" onClick={() => addTag('medications', medInput)}
                style={{ color: '#52c41a', borderColor: '#52c41a', borderRadius: 16 }}>
                添加
              </Button>
            </div>
          )}
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 80 }} title="健康趋势">
          <div className="text-center py-8 text-gray-400 text-sm">
            <div className="text-3xl mb-2">📊</div>
            <p>体检数据趋势图</p>
            <p className="text-xs mt-1">上传多次体检报告后自动生成</p>
          </div>
        </Card>
      </div>
    </div>
  );
}
