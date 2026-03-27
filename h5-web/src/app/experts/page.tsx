'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, SearchBar, Card, Tag, Avatar, Rate } from 'antd-mobile';

const mockExperts = [
  {
    id: 1,
    name: '王医生',
    title: '主任中医师',
    department: '中医内科',
    hospital: '宾尼中医诊所',
    rating: 4.9,
    consultCount: 2360,
    price: 198,
    tags: ['中医调理', '慢病管理', '体质辨识'],
    desc: '从事中医临床30余年，擅长中医内科疾病诊治',
  },
  {
    id: 2,
    name: '李营养师',
    title: '高级营养师',
    department: '营养科',
    hospital: '宾尼健康中心',
    rating: 4.8,
    consultCount: 1580,
    price: 128,
    tags: ['减脂饮食', '营养配餐', '慢病饮食'],
    desc: '注册营养师，擅长个性化饮食方案定制',
  },
  {
    id: 3,
    name: '张心理师',
    title: '心理咨询师',
    department: '心理科',
    hospital: '宾尼心理咨询中心',
    rating: 4.7,
    consultCount: 890,
    price: 258,
    tags: ['焦虑抑郁', '睡眠障碍', '压力管理'],
    desc: '国家二级心理咨询师，10年临床心理咨询经验',
  },
  {
    id: 4,
    name: '陈医生',
    title: '副主任医师',
    department: '全科',
    hospital: '宾尼健康体检中心',
    rating: 4.9,
    consultCount: 3100,
    price: 168,
    tags: ['体检解读', '健康管理', '家庭医生'],
    desc: '全科医生，擅长体检报告解读和健康管理',
  },
];

export default function ExpertsPage() {
  const router = useRouter();
  const [search, setSearch] = useState('');

  const filtered = mockExperts.filter(
    (e) => !search || e.name.includes(search) || e.department.includes(search) || e.tags.some((t) => t.includes(search))
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        专家列表
      </NavBar>

      <div className="px-4 pt-3">
        <SearchBar
          placeholder="搜索专家姓名、科室"
          value={search}
          onChange={setSearch}
          style={{ '--border-radius': '20px', '--height': '40px', marginBottom: 12 }}
        />

        {filtered.map((expert) => (
          <Card
            key={expert.id}
            onClick={() => router.push(`/expert/${expert.id}`)}
            style={{ marginBottom: 12, borderRadius: 12 }}
          >
            <div className="flex">
              <Avatar
                src=""
                style={{
                  '--size': '56px',
                  '--border-radius': '12px',
                  background: 'linear-gradient(135deg, #52c41a40, #13c2c240)',
                  flexShrink: 0,
                }}
              />
              <div className="flex-1 ml-3 min-w-0">
                <div className="flex items-center">
                  <span className="font-bold">{expert.name}</span>
                  <span className="text-xs text-gray-400 ml-2">{expert.title}</span>
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  {expert.department} · {expert.hospital}
                </div>
                <div className="flex items-center mt-1">
                  <span className="text-xs text-yellow-500">★ {expert.rating}</span>
                  <span className="text-xs text-gray-400 ml-2">接诊{expert.consultCount}次</span>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {expert.tags.map((tag) => (
                    <Tag
                      key={tag}
                      style={{
                        '--background-color': '#52c41a10',
                        '--text-color': '#52c41a',
                        '--border-color': 'transparent',
                        fontSize: 10,
                      }}
                    >
                      {tag}
                    </Tag>
                  ))}
                </div>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-primary font-bold">¥{expert.price}<span className="text-xs text-gray-400 font-normal">/次</span></span>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
