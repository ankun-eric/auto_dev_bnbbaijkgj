'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Tag, Switch, Modal, Form, Input, Select, InputNumber,
  Radio, Typography, message, Popconfirm, Image, Upload,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ArrowUpOutlined, ArrowDownOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { get, post, put, del, upload } from '@/lib/api';

const EMOJI_KEYWORD_MAP: { keywords: string[]; emojis: string[] }[] = [
  { keywords: ['体检', '检查', '检测', '化验'], emojis: ['🏥', '🩺', '💊', '🔬', '📋'] },
  { keywords: ['运动', '健身', '锻炼', '跑步'], emojis: ['🏃', '💪', '🧘', '🚴', '🏋️'] },
  { keywords: ['饮食', '营养', '食谱'], emojis: ['🥗', '🍎', '🥦', '🍽️', '🥕'] },
  { keywords: ['心理', '情绪', '压力', '心情'], emojis: ['🧠', '😊', '💆', '🌿', '❤️'] },
  { keywords: ['睡眠', '休息', '失眠'], emojis: ['😴', '🌙', '🛌', '💤', '⭐'] },
  { keywords: ['家庭', '亲子', '家人', '宝宝'], emojis: ['👨‍👩‍👧', '👶', '🏠', '❤️', '🌸'] },
  { keywords: ['预约', '挂号', '就诊', '看诊'], emojis: ['📅', '🗓️', '📞', '🏨', '✅'] },
  { keywords: ['报告', '记录', '档案', '数据'], emojis: ['📊', '📈', '📋', '🗂️', '📝'] },
  { keywords: ['购物', '商城', '积分', '会员'], emojis: ['🛒', '🎁', '💳', '⭐', '🏆'] },
  { keywords: ['专家', '医生', '咨询', '问诊'], emojis: ['👨‍⚕️', '🩺', '💬', '🔍', '📱'] },
  { keywords: ['健康', '养生', '保健'], emojis: ['💚', '🌿', '🍃', '✨', '🌟'] },
];

const EMOJI_FALLBACK = ['⭐', '📋', '🔖', '💡', '🎯', '🌟', '✅', '🏷️'];

function getRecommendedEmojis(title: string): string[] {
  if (!title) return EMOJI_FALLBACK.slice(0, 5);
  for (const group of EMOJI_KEYWORD_MAP) {
    if (group.keywords.some((kw) => title.includes(kw))) {
      return group.emojis.slice(0, 5);
    }
  }
  return EMOJI_FALLBACK.slice(0, 5);
}

const { Title } = Typography;

interface HomeMenu {
  id: number;
  name: string;
  icon_type: string;
  icon_content: string;
  link_type: string;
  link_url: string;
  miniprogram_appid?: string;
  sort_order: number;
  is_visible: boolean;
}

export default function HomeMenusPage() {
  const [menus, setMenus] = useState<HomeMenu[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingMenu, setEditingMenu] = useState<HomeMenu | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const [iconType, setIconType] = useState<string>('emoji');
  const [linkType, setLinkType] = useState<string>('internal');
  const [uploading, setUploading] = useState(false);
  const [selectedEmoji, setSelectedEmoji] = useState<string>('');
  const watchedName = Form.useWatch('name', form);

  const fetchMenus = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<HomeMenu[]>('/api/admin/home-menus');
      const data = Array.isArray(res) ? res : (res as any).items || [];
      setMenus(data);
    } catch {
      message.error('获取菜单列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMenus();
  }, [fetchMenus]);

  const handleToggleVisible = async (record: HomeMenu, checked: boolean) => {
    try {
      await put(`/api/admin/home-menus/${record.id}`, { ...record, is_visible: checked });
      message.success('状态更新成功');
      fetchMenus();
    } catch {
      message.error('状态更新失败');
    }
  };

  const handleOpenModal = (record?: HomeMenu) => {
    setEditingMenu(record || null);
    form.resetFields();
    if (record) {
      form.setFieldsValue({
        name: record.name,
        icon_type: record.icon_type || 'emoji',
        icon_content: record.icon_content,
        link_type: record.link_type || 'internal',
        link_url: record.link_url,
        miniprogram_appid: record.miniprogram_appid,
        sort_order: record.sort_order,
        is_visible: record.is_visible,
      });
      setIconType(record.icon_type || 'emoji');
      setLinkType(record.link_type || 'internal');
      setSelectedEmoji(record.icon_type === 'emoji' ? (record.icon_content || '') : '');
    } else {
      form.setFieldsValue({ is_visible: true, sort_order: 0, icon_type: 'emoji', link_type: 'internal' });
      setIconType('emoji');
      setLinkType('internal');
      setSelectedEmoji('');
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      if (editingMenu) {
        await put(`/api/admin/home-menus/${editingMenu.id}`, values);
        message.success('菜单更新成功');
      } else {
        await post('/api/admin/home-menus', values);
        message.success('菜单创建成功');
      }
      setModalOpen(false);
      fetchMenus();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/home-menus/${id}`);
      message.success('菜单删除成功');
      fetchMenus();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const handleMove = async (index: number, direction: 'up' | 'down') => {
    const newMenus = [...menus];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= newMenus.length) return;
    [newMenus[index], newMenus[targetIndex]] = [newMenus[targetIndex], newMenus[index]];
    const sortPayload = newMenus.map((m, i) => ({ id: m.id, sort_order: i }));
    try {
      await put('/api/admin/home-menus/sort', sortPayload);
      message.success('排序更新成功');
      fetchMenus();
    } catch {
      message.error('排序更新失败');
    }
  };

  const handleUploadIcon = async (file: File) => {
    setUploading(true);
    try {
      const res = await upload<{ url: string }>('/api/upload/image', file);
      form.setFieldsValue({ icon_content: res.url });
      message.success('图标上传成功');
    } catch {
      message.error('图标上传失败');
    } finally {
      setUploading(false);
    }
  };

  const linkTypeLabel = (type: string) => {
    const map: Record<string, string> = {
      internal: '内部页面',
      external: '外部链接',
      miniprogram: '小程序',
      none: '无跳转',
    };
    return map[type] || type;
  };

  const linkTypeColor = (type: string) => {
    const map: Record<string, string> = {
      internal: 'blue',
      external: 'green',
      miniprogram: 'purple',
      none: 'default',
    };
    return map[type] || 'default';
  };

  const columns = [
    {
      title: '排序',
      dataIndex: 'sort_order',
      key: 'sort_order',
      width: 120,
      render: (_: any, __: HomeMenu, index: number) => (
        <Space>
          <Button
            type="text"
            size="small"
            icon={<ArrowUpOutlined />}
            disabled={index === 0}
            onClick={() => handleMove(index, 'up')}
          />
          <Button
            type="text"
            size="small"
            icon={<ArrowDownOutlined />}
            disabled={index === menus.length - 1}
            onClick={() => handleMove(index, 'down')}
          />
        </Space>
      ),
    },
    {
      title: '图标',
      dataIndex: 'icon_content',
      key: 'icon_content',
      width: 80,
      render: (val: string, record: HomeMenu) => {
        if (record.icon_type === 'image' && val) {
          return <Image src={val} width={32} height={32} style={{ objectFit: 'cover', borderRadius: 4 }} preview={false} />;
        }
        return <span style={{ fontSize: 24 }}>{val}</span>;
      },
    },
    { title: '菜单名称', dataIndex: 'name', key: 'name', width: 140 },
    {
      title: '跳转类型',
      dataIndex: 'link_type',
      key: 'link_type',
      width: 120,
      render: (val: string) => <Tag color={linkTypeColor(val)}>{linkTypeLabel(val)}</Tag>,
    },
    {
      title: '跳转地址',
      dataIndex: 'link_url',
      key: 'link_url',
      ellipsis: true,
      render: (val: string) => val || '-',
    },
    {
      title: '显示状态',
      dataIndex: 'is_visible',
      key: 'is_visible',
      width: 100,
      render: (val: boolean, record: HomeMenu) => (
        <Switch checked={val} onChange={(checked) => handleToggleVisible(record, checked)} />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, record: HomeMenu) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除此菜单？" onConfirm={() => handleDelete(record.id)} okText="确定" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>首页菜单管理</Title>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>
          新增菜单
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={menus}
        rowKey="id"
        loading={loading}
        pagination={false}
        scroll={{ x: 800 }}
      />
      <Modal
        title={editingMenu ? '编辑菜单' : '新增菜单'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical" initialValues={{ is_visible: true, sort_order: 0, icon_type: 'emoji', link_type: 'internal' }}>
          <Form.Item label="菜单名称" name="name" rules={[{ required: true, message: '请输入菜单名称' }]}>
            <Input placeholder="请输入菜单名称" maxLength={10} />
          </Form.Item>
          <Form.Item label="图标类型" name="icon_type" rules={[{ required: true }]}>
            <Radio.Group onChange={(e) => setIconType(e.target.value)}>
              <Radio value="emoji">Emoji</Radio>
              <Radio value="image">图片</Radio>
            </Radio.Group>
          </Form.Item>
          {iconType === 'emoji' ? (
            <>
              {/* Emoji recommendation area */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 13, color: '#666', marginBottom: 8 }}>推荐图标：</div>
                <div
                  style={{
                    background: '#f0f8ff',
                    padding: 12,
                    borderRadius: 8,
                  }}
                >
                  {watchedName ? (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {getRecommendedEmojis(watchedName).map((emoji) => (
                        <button
                          key={emoji}
                          type="button"
                          onClick={() => {
                            setSelectedEmoji(emoji);
                            form.setFieldsValue({ icon_content: emoji });
                          }}
                          style={{
                            fontSize: 22,
                            padding: '4px 8px',
                            border: selectedEmoji === emoji ? '2px solid #52c41a' : '1px solid #d9d9d9',
                            borderRadius: 6,
                            backgroundColor: selectedEmoji === emoji ? '#f6ffed' : '#fff',
                            cursor: 'pointer',
                            lineHeight: 1.4,
                          }}
                        >
                          {emoji}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, opacity: 0.4 }}>
                      {EMOJI_FALLBACK.slice(0, 5).map((emoji) => (
                        <button
                          key={emoji}
                          type="button"
                          disabled
                          style={{
                            fontSize: 22,
                            padding: '4px 8px',
                            border: '1px solid #d9d9d9',
                            borderRadius: 6,
                            backgroundColor: '#fff',
                            cursor: 'not-allowed',
                            lineHeight: 1.4,
                          }}
                        >
                          {emoji}
                        </button>
                      ))}
                      <div style={{ width: '100%', marginTop: 6, fontSize: 12, color: '#999' }}>
                        请先填写菜单名称以获取推荐图标
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Current icon preview */}
              <Form.Item noStyle shouldUpdate={(prev, cur) => prev.icon_content !== cur.icon_content}>
                {() => {
                  const iconContent = form.getFieldValue('icon_content');
                  if (!iconContent) return null;
                  return (
                    <div
                      style={{
                        background: '#f5f5f5',
                        borderRadius: 8,
                        padding: '8px 16px',
                        marginBottom: 8,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                      }}
                    >
                      <span style={{ fontSize: 13, color: '#666' }}>当前图标：</span>
                      <span style={{ fontSize: 32, lineHeight: 1 }}>{iconContent}</span>
                    </div>
                  );
                }}
              </Form.Item>

              <Form.Item label="图标内容" name="icon_content" rules={[{ required: true, message: '请输入Emoji图标' }]}>
                <Input placeholder="请输入Emoji，如 🏠" maxLength={4} />
              </Form.Item>
            </>
          ) : (
            <Form.Item label="图标图片" name="icon_content" rules={[{ required: true, message: '请上传图标图片' }]}>
              <Input
                placeholder="请上传图标图片"
                readOnly
                addonAfter={
                  <Upload
                    showUploadList={false}
                    beforeUpload={(file) => {
                      handleUploadIcon(file);
                      return false;
                    }}
                    accept="image/*"
                  >
                    <Button type="link" size="small" icon={<UploadOutlined />} loading={uploading}>
                      上传
                    </Button>
                  </Upload>
                }
              />
            </Form.Item>
          )}
          <Form.Item label="跳转类型" name="link_type" rules={[{ required: true, message: '请选择跳转类型' }]}>
            <Select
              onChange={(val) => setLinkType(val)}
              options={[
                { label: '内部页面', value: 'internal' },
                { label: '外部链接', value: 'external' },
                { label: '小程序', value: 'miniprogram' },
                { label: '无跳转', value: 'none' },
              ]}
            />
          </Form.Item>
          {linkType !== 'none' && (
            <Form.Item label="跳转地址" name="link_url" rules={[{ required: true, message: '请输入跳转地址' }]}>
              <Input placeholder={linkType === 'external' ? '请输入完整URL' : '请输入页面路径'} />
            </Form.Item>
          )}
          {linkType === 'miniprogram' && (
            <Form.Item label="小程序AppID" name="miniprogram_appid" rules={[{ required: true, message: '请输入小程序AppID' }]}>
              <Input placeholder="请输入小程序AppID" />
            </Form.Item>
          )}
          <Form.Item label="排序值" name="sort_order">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="是否显示" name="is_visible" valuePropName="checked">
            <Switch checkedChildren="显示" unCheckedChildren="隐藏" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
