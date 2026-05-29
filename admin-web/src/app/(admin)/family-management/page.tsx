'use client';

/**
 * [Bug 修复 v1.2 §6] 守护关系管理 - 卡片网格化改造
 *
 * 关键变更：
 * - 顶部 120px 天蓝 Hero 区 + 4 个统计数字（总数 / 主守护人 / 普通守护人 / 付费）
 * - 响应式卡片网格 + 上下分区式卡片（顶部头像+姓名+角色徽章 / 中部关系+会员+优先级 / 底部双进度条 + 详情按钮）
 * - 主色 #1890FF / 圆角 20px / 阴影 0 4px 16px rgba(24,144,255,0.08)
 * - 角色徽章：主守护人 #1890FF 实心；普通守护人 #E6F7FF 浅底 + #91D5FF 描边 + #1890FF 文字
 * - 3 个筛选器：仅看主守护人 / 仅看普通守护人 / 仅看付费
 * - 卡片底部"详情"按钮 → 打开只读详情抽屉（6 分区）
 * - 旧 Table 实现保留为 page.legacy.tsx 作为回滚兜底
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  Avatar, Tag, Space, Typography, message, Button, Input, Drawer, Segmented,
  Progress, Empty, Spin, Descriptions, Popconfirm,
} from 'antd';
import {
  EyeOutlined, ReloadOutlined, SearchOutlined, UserOutlined,
  CrownFilled, TeamOutlined, FireOutlined,
} from '@ant-design/icons';
import { get, del } from '@/lib/api';
import dayjs from 'dayjs';

const { Text } = Typography;

const COLOR = {
  primary: '#1890FF',
  primaryDark: '#096DD9',
  primaryLight: '#69C0FF',
  primaryBg: '#E6F7FF',
  pageBg: '#F0F8FF',
  success: '#52C41A',
  warning: '#FAAD14',
  danger: '#FF4D4F',
  gray: '#8C8C8C',
};

interface GuardianRow {
  id: number;
  manager_user_id: number;
  manager_nickname?: string;
  manager_phone?: string;
  manager_avatar?: string;
  managed_user_id: number;
  managed_user_nickname?: string;
  managed_user_phone?: string;
  managed_user_avatar?: string;
  relation_label?: string;
  role: 'primary' | 'normal';
  role_label?: string;
  priority: number;
  membership_level: 'normal' | 'health' | 'premium';
  membership_level_label?: string;
  plan_name?: string;
  is_paid_member: boolean;
  emergency_quota_total: number;
  emergency_quota_used: number;
  emergency_quota_remaining: number;
  ai_call_quota_total: number;
  ai_call_quota_used: number;
  ai_call_quota_remaining: number;
  status: string;
  created_at?: string;
  cancelled_at?: string | null;
}

interface Stats {
  total: number;
  primary: number;
  normal: number;
  paid: number;
}

function PageHero({ title, subtitle, statItems }: {
  title: string;
  subtitle: string;
  statItems: { label: string; value: number | string }[];
}) {
  return (
    <div
      style={{
        height: 120,
        background: `linear-gradient(135deg, ${COLOR.primary} 0%, ${COLOR.primaryDark} 100%)`,
        borderRadius: 20,
        padding: '20px 28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 4px 16px rgba(24, 144, 255, 0.18)',
        marginBottom: 24,
        color: '#fff',
      }}
    >
      <div>
        <div style={{ fontSize: 22, fontWeight: 700, lineHeight: 1.3 }}>{title}</div>
        <div style={{ fontSize: 14, color: 'rgba(255,255,255,0.7)', marginTop: 4 }}>{subtitle}</div>
      </div>
      <Space size={12} wrap>
        {statItems.map((it) => (
          <div
            key={it.label}
            style={{
              background: 'rgba(255,255,255,0.18)', borderRadius: 12,
              padding: '8px 18px', minWidth: 80, textAlign: 'center',
              backdropFilter: 'blur(4px)',
            }}
          >
            <div style={{ fontSize: 24, fontWeight: 700, lineHeight: 1.1 }}>{it.value}</div>
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.9)', marginTop: 2 }}>{it.label}</div>
          </div>
        ))}
      </Space>
    </div>
  );
}

function RoleBadge({ role, roleLabel }: { role: 'primary' | 'normal'; roleLabel?: string }) {
  if (role === 'primary') {
    return (
      <Tag
        style={{
          margin: 0,
          padding: '2px 10px',
          background: COLOR.primary,
          color: '#fff',
          border: 'none',
          borderRadius: 12,
          fontWeight: 600,
        }}
      >
        <CrownFilled style={{ marginRight: 4 }} />{roleLabel || '主守护人'}
      </Tag>
    );
  }
  return (
    <Tag
      style={{
        margin: 0,
        padding: '2px 10px',
        background: COLOR.primaryBg,
        color: COLOR.primary,
        border: `1px solid #91D5FF`,
        borderRadius: 12,
      }}
    >
      {roleLabel || '普通守护人'}
    </Tag>
  );
}

function MembershipBadge({ level, label }: { level: 'normal' | 'health' | 'premium'; label?: string }) {
  const cfg = level === 'premium'
    ? { bg: '#FFF7E6', color: '#FA8C16', border: '#FFD591' }
    : level === 'health'
    ? { bg: '#E6FFFB', color: '#13C2C2', border: '#87E8DE' }
    : { bg: '#F5F5F5', color: '#595959', border: '#D9D9D9' };
  return (
    <Tag style={{ margin: 0, background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}`, borderRadius: 10 }}>
      {label || (level === 'premium' ? '尊享会员' : level === 'health' ? '健康会员' : '免费会员')}
    </Tag>
  );
}

function QuotaProgress({
  label, total, used, remaining,
}: {
  label: string; total: number; used: number; remaining: number;
}) {
  // 不限额
  if (total < 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ flex: 1, fontSize: 12, color: '#4B5563' }}>{label}</div>
        <div style={{ flex: 2 }}>
          <Progress percent={0} showInfo={false} strokeColor={COLOR.primary} size='small' />
        </div>
        <div style={{ minWidth: 60, textAlign: 'right', fontSize: 12, color: COLOR.primary, fontWeight: 600 }}>
          不限
        </div>
      </div>
    );
  }
  const percent = total > 0 ? Math.min(100, Math.round((used / total) * 100)) : 0;
  let color = COLOR.primary;
  if (remaining === 0) color = COLOR.danger;
  else if (remaining <= 2) color = COLOR.warning;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, fontSize: 12, color: '#4B5563', minWidth: 80 }}>{label}</div>
      <div style={{ flex: 2 }}>
        <Progress percent={percent} showInfo={false} strokeColor={color} size='small' />
      </div>
      <div style={{ minWidth: 60, textAlign: 'right', fontSize: 12, color, fontWeight: 600 }}>
        {remaining} / {total}
      </div>
    </div>
  );
}

function GuardianCard({
  data, onDetail, onCancel,
}: {
  data: GuardianRow;
  onDetail: (rec: GuardianRow) => void;
  onCancel: (rec: GuardianRow) => void;
}) {
  const [hover, setHover] = useState(false);
  return (
    <div
      style={{
        background: '#FFFFFF',
        borderRadius: 20,
        padding: 20,
        boxShadow: hover ? '0 6px 20px rgba(24, 144, 255, 0.16)' : '0 4px 16px rgba(24, 144, 255, 0.08)',
        transform: hover ? 'translateY(-2px)' : 'none',
        transition: 'all 0.2s ease',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        height: '100%',
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {/* 顶部分区：头像 + 姓名 + 角色徽章 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Avatar
          size={48}
          src={data.managed_user_avatar || undefined}
          icon={<UserOutlined />}
          style={{ background: COLOR.primaryLight, flexShrink: 0 }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Text strong style={{ fontSize: 16, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {data.managed_user_nickname || '未命名'}
            </Text>
            <RoleBadge role={data.role} roleLabel={data.role_label} />
          </div>
          <div style={{ fontSize: 12, color: COLOR.gray }}>
            关系：{data.relation_label || '—'}
            <span style={{ marginLeft: 8 }}>守护人：{data.manager_nickname || '—'}</span>
          </div>
        </div>
      </div>

      <div style={{ borderTop: '1px dashed #E5E7EB' }} />

      {/* 中部分区：会员等级 / 优先级 / 守护开始 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 13 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Text type='secondary' style={{ fontSize: 12 }}>会员：</Text>
          <MembershipBadge level={data.membership_level} label={data.membership_level_label} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Text type='secondary' style={{ fontSize: 12 }}>优先级：</Text>
          <Text strong style={{ color: COLOR.primary }}>{data.priority} 顺位</Text>
        </div>
        <div style={{ gridColumn: '1 / span 2', fontSize: 12, color: COLOR.gray }}>
          守护开始：{data.created_at ? dayjs(data.created_at).format('YYYY-MM-DD') : '—'}
        </div>
      </div>

      <div style={{ borderTop: '1px dashed #E5E7EB' }} />

      {/* 底部分区：双进度条 + 详情按钮 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <QuotaProgress
          label='紧急 AI 呼叫'
          total={data.emergency_quota_total}
          used={data.emergency_quota_used}
          remaining={data.emergency_quota_remaining}
        />
        <QuotaProgress
          label='AI 外呼额度'
          total={data.ai_call_quota_total}
          used={data.ai_call_quota_used}
          remaining={data.ai_call_quota_remaining}
        />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginTop: 'auto' }}>
        {data.status === 'active' ? (
          <Popconfirm
            title='确定解除该守护关系？'
            description='解除后双方将无法再相互查看健康档案'
            onConfirm={() => onCancel(data)}
            okButtonProps={{ danger: true }}
          >
            <Button danger size='small' style={{ borderRadius: 22 }}>解除</Button>
          </Popconfirm>
        ) : (
          <Tag color='default'>已取消</Tag>
        )}
        <Button
          type='primary'
          icon={<EyeOutlined />}
          size='small'
          onClick={() => onDetail(data)}
          style={{ borderRadius: 22, background: COLOR.primary, borderColor: COLOR.primary }}
        >
          详情
        </Button>
      </div>
    </div>
  );
}

// ─────────── 只读详情抽屉（6 分区） ───────────

interface DetailData {
  basic_info: any;
  membership_quota: any;
  proxy_pay_info: any;
  associated_guardians: any[];
  last_emergency_call: any;
  last_ai_call: any;
}

function SectionTitle({ icon, text }: { icon: string; text: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '12px 0 8px', borderBottom: `2px solid ${COLOR.primaryBg}`,
      marginBottom: 12,
    }}>
      <span style={{ fontSize: 18 }}>{icon}</span>
      <Text strong style={{ fontSize: 15, color: COLOR.primary }}>{text}</Text>
    </div>
  );
}

function DetailDrawer({
  open, onClose, mgmtId,
}: {
  open: boolean; onClose: () => void; mgmtId: number | null;
}) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<DetailData | null>(null);

  const fetchDetail = useCallback(async () => {
    if (!mgmtId) return;
    setLoading(true);
    try {
      const res: any = await get(`/api/admin/family-management/${mgmtId}/detail`);
      setData(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载详情失败');
    } finally {
      setLoading(false);
    }
  }, [mgmtId]);

  useEffect(() => {
    if (open && mgmtId) {
      fetchDetail();
    } else {
      setData(null);
    }
  }, [open, mgmtId, fetchDetail]);

  return (
    <Drawer
      title='守护关系详情（只读）'
      open={open}
      onClose={onClose}
      width={560}
      destroyOnClose
    >
      <Spin spinning={loading}>
        {!data ? <Empty description='暂无数据' /> : (
          <>
            <SectionTitle icon='👤' text='1. 基本信息' />
            <Descriptions column={2} size='small' bordered>
              <Descriptions.Item label='被守护人' span={1}>
                {data.basic_info.managed_user_nickname || '—'}
              </Descriptions.Item>
              <Descriptions.Item label='关系称呼' span={1}>
                {data.basic_info.relation_label || '—'}
              </Descriptions.Item>
              <Descriptions.Item label='性别' span={1}>
                {data.basic_info.managed_member_gender || '—'}
              </Descriptions.Item>
              <Descriptions.Item label='出生日期' span={1}>
                {data.basic_info.managed_member_birthday || '—'}
              </Descriptions.Item>
              <Descriptions.Item label='我的角色' span={1}>
                <RoleBadge role={data.basic_info.role} roleLabel={data.basic_info.role_label} />
              </Descriptions.Item>
              <Descriptions.Item label='优先级' span={1}>
                {data.basic_info.priority} 顺位
              </Descriptions.Item>
              <Descriptions.Item label='守护开始时间' span={2}>
                {data.basic_info.created_at ? dayjs(data.basic_info.created_at).format('YYYY-MM-DD HH:mm:ss') : '—'}
              </Descriptions.Item>
            </Descriptions>

            <SectionTitle icon='💎' text='2. 会员与配额' />
            <Descriptions column={2} size='small' bordered>
              <Descriptions.Item label='套餐名称' span={1}>
                {data.membership_quota.plan_name || '免费会员'}
              </Descriptions.Item>
              <Descriptions.Item label='会员等级' span={1}>
                <MembershipBadge level={data.membership_quota.membership_level} label={data.membership_quota.membership_level_label} />
              </Descriptions.Item>
              <Descriptions.Item label='套餐到期' span={2}>
                {data.membership_quota.plan_expire_at ? dayjs(data.membership_quota.plan_expire_at).format('YYYY-MM-DD') : '—'}
              </Descriptions.Item>
              <Descriptions.Item label='本月紧急 AI 呼叫' span={2}>
                总额 {data.membership_quota.emergency_quota_total < 0 ? '不限' : data.membership_quota.emergency_quota_total}
                {' / '}已用 {data.membership_quota.emergency_quota_used}
                {' / '}剩余 <Text strong style={{ color: COLOR.primary }}>
                  {data.membership_quota.emergency_quota_remaining < 0 ? '不限' : data.membership_quota.emergency_quota_remaining}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label='本月 AI 外呼' span={2}>
                总额 {data.membership_quota.ai_call_quota_total < 0 ? '不限' : data.membership_quota.ai_call_quota_total}
                {' / '}已用 {data.membership_quota.ai_call_quota_used}
                {' / '}剩余 <Text strong style={{ color: COLOR.primary }}>
                  {data.membership_quota.ai_call_quota_remaining < 0 ? '不限' : data.membership_quota.ai_call_quota_remaining}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label='家庭守护成员配额（含本人）' span={2}>
                {/* [PRD-HEALTH-ARCHIVE-MGR-V1 2026-05-29] 资产/配额语境：「已守护 X / 总上限 Y」→「已管理 X 份家人档案 / 配额 Y 份」（字段名不变） */}
                已管理 <Text strong>{data.membership_quota.max_managed_used}</Text> 份家人档案
                {' / '}配额 {data.membership_quota.max_managed_total} 份
              </Descriptions.Item>
            </Descriptions>

            <SectionTitle icon='💰' text='3. 代付开关状态' />
            <Descriptions column={1} size='small' bordered>
              <Descriptions.Item label='主守护人'>
                {data.proxy_pay_info.primary_guardian_nickname || '—'}
              </Descriptions.Item>
              <Descriptions.Item label='代付开关'>
                {data.proxy_pay_info.enabled ? (
                  <Tag color='green'>已开启</Tag>
                ) : (
                  <Tag>未开启</Tag>
                )}
              </Descriptions.Item>
              {data.proxy_pay_info.enabled && (
                <Descriptions.Item label='开启时间'>
                  {data.proxy_pay_info.enabled_at ? dayjs(data.proxy_pay_info.enabled_at).format('YYYY-MM-DD HH:mm:ss') : '—'}
                </Descriptions.Item>
              )}
            </Descriptions>

            <SectionTitle icon='👥' text='4. 关联守护人列表' />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {data.associated_guardians.length === 0 ? (
                <Empty description='暂无' />
              ) : data.associated_guardians.map((g: any) => (
                <div key={g.management_id}
                  style={{
                    border: g.is_current ? `2px solid ${COLOR.primary}` : '1px solid #E5E7EB',
                    background: g.is_current ? COLOR.primaryBg : '#FAFAFA',
                    borderRadius: 12,
                    padding: 12,
                    display: 'flex', alignItems: 'center', gap: 12,
                  }}
                >
                  <Avatar src={g.manager_avatar || undefined} icon={<UserOutlined />} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Text strong>{g.manager_nickname || '—'}</Text>
                      <RoleBadge role={g.role} roleLabel={g.role_label} />
                      <MembershipBadge level={g.membership_level} label={g.membership_level_label} />
                      {g.is_current && <Tag color={COLOR.primary} style={{ borderRadius: 10 }}>当前</Tag>}
                    </div>
                    <div style={{ fontSize: 12, color: COLOR.gray, marginTop: 4 }}>
                      {g.manager_phone_masked || '—'} · 关系：{g.relation_label || '—'} · 优先级：{g.priority}
                    </div>
                    <div style={{ fontSize: 12, color: COLOR.gray }}>
                      守护开始：{g.created_at ? dayjs(g.created_at).format('YYYY-MM-DD') : '—'}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <SectionTitle icon='🆘' text='5. 最近一次紧急 AI 呼叫' />
            {data.last_emergency_call ? (
              <Descriptions column={2} size='small' bordered>
                <Descriptions.Item label='触发时间' span={2}>
                  {dayjs(data.last_emergency_call.used_at).format('YYYY-MM-DD HH:mm:ss')}
                </Descriptions.Item>
                <Descriptions.Item label='触发源' span={1}>
                  {data.last_emergency_call.source_name}
                </Descriptions.Item>
                <Descriptions.Item label='扣额度' span={1}>
                  {data.last_emergency_call.charged_count} 次
                </Descriptions.Item>
                <Descriptions.Item label='扣谁的额度' span={2}>
                  {data.last_emergency_call.charged_user_nickname || '—'}
                </Descriptions.Item>
              </Descriptions>
            ) : <Empty description='暂无紧急呼叫记录' />}

            <SectionTitle icon='📞' text='6. 最近一次 AI 外呼' />
            {data.last_ai_call ? (
              <Descriptions column={2} size='small' bordered>
                <Descriptions.Item label='提醒名称' span={2}>
                  {data.last_ai_call.title}
                </Descriptions.Item>
                <Descriptions.Item label='设置者' span={1}>
                  {data.last_ai_call.setter_nickname || '—'}
                </Descriptions.Item>
                <Descriptions.Item label='下次执行' span={1}>
                  {data.last_ai_call.next_fire_at ? dayjs(data.last_ai_call.next_fire_at).format('YYYY-MM-DD HH:mm') : '—'}
                </Descriptions.Item>
                <Descriptions.Item label='设置时间' span={2}>
                  {dayjs(data.last_ai_call.created_at).format('YYYY-MM-DD HH:mm:ss')}
                </Descriptions.Item>
                <Descriptions.Item label='扣谁的额度' span={2}>
                  {data.last_ai_call.charged_user_nickname || '—'}
                  {data.last_ai_call.is_proxy_paid && (
                    <Tag color='gold' style={{ marginLeft: 8, borderRadius: 10 }}>代付</Tag>
                  )}
                </Descriptions.Item>
              </Descriptions>
            ) : <Empty description='暂无 AI 外呼记录' />}
          </>
        )}
      </Spin>
    </Drawer>
  );
}

// ─────────── 主页面 ───────────

export default function FamilyManagementPage() {
  const [data, setData] = useState<GuardianRow[]>([]);
  const [stats, setStats] = useState<Stats>({ total: 0, primary: 0, normal: 0, paid: 0 });
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [roleFilter, setRoleFilter] = useState<'all' | 'primary' | 'normal'>('all');
  const [paidFilter, setPaidFilter] = useState<'all' | 'paid' | 'free'>('all');
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailMgmtId, setDetailMgmtId] = useState<number | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { page: 1, page_size: 200 };
      if (keyword) params.keyword = keyword;
      if (roleFilter !== 'all') params.role_filter = roleFilter;
      if (paidFilter !== 'all') params.is_paid = paidFilter === 'paid';
      const res: any = await get('/api/admin/family-management', params);
      setData(res?.items || []);
      setStats(res?.stats || { total: 0, primary: 0, normal: 0, paid: 0 });
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [keyword, roleFilter, paidFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleDetail = (rec: GuardianRow) => {
    setDetailMgmtId(rec.id);
    setDetailOpen(true);
  };

  const handleCancel = async (rec: GuardianRow) => {
    try {
      await del(`/api/admin/family-management/${rec.id}`);
      message.success('已解除');
      fetchData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '操作失败');
    }
  };

  return (
    <div style={{ background: COLOR.pageBg, minHeight: 'calc(100vh - 112px)', margin: -24, padding: 24 }}>
      <PageHero
        title='守护关系管理'
        subtitle='管理用户之间的主守护人 / 普通守护人关系，可查看双配额、付费状态与详情'
        statItems={[
          { label: '总关系', value: stats.total },
          { label: '主守护人', value: stats.primary },
          { label: '普通守护人', value: stats.normal },
          { label: '付费会员', value: stats.paid },
        ]}
      />

      {/* 筛选栏 */}
      <div style={{
        background: '#fff', borderRadius: 20, padding: 16, marginBottom: 20,
        boxShadow: '0 4px 16px rgba(24, 144, 255, 0.06)',
        display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', justifyContent: 'space-between',
      }}>
        <Space size={12} wrap>
          <Input.Search
            placeholder='搜索昵称 / 手机号'
            allowClear
            enterButton={<><SearchOutlined /> 搜索</>}
            style={{ width: 260 }}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onSearch={() => fetchData()}
          />
          <Segmented
            value={roleFilter}
            onChange={(v) => setRoleFilter(v as any)}
            options={[
              { label: '全部', value: 'all' },
              { label: '仅看主守护人', value: 'primary', icon: <CrownFilled /> },
              { label: '仅看普通守护人', value: 'normal', icon: <TeamOutlined /> },
            ]}
          />
          <Segmented
            value={paidFilter}
            onChange={(v) => setPaidFilter(v as any)}
            options={[
              { label: '全部', value: 'all' },
              { label: '仅看付费', value: 'paid', icon: <FireOutlined /> },
              { label: '仅看免费', value: 'free' },
            ]}
          />
        </Space>
        <Button icon={<ReloadOutlined />} onClick={fetchData} style={{ borderRadius: 22 }}>
          刷新
        </Button>
      </div>

      <Spin spinning={loading}>
        {data.length === 0 ? (
          <div style={{ background: '#fff', borderRadius: 20, padding: 60 }}>
            <Empty description='暂无守护关系' />
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gap: 16,
              gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            }}
          >
            {data.map((rec) => (
              <GuardianCard
                key={rec.id}
                data={rec}
                onDetail={handleDetail}
                onCancel={handleCancel}
              />
            ))}
          </div>
        )}
      </Spin>

      <DetailDrawer
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        mgmtId={detailMgmtId}
      />
    </div>
  );
}
