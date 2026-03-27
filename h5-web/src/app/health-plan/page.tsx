'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Button, ProgressBar, Tag, Checkbox, Toast, FloatingBubble } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';

interface Task {
  id: number;
  title: string;
  desc: string;
  done: boolean;
  points: number;
}

interface Plan {
  id: number;
  title: string;
  desc: string;
  progress: number;
  days: number;
  totalDays: number;
  color: string;
}

const mockPlans: Plan[] = [
  { id: 1, title: '减重计划', desc: '目标：1个月减重5斤', progress: 45, days: 14, totalDays: 30, color: '#52c41a' },
  { id: 2, title: '睡眠改善', desc: '目标：每晚11点前入睡', progress: 70, days: 21, totalDays: 30, color: '#1890ff' },
];

const initialTasks: Task[] = [
  { id: 1, title: '晨起一杯温水', desc: '250ml温水，唤醒身体', done: false, points: 5 },
  { id: 2, title: '步行8000步', desc: '日常运动，增强体质', done: false, points: 10 },
  { id: 3, title: '午餐吃蔬菜', desc: '至少200g绿叶蔬菜', done: true, points: 5 },
  { id: 4, title: '饮水2000ml', desc: '分多次少量饮水', done: false, points: 5 },
  { id: 5, title: '冥想10分钟', desc: '放松身心，缓解压力', done: false, points: 10 },
  { id: 6, title: '11点前入睡', desc: '保证充足睡眠', done: false, points: 10 },
];

export default function HealthPlanPage() {
  const router = useRouter();
  const [tasks, setTasks] = useState<Task[]>(initialTasks);

  const toggleTask = (id: number) => {
    setTasks(tasks.map((t) => {
      if (t.id === id && !t.done) {
        Toast.show({ content: `打卡成功 +${t.points}积分` });
        return { ...t, done: true };
      }
      return t;
    }));
  };

  const doneCount = tasks.filter((t) => t.done).length;
  const totalPoints = tasks.reduce((sum, t) => sum + (t.done ? t.points : 0), 0);

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        健康计划
      </NavBar>

      <div
        className="px-4 py-5"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
      >
        <div className="flex items-center justify-between text-white">
          <div>
            <div className="text-lg font-bold">今日任务</div>
            <div className="text-xs opacity-70 mt-1">已完成 {doneCount}/{tasks.length} · 已获{totalPoints}积分</div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold">{Math.round((doneCount / tasks.length) * 100)}%</div>
            <div className="text-xs opacity-70">完成率</div>
          </div>
        </div>
        <ProgressBar
          percent={(doneCount / tasks.length) * 100}
          style={{
            '--track-width': '8px',
            '--fill-color': '#fff',
            '--track-color': 'rgba(255,255,255,0.3)',
            marginTop: 12,
          }}
        />
      </div>

      <div className="px-4 -mt-3">
        <Card style={{ borderRadius: 12, marginBottom: 16 }}>
          <div className="section-title">今日打卡</div>
          {tasks.map((task) => (
            <div
              key={task.id}
              className="flex items-center py-3 border-b border-gray-50 last:border-b-0"
              onClick={() => toggleTask(task.id)}
            >
              <Checkbox
                checked={task.done}
                style={{
                  '--icon-size': '20px',
                } as React.CSSProperties}
              />
              <div className="flex-1 ml-3">
                <div className={`text-sm ${task.done ? 'text-gray-400 line-through' : ''}`}>
                  {task.title}
                </div>
                <div className="text-xs text-gray-400 mt-0.5">{task.desc}</div>
              </div>
              <Tag
                style={{
                  '--background-color': task.done ? '#52c41a15' : '#fa8c1615',
                  '--text-color': task.done ? '#52c41a' : '#fa8c16',
                  '--border-color': 'transparent',
                  fontSize: 10,
                }}
              >
                {task.done ? `+${task.points}` : `${task.points}分`}
              </Tag>
            </div>
          ))}
        </Card>

        <div className="section-title">我的计划</div>
        {mockPlans.map((plan) => (
          <Card key={plan.id} style={{ borderRadius: 12, marginBottom: 12 }}>
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">{plan.title}</span>
              <Tag
                style={{
                  '--background-color': `${plan.color}15`,
                  '--text-color': plan.color,
                  '--border-color': 'transparent',
                  fontSize: 10,
                }}
              >
                第{plan.days}天
              </Tag>
            </div>
            <p className="text-xs text-gray-400 mb-2">{plan.desc}</p>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-gray-400">进度</span>
              <span className="text-xs" style={{ color: plan.color }}>{plan.progress}%</span>
            </div>
            <ProgressBar
              percent={plan.progress}
              style={{
                '--track-width': '6px',
                '--fill-color': plan.color,
              }}
            />
          </Card>
        ))}
      </div>

      <FloatingBubble
        style={{
          '--initial-position-bottom': '24px',
          '--initial-position-right': '20px',
          '--edge-distance': '20px',
          '--background': 'linear-gradient(135deg, #52c41a, #13c2c2)',
          '--size': '52px',
        }}
        onClick={() => {
          Toast.show({ content: 'AI正在为您生成个性化健康计划...' });
          setTimeout(() => {
            const sessionId = `plan-${Date.now()}`;
            router.push(`/chat/${sessionId}?type=health&msg=${encodeURIComponent('请根据我的健康档案为我制定一份个性化的健康计划')}`);
          }, 1000);
        }}
      >
        <AddOutline fontSize={24} color="#fff" />
      </FloatingBubble>
    </div>
  );
}
