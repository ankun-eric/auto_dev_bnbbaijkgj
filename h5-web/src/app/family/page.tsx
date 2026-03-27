'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Button, Dialog, Form, Input, Picker, Avatar, Tag, List, Empty } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';

interface FamilyMember {
  id: number;
  name: string;
  relation: string;
  age: number;
  avatar: string;
  healthStatus: string;
}

const mockMembers: FamilyMember[] = [
  { id: 1, name: '张大爷', relation: '父亲', age: 65, avatar: '', healthStatus: '高血压' },
  { id: 2, name: '李阿姨', relation: '母亲', age: 62, avatar: '', healthStatus: '健康' },
  { id: 3, name: '小明', relation: '儿子', age: 8, avatar: '', healthStatus: '健康' },
];

const relationOptions = [
  [
    { label: '父亲', value: '父亲' },
    { label: '母亲', value: '母亲' },
    { label: '配偶', value: '配偶' },
    { label: '儿子', value: '儿子' },
    { label: '女儿', value: '女儿' },
    { label: '其他', value: '其他' },
  ],
];

export default function FamilyPage() {
  const router = useRouter();
  const [members, setMembers] = useState<FamilyMember[]>(mockMembers);
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState('');
  const [newRelation, setNewRelation] = useState('');
  const [newAge, setNewAge] = useState('');

  const addMember = () => {
    if (!newName || !newRelation || !newAge) return;
    const member: FamilyMember = {
      id: Date.now(),
      name: newName,
      relation: newRelation,
      age: parseInt(newAge),
      avatar: '',
      healthStatus: '健康',
    };
    setMembers([...members, member]);
    setShowAdd(false);
    setNewName('');
    setNewRelation('');
    setNewAge('');
  };

  const statusColor = (status: string) => (status === '健康' ? '#52c41a' : '#fa8c16');

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        家庭成员
      </NavBar>

      <div className="px-4 pt-4">
        <div
          className="rounded-xl p-4 mb-4 text-center"
          style={{ background: 'linear-gradient(135deg, #52c41a20, #13c2c220)' }}
        >
          <div className="text-3xl mb-2">👨‍👩‍👧‍👦</div>
          <h2 className="font-bold">我的家庭</h2>
          <p className="text-xs text-gray-500 mt-1">为家人建立健康档案，关爱每一位家人</p>
        </div>

        {members.length === 0 ? (
          <Empty description="暂无家庭成员" style={{ padding: '40px 0' }} />
        ) : (
          members.map((m) => (
            <Card key={m.id} style={{ marginBottom: 12, borderRadius: 12 }}>
              <div className="flex items-center">
                <Avatar
                  src={m.avatar}
                  style={{
                    '--size': '48px',
                    '--border-radius': '50%',
                    background: 'linear-gradient(135deg, #52c41a40, #13c2c240)',
                  }}
                />
                <div className="flex-1 ml-3">
                  <div className="flex items-center">
                    <span className="font-medium">{m.name}</span>
                    <Tag
                      style={{
                        '--background-color': '#1890ff15',
                        '--text-color': '#1890ff',
                        '--border-color': 'transparent',
                        fontSize: 10,
                        marginLeft: 8,
                      }}
                    >
                      {m.relation}
                    </Tag>
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    {m.age}岁 ·{' '}
                    <span style={{ color: statusColor(m.healthStatus) }}>{m.healthStatus}</span>
                  </div>
                </div>
                <Button
                  size="small"
                  onClick={() => router.push(`/health-profile?member=${m.id}`)}
                  style={{ color: '#52c41a', borderColor: '#52c41a', borderRadius: 16, fontSize: 12 }}
                >
                  健康档案
                </Button>
              </div>
            </Card>
          ))
        )}

        <Button
          block
          onClick={() => setShowAdd(true)}
          style={{
            marginTop: 16,
            background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
            color: '#fff',
            border: 'none',
            borderRadius: 24,
            height: 44,
          }}
        >
          <AddOutline /> 添加家庭成员
        </Button>
      </div>

      <Dialog
        visible={showAdd}
        title="添加家庭成员"
        content={
          <div className="space-y-3 pt-2">
            <Input
              placeholder="请输入姓名"
              value={newName}
              onChange={setNewName}
              style={{ '--font-size': '14px' }}
              className="bg-gray-50 rounded-lg px-3 py-2"
            />
            <Input
              placeholder="关系（如：父亲、母亲）"
              value={newRelation}
              onChange={setNewRelation}
              style={{ '--font-size': '14px' }}
              className="bg-gray-50 rounded-lg px-3 py-2"
            />
            <Input
              placeholder="年龄"
              value={newAge}
              onChange={setNewAge}
              type="number"
              style={{ '--font-size': '14px' }}
              className="bg-gray-50 rounded-lg px-3 py-2"
            />
          </div>
        }
        closeOnAction
        onClose={() => setShowAdd(false)}
        actions={[
          [
            { key: 'cancel', text: '取消', onClick: () => setShowAdd(false) },
            { key: 'confirm', text: '添加', onClick: addMember, bold: true, style: { color: '#52c41a' } },
          ],
        ]}
      />
    </div>
  );
}
