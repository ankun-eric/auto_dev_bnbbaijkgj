'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Input, Button, SpinLoading } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';

import GreenNavBar from '@/components/GreenNavBar';
interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  time: string;
}

const initialMessages: Message[] = [
  {
    id: '1',
    role: 'assistant',
    content: '您好！欢迎来到宾尼小康客服中心，我是AI客服小康。请问有什么可以帮到您？\n\n您可以咨询：\n• 订单相关问题\n• 服务使用指南\n• 积分与会员\n• 账户与设置',
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
  },
];

const autoReplies: Record<string, string> = {
  订单: '关于订单问题，您可以在「我的 → 我的订单」中查看订单状态。如需退款，请提供订单号，我将为您处理。',
  退款: '退款流程：\n1. 进入「我的订单」\n2. 找到需要退款的订单\n3. 点击「申请退款」\n4. 填写退款原因\n\n退款将在3个工作日内原路退回。',
  积分: '积分获取方式：\n• 每日签到 +10积分\n• 完成健康任务 +5~20积分\n• 邀请好友 +100积分\n• 购买服务返积分\n\n积分可在积分商城兑换礼品和优惠券。',
  会员: '宾尼小康付费会员：\n• 免费会员：注册即可，享基础权益\n• 守护版/家庭版/年度版：付费会员，享 AI 电话告警、AI 用药提醒、守护人扩容、商城折扣等专属权益\n\n说明：原"积分会员等级"已升级为付费会员套餐，权益更清晰、服务更直接。您账户中的积分完全保留，可在积分商城兑换或下单时按比例抵扣金额（单笔最多 20%）。',
};

export default function CustomerServicePage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [inputVal, setInputVal] = useState('');
  const [loading, setLoading] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = () => {
    const text = inputVal.trim();
    if (!text || loading) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputVal('');
    setLoading(true);

    setTimeout(() => {
      let reply = '感谢您的咨询，我已记录您的问题。如需进一步帮助，您可以点击下方「转人工」按钮联系人工客服。';
      for (const [keyword, response] of Object.entries(autoReplies)) {
        if (text.includes(keyword)) {
          reply = response;
          break;
        }
      }
      const aiMsg: Message = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: reply,
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, aiMsg]);
      setLoading(false);
    }, 800);
  };

  const transferHuman = () => {
    const sysMsg: Message = {
      id: `sys-${Date.now()}`,
      role: 'system',
      content: '正在为您转接人工客服，请稍候...',
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages((prev) => [...prev, sysMsg]);
    showToast('已为您转接人工客服');
  };

  return (
    <div className="flex flex-col h-screen bh-ai-page">
      <div className="cs-topbar-wrap" style={{ background: 'linear-gradient(135deg, #0C4A6E, #0284C7)', borderRadius: '0 0 16px 16px' }}>
        <style>{`.cs-topbar-wrap > div { background: transparent !important; }`}</style>
        <GreenNavBar
          right={
            <span
              className="text-sm font-medium"
              style={{ color: '#fff' }}
              onClick={transferHuman}
            >
              转人工
            </span>
          }
        >
          <span style={{ color: '#fff' }}>在线客服</span>
        </GreenNavBar>
      </div>

      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3">
        {messages.map((msg) => {
          if (msg.role === 'system') {
            return (
              <div key={msg.id} className="text-center my-3">
                <span className="text-xs text-gray-400 bg-gray-100 px-3 py-1 rounded-full">
                  {msg.content}
                </span>
              </div>
            );
          }
          return (
            <div
              key={msg.id}
              className={`flex mb-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'assistant' && (
                <div className="flex-shrink-0 flex items-center justify-center mr-2" style={{ width: 48, height: 48, borderRadius: '50%', background: 'linear-gradient(135deg, #38BDF8, #0284C7)' }}>
                  <span className="text-white text-sm font-bold">客</span>
                </div>
              )}
              <div className="max-w-[75%]">
                <div
                  className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-line ${
                    msg.role === 'user' ? 'rounded-tr-sm' : 'rounded-tl-sm'
                  }`}
                  style={msg.role === 'user'
                    ? { background: 'linear-gradient(135deg, #7DD3FC 0%, #38BDF8 100%)', color: '#fff', boxShadow: '0 1px 4px rgba(2,132,199,0.18)' }
                    : { background: '#fff', color: '#1F2937', borderRadius: 12, borderLeft: '3px solid #0EA5E9', boxShadow: '0 1px 4px rgba(56,189,248,0.08)' }}
                >
                  {msg.content}
                </div>
                <div className={`text-xs text-gray-300 mt-1 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                  {msg.time}
                </div>
              </div>
              {msg.role === 'user' && (
                <div className="flex-shrink-0 flex items-center justify-center ml-2" style={{ width: 48, height: 48, borderRadius: '50%', background: 'linear-gradient(135deg, #38BDF8, #0284C7)' }}>
                  <span className="text-white text-sm font-bold">我</span>
                </div>
              )}
            </div>
          );
        })}
        {loading && (
          <div className="flex items-center mb-4">
            <div className="flex-shrink-0 flex items-center justify-center mr-2" style={{ width: 48, height: 48, borderRadius: '50%', background: 'linear-gradient(135deg, #38BDF8, #0284C7)' }}>
              <span className="text-white text-sm font-bold">客</span>
            </div>
            <div className="rounded-2xl rounded-tl-sm px-4 py-3" style={{ background: '#fff', borderRadius: 12, borderLeft: '3px solid #0EA5E9', boxShadow: '0 1px 4px rgba(56,189,248,0.08)' }}>
              <SpinLoading style={{ '--size': '20px', '--color': '#0EA5E9' }} />
            </div>
          </div>
        )}
      </div>

      <div className="bg-white border-t border-gray-100 px-4 py-3 flex items-end gap-2">
        <div className="flex-1 bh-ai-input px-4 py-2">
          <Input
            placeholder="输入您的问题..."
            value={inputVal}
            onChange={setInputVal}
            onEnterPress={sendMessage}
            style={{ '--font-size': '14px' }}
          />
        </div>
        <Button
          onClick={sendMessage}
          disabled={!inputVal.trim() || loading}
          style={{
            background: inputVal.trim() ? 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)' : '#e8e8e8',
            color: inputVal.trim() ? '#fff' : '#999',
            border: 'none',
            borderRadius: '50%',
            width: 40,
            height: 40,
            padding: 0,
          }}
        >
          ➤
        </Button>
      </div>
    </div>
  );
}
