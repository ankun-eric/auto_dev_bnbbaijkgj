'use client';

import { useRouter } from 'next/navigation';
import { List, Card, Button, Tag, FloatingBubble } from 'antd-mobile';
import { AddOutline, MessageOutline } from 'antd-mobile-icons';

const consultTypes = [
  {
    key: 'health',
    title: '健康问答',
    desc: 'AI全科医生在线解答',
    icon: '💬',
    color: '#52c41a',
  },
  {
    key: 'symptom',
    title: '症状自查',
    desc: '智能分析症状可能原因',
    icon: '🔍',
    color: '#1890ff',
  },
  {
    key: 'tcm',
    title: '中医辨证',
    desc: '舌诊面诊体质分析',
    icon: '🏥',
    color: '#eb2f96',
  },
  {
    key: 'drug',
    title: '药物查询',
    desc: '用药指南与相互作用',
    icon: '💊',
    color: '#fa8c16',
  },
];

const recentChats = [
  {
    id: 'session-1',
    title: '头痛相关咨询',
    lastMessage: '建议您注意休息，避免长时间用眼...',
    time: '今天 14:30',
    type: 'health',
  },
  {
    id: 'session-2',
    title: '体质辨识',
    lastMessage: '根据您的舌象分析，您偏向气虚体质...',
    time: '昨天 09:15',
    type: 'tcm',
  },
  {
    id: 'session-3',
    title: '阿莫西林用药咨询',
    lastMessage: '阿莫西林属于青霉素类抗生素...',
    time: '3天前',
    type: 'drug',
  },
];

const typeLabel: Record<string, { text: string; color: string }> = {
  health: { text: '问答', color: '#52c41a' },
  symptom: { text: '自查', color: '#1890ff' },
  tcm: { text: '中医', color: '#eb2f96' },
  drug: { text: '用药', color: '#fa8c16' },
};

export default function AIPage() {
  const router = useRouter();

  const startNewChat = (type: string) => {
    const sessionId = `new-${type}-${Date.now()}`;
    router.push(`/chat/${sessionId}?type=${type}`);
  };

  return (
    <div className="pb-20">
      <div className="gradient-header">
        <h1 className="text-xl font-bold">AI智能问诊</h1>
        <p className="text-xs opacity-80 mt-1">选择问诊类型，开始健康咨询</p>
      </div>

      <div className="px-4 -mt-4">
        <div className="grid grid-cols-2 gap-3 mb-4">
          {consultTypes.map((ct) => (
            <div
              key={ct.key}
              className="card cursor-pointer"
              onClick={() => {
                if (ct.key === 'symptom') router.push('/symptom');
                else if (ct.key === 'tcm') router.push('/tcm');
                else if (ct.key === 'drug') router.push('/drug');
                else startNewChat(ct.key);
              }}
            >
              <div className="flex items-start">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-xl mr-3"
                  style={{ background: `${ct.color}15` }}
                >
                  {ct.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm">{ct.title}</div>
                  <div className="text-xs text-gray-400 mt-1">{ct.desc}</div>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between mb-3">
          <span className="section-title mb-0">最近对话</span>
          <span className="text-xs text-gray-400">{recentChats.length}条记录</span>
        </div>

        {recentChats.length === 0 ? (
          <div className="card text-center py-10">
            <MessageOutline style={{ fontSize: 40, color: '#ddd' }} />
            <p className="text-sm text-gray-400 mt-3">暂无对话记录</p>
            <Button
              size="small"
              onClick={() => startNewChat('health')}
              style={{
                marginTop: 12,
                color: '#52c41a',
                borderColor: '#52c41a',
                borderRadius: 20,
              }}
            >
              开始第一次问诊
            </Button>
          </div>
        ) : (
          <List style={{ '--border-top': 'none', '--border-bottom': 'none' }}>
            {recentChats.map((chat) => (
              <Card
                key={chat.id}
                onClick={() => router.push(`/chat/${chat.id}`)}
                style={{ marginBottom: 8, borderRadius: 12 }}
              >
                <div className="flex items-start">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center">
                      <span className="font-medium text-sm">{chat.title}</span>
                      <Tag
                        style={{
                          '--border-radius': '4px',
                          '--background-color': `${typeLabel[chat.type].color}15`,
                          '--text-color': typeLabel[chat.type].color,
                          '--border-color': 'transparent',
                          fontSize: 10,
                          marginLeft: 8,
                        }}
                      >
                        {typeLabel[chat.type].text}
                      </Tag>
                    </div>
                    <p className="text-xs text-gray-400 mt-1 truncate">{chat.lastMessage}</p>
                  </div>
                  <span className="text-xs text-gray-300 ml-2 whitespace-nowrap">{chat.time}</span>
                </div>
              </Card>
            ))}
          </List>
        )}
      </div>

      <FloatingBubble
        style={{
          '--initial-position-bottom': '80px',
          '--initial-position-right': '20px',
          '--edge-distance': '20px',
          '--background': 'linear-gradient(135deg, #52c41a, #13c2c2)',
          '--size': '52px',
        }}
        onClick={() => startNewChat('health')}
      >
        <AddOutline fontSize={24} color="#fff" />
      </FloatingBubble>
    </div>
  );
}
