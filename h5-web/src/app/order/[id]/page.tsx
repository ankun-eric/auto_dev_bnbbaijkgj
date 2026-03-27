'use client';

import { useRouter, useParams } from 'next/navigation';
import { NavBar, Card, Steps, Tag, Button, Divider, Toast } from 'antd-mobile';

const mockOrder = {
  id: 'ORD20240315001',
  title: '基础体检套餐',
  price: 298,
  status: 'unused',
  statusText: '待核销',
  createTime: '2024-03-15 14:30',
  payTime: '2024-03-15 14:32',
  verifyCode: 'BN2024031500128',
  location: '宾尼健康体检中心（朝阳分店）',
  validUntil: '2024-06-15',
  items: [
    '一般检查（身高、体重、血压等）',
    '血常规（25项）',
    '尿常规（12项）',
    '肝功能（6项）',
  ],
};

export default function OrderDetailPage() {
  const router = useRouter();
  const params = useParams();

  const copyCode = () => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(mockOrder.verifyCode);
    }
    Toast.show({ content: '核销码已复制' });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        订单详情
      </NavBar>

      <div
        className="px-4 py-6 text-center"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
      >
        <div className="text-white text-lg font-bold">{mockOrder.statusText}</div>
        <div className="text-white/70 text-xs mt-1">请在有效期内前往门店核销</div>
      </div>

      <div className="px-4 -mt-3">
        {mockOrder.status === 'unused' && (
          <Card style={{ borderRadius: 12, marginBottom: 12, textAlign: 'center' }}>
            <div className="text-sm text-gray-500 mb-2">核销码</div>
            <div className="text-2xl font-bold tracking-widest text-primary mb-2">
              {mockOrder.verifyCode}
            </div>
            <Button
              size="small"
              onClick={copyCode}
              style={{ color: '#52c41a', borderColor: '#52c41a', borderRadius: 16, fontSize: 12 }}
            >
              复制核销码
            </Button>
            <div className="text-xs text-gray-400 mt-3">
              有效期至：{mockOrder.validUntil}
            </div>
          </Card>
        )}

        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="flex items-center mb-3">
            <div
              className="w-14 h-14 rounded-lg flex items-center justify-center text-2xl flex-shrink-0"
              style={{ background: '#f6ffed' }}
            >
              🏥
            </div>
            <div className="ml-3 flex-1">
              <div className="font-medium">{mockOrder.title}</div>
              <div className="text-sm font-bold text-red-500 mt-1">¥{mockOrder.price}</div>
            </div>
          </div>
          <Divider />
          <div className="space-y-2 text-sm text-gray-500">
            <div className="flex justify-between">
              <span>订单编号</span>
              <span>{mockOrder.id}</span>
            </div>
            <div className="flex justify-between">
              <span>下单时间</span>
              <span>{mockOrder.createTime}</span>
            </div>
            <div className="flex justify-between">
              <span>支付时间</span>
              <span>{mockOrder.payTime}</span>
            </div>
            <div className="flex justify-between">
              <span>服务地点</span>
              <span className="text-right max-w-[60%]">{mockOrder.location}</span>
            </div>
          </div>
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 12 }} title="服务内容">
          <div className="space-y-2">
            {mockOrder.items.map((item, i) => (
              <div key={i} className="flex items-start text-sm">
                <span className="text-primary mr-2">✓</span>
                <span className="text-gray-600">{item}</span>
              </div>
            ))}
            <div className="text-xs text-gray-400">...等共18项检查</div>
          </div>
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 20 }} title="订单进度">
          <Steps
            current={1}
            direction="vertical"
            style={{ '--title-font-size': '13px', '--description-font-size': '11px' }}
          >
            <Steps.Step title="下单成功" description={mockOrder.createTime} />
            <Steps.Step title="支付完成" description={mockOrder.payTime} />
            <Steps.Step title="待核销" description="请在有效期内前往门店" />
            <Steps.Step title="服务完成" />
          </Steps>
        </Card>
      </div>
    </div>
  );
}
