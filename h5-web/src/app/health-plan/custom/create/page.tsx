'use client';

import { Suspense, useState, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { NavBar, Form, Input, Button, Toast, TextArea, Stepper, Switch, SpinLoading } from 'antd-mobile';
import { AddOutline, CloseOutline } from 'antd-mobile-icons';
import api from '@/lib/api';

interface TaskItem {
  tempId: string;
  name: string;
}

export default function CreateCustomPlanPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50 flex items-center justify-center"><SpinLoading color="primary" /></div>}>
      <CreateCustomPlanContent />
    </Suspense>
  );
}

function CreateCustomPlanContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const editId = searchParams.get('editId');
  const isEdit = !!editId;

  const [fetching, setFetching] = useState(isEdit);
  const [submitting, setSubmitting] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isInfinite, setIsInfinite] = useState(false);
  const [durationDays, setDurationDays] = useState(30);
  const [tasks, setTasks] = useState<TaskItem[]>([
    { tempId: '1', name: '' },
  ]);

  const fetchPlanDetail = useCallback(async () => {
    if (!editId) return;
    try {
      const res: any = await api.get(`/api/health-plan/user-plans/${editId}`);
      const data = res.data || res;
      setName(data.plan_name || '');
      setDescription(data.description || '');
      if (data.duration_days == null) {
        setIsInfinite(true);
      } else {
        setIsInfinite(false);
        setDurationDays(data.duration_days);
      }
      if (data.tasks && data.tasks.length > 0) {
        setTasks(data.tasks.map((t: any, idx: number) => ({
          tempId: String(t.id || idx),
          name: t.task_name || t.name || '',
        })));
      }
    } catch {
      Toast.show({ content: '加载计划详情失败', icon: 'fail' });
    } finally {
      setFetching(false);
    }
  }, [editId]);

  useEffect(() => {
    if (isEdit) fetchPlanDetail();
  }, [isEdit, fetchPlanDetail]);

  const addTask = () => {
    setTasks([...tasks, { tempId: String(Date.now()), name: '' }]);
  };

  const removeTask = (tempId: string) => {
    if (tasks.length <= 1) {
      Toast.show({ content: '至少保留一个任务', icon: 'fail' });
      return;
    }
    setTasks(tasks.filter((t) => t.tempId !== tempId));
  };

  const updateTask = (tempId: string, field: keyof TaskItem, value: string) => {
    setTasks(tasks.map((t) => (t.tempId === tempId ? { ...t, [field]: value } : t)));
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      Toast.show({ content: '请输入计划名称', icon: 'fail' });
      return;
    }
    const validTasks = tasks.filter((t) => t.name.trim());
    if (validTasks.length === 0) {
      Toast.show({ content: '请至少添加一个任务', icon: 'fail' });
      return;
    }

    setSubmitting(true);
    try {
      if (isEdit) {
        await api.put(`/api/health-plan/user-plans/${editId}`, {
          plan_name: name.trim(),
          description: description.trim(),
          duration_days: isInfinite ? null : durationDays,
        });
        Toast.show({ content: '更新成功', icon: 'success' });
      } else {
        await api.post('/api/health-plan/user-plans', {
          plan_name: name.trim(),
          description: description.trim(),
          duration_days: isInfinite ? null : durationDays,
          tasks: validTasks.map((t, idx) => ({
            task_name: t.name.trim(),
            sort_order: idx,
          })),
        });
        Toast.show({ content: '创建成功', icon: 'success' });
      }
      router.back();
    } catch {
      Toast.show({ content: isEdit ? '更新失败' : '创建失败', icon: 'fail' });
    } finally {
      setSubmitting(false);
    }
  };

  if (fetching) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>编辑计划</NavBar>
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 45px)' }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>{isEdit ? '编辑计划' : '创建计划'}</NavBar>

      <div className="px-4 pt-4">
        <div className="card">
          <div className="section-title">基本信息</div>
          <Form layout="vertical">
            <Form.Item label="计划名称" required>
              <Input
                placeholder="给你的计划取个名字"
                value={name}
                onChange={setName}
                clearable
              />
            </Form.Item>
            <Form.Item label="描述">
              <TextArea
                placeholder="描述一下你的计划目标"
                value={description}
                onChange={setDescription}
                rows={2}
                maxLength={200}
                showCount
              />
            </Form.Item>
            <Form.Item label="计划周期">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600">无限期</span>
                  <Switch
                    checked={isInfinite}
                    onChange={setIsInfinite}
                    style={{ '--checked-color': '#52c41a' } as React.CSSProperties}
                  />
                </div>
                {!isInfinite && (
                  <div className="flex items-center gap-2">
                    <Stepper
                      min={1}
                      max={365}
                      value={durationDays}
                      onChange={(val) => setDurationDays(val as number)}
                      style={{ '--button-background-color': '#52c41a15' } as React.CSSProperties}
                    />
                    <span className="text-sm text-gray-500">天</span>
                  </div>
                )}
              </div>
            </Form.Item>
          </Form>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <div className="section-title mb-0">每日任务</div>
            <Button
              size="mini"
              onClick={addTask}
              style={{ borderRadius: 8, color: '#52c41a', borderColor: '#52c41a' }}
            >
              <AddOutline /> 添加
            </Button>
          </div>

          {tasks.map((task, idx) => (
            <div
              key={task.tempId}
              className="p-3 rounded-xl mb-3"
              style={{ background: '#f9f9f9', border: '1px solid #f0f0f0' }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-400 font-medium">任务 {idx + 1}</span>
                <CloseOutline
                  className="text-gray-400 cursor-pointer"
                  fontSize={16}
                  onClick={() => removeTask(task.tempId)}
                />
              </div>
              <Input
                placeholder="任务名称（必填）"
                value={task.name}
                onChange={(val) => updateTask(task.tempId, 'name', val)}
                style={{ '--font-size': '14px' } as React.CSSProperties}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="fixed bottom-0 left-0 right-0 p-4 bg-white" style={{ maxWidth: 750, margin: '0 auto', boxShadow: '0 -2px 8px rgba(0,0,0,0.06)', paddingBottom: 'calc(16px + env(safe-area-inset-bottom))' }}>
        <Button
          block
          color="primary"
          size="large"
          loading={submitting}
          style={{ borderRadius: 12, background: 'linear-gradient(135deg, #52c41a, #13c2c2)', border: 'none', height: 48 }}
          onClick={handleSubmit}
        >
          {isEdit ? '保存修改' : '创建计划'}
        </Button>
      </div>
    </div>
  );
}
