'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { TreeSelect, Tag, Space, Spin } from 'antd';
import { get } from '@/lib/api';

export interface CategoryNode {
  id: number;
  name: string;
  parent_id: number | null;
  level: number;
  children?: CategoryNode[];
}

interface Props {
  value?: number[];
  onChange?: (ids: number[]) => void;
  /** 编辑回填时，可能含已删除/隐藏的旧分类 ID（红色 Tag 提示） */
  fallbackMissing?: Array<{ id: number; missing?: boolean }>;
}

/**
 * F3：分类树形选择器
 * - antd TreeSelect 多选 + 搜索
 * - 勾父类自动包含子类（treeCheckable + showCheckedStrategy=SHOW_PARENT）
 * - 已选分类以蓝色 Tag 形式在控件下方展示
 * - 数据落地只保存"用户实际勾选的最上层分类 ID"
 */
export default function CategoryTreePicker({ value, onChange, fallbackMissing }: Props) {
  const [tree, setTree] = useState<CategoryNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [namesById, setNamesById] = useState<Record<number, string>>({});

  useEffect(() => {
    setLoading(true);
    get('/api/admin/coupons/category-tree')
      .then((res: any) => {
        const items = res?.items || [];
        setTree(items);
        const map: Record<number, string> = {};
        const walk = (nodes: CategoryNode[]) => {
          nodes.forEach(n => {
            map[n.id] = n.name;
            if (n.children?.length) walk(n.children);
          });
        };
        walk(items);
        setNamesById(map);
      })
      .finally(() => setLoading(false));
  }, []);

  // 编辑回填：通过 categories-by-ids 拉取真实名称（包含 missing）
  useEffect(() => {
    if (!value || value.length === 0) return;
    const missing = value.filter(v => !namesById[v]);
    if (missing.length === 0) return;
    get(`/api/admin/coupons/categories-by-ids?ids=${missing.join(',')}`)
      .then((res: any) => {
        const arr = res?.items || [];
        setNamesById(prev => {
          const next = { ...prev };
          arr.forEach((it: any) => {
            if (it.name) next[it.id] = it.name;
            else next[it.id] = `❌ 分类已不存在(ID:${it.id})`;
          });
          return next;
        });
      })
      .catch(() => {});
  }, [value, namesById]);

  // 把后端 tree 转 antd TreeSelect treeData
  const treeData = useMemo(() => {
    const conv = (nodes: CategoryNode[]): any[] =>
      nodes.map(n => ({
        title: n.name,
        value: n.id,
        key: n.id,
        children: n.children?.length ? conv(n.children) : undefined,
      }));
    return conv(tree);
  }, [tree]);

  const ids = value || [];

  const handleRemove = (id: number) => {
    const next = ids.filter(v => v !== id);
    onChange?.(next);
  };

  return (
    <div>
      <Spin spinning={loading} size="small">
        <TreeSelect
          treeData={treeData}
          value={ids}
          onChange={(v) => onChange?.(Array.isArray(v) ? v : [])}
          multiple
          treeCheckable
          showCheckedStrategy={TreeSelect.SHOW_PARENT}
          placeholder="请选择分类（可搜索 / 勾父类自动包含子类）"
          treeNodeFilterProp="title"
          allowClear
          maxTagCount="responsive"
          style={{ width: '100%' }}
          dropdownStyle={{ maxHeight: 480, overflow: 'auto' }}
        />
      </Spin>
      {ids.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <Space size={[4, 6]} wrap>
            {ids.map(id => {
              const name = namesById[id];
              const isMissing = !name || name.startsWith('❌');
              return (
                <Tag
                  key={id}
                  color={isMissing ? 'red' : 'blue'}
                  closable
                  onClose={() => handleRemove(id)}
                >
                  {name || `分类#${id}`}
                </Tag>
              );
            })}
          </Space>
        </div>
      )}
    </div>
  );
}
