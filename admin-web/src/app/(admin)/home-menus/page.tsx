'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Table, Button, Space, Tag, Switch, Modal, Form, Input, Select, InputNumber,
  Radio, Typography, message, Popconfirm, Image, Upload,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ArrowUpOutlined, ArrowDownOutlined,
  UploadOutlined, SmileOutlined, CloseCircleOutlined,
} from '@ant-design/icons';
import { get, post, put, del, upload } from '@/lib/api';

// ─── Emoji Keyword Mapping (40+ groups) ───────────────────────────────────────

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
  { keywords: ['健康', '保健'], emojis: ['💚', '🌿', '🍃', '✨', '🌟'] },
  { keywords: ['中医', '针灸', '推拿', '艾灸', '拔罐'], emojis: ['🧧', '🍵', '🌿', '🏮', '💊'] },
  { keywords: ['药品', '用药', '处方', '配药', '药房'], emojis: ['💊', '💉', '🧪', '🏪', '📜'] },
  { keywords: ['疫苗', '接种', '免疫', '打针'], emojis: ['💉', '🛡️', '✅', '📋', '🏥'] },
  { keywords: ['保险', '医保', '社保', '理赔'], emojis: ['🛡️', '💳', '📄', '🏦', '✅'] },
  { keywords: ['社区', '居家', '养老', '护理', '照护'], emojis: ['🏘️', '🏠', '👴', '🤝', '💝'] },
  { keywords: ['慢病', '糖尿病', '高血压', '血糖', '血压'], emojis: ['🩸', '💓', '📊', '⚕️', '🔬'] },
  { keywords: ['急救', '120', '紧急', 'SOS', '急诊'], emojis: ['🚑', '🆘', '⚠️', '📞', '🏥'] },
  { keywords: ['康复', '理疗', '复健', '恢复'], emojis: ['🦽', '💪', '🏃', '🌈', '✨'] },
  { keywords: ['口腔', '牙齿', '洗牙', '补牙', '正畸'], emojis: ['🦷', '😁', '🪥', '✨', '🏥'] },
  { keywords: ['眼科', '视力', '近视', '眼睛', '配镜'], emojis: ['👁️', '👓', '🔍', '💡', '🏥'] },
  { keywords: ['皮肤', '美容', '护肤', '祛痘'], emojis: ['🧴', '✨', '🌸', '💆', '🪞'] },
  { keywords: ['妇科', '产检', '孕期', '月子', '母婴'], emojis: ['🤰', '👶', '🌸', '💗', '🏥'] },
  { keywords: ['男科', '前列腺'], emojis: ['🩺', '💪', '🏥', '⚕️', '🔬'] },
  { keywords: ['儿科', '儿童', '小儿', '宝宝健康'], emojis: ['👶', '🧒', '🍼', '🎈', '🏥'] },
  { keywords: ['养生', '调理', '滋补', '食疗', '膳食'], emojis: ['🍲', '🫖', '🌿', '🍯', '✨'] },
  { keywords: ['减肥', '瘦身', '体重', 'BMI', '塑形'], emojis: ['⚖️', '🏃', '🥗', '📉', '💪'] },
  { keywords: ['心脏', '心血管', '冠心病', '房颤'], emojis: ['❤️', '💓', '🫀', '🩺', '📊'] },
  { keywords: ['呼吸', '哮喘', '肺', '咳嗽', '感冒'], emojis: ['🫁', '😷', '🌬️', '💨', '🤧'] },
  { keywords: ['骨科', '骨折', '关节', '腰椎', '颈椎'], emojis: ['🦴', '🩻', '💆', '🏥', '🦽'] },
  { keywords: ['肿瘤', '癌症', '筛查', '基因'], emojis: ['🔬', '🧬', '🎗️', '🏥', '📋'] },
  { keywords: ['内分泌', '甲状腺', '激素'], emojis: ['🧪', '🔬', '💊', '📊', '🩺'] },
  { keywords: ['消化', '胃', '肠', '便秘', '腹泻'], emojis: ['🫃', '💊', '🥗', '🏥', '📋'] },
  { keywords: ['神经', '头痛', '偏头痛', '癫痫'], emojis: ['🧠', '💆', '⚡', '🩺', '💊'] },
  { keywords: ['过敏', '花粉', '湿疹', '荨麻疹'], emojis: ['🤧', '🌼', '💊', '🩺', '⚠️'] },
  { keywords: ['传染病', '流感', '防疫', '隔离'], emojis: ['😷', '🦠', '🛡️', '🏥', '⚠️'] },
  { keywords: ['签到', '打卡', '每日', '日历'], emojis: ['✅', '📅', '🎯', '⏰', '🌞'] },
  { keywords: ['问卷', '评估', '测评', '量表', '自测'], emojis: ['📝', '📊', '✍️', '🎯', '📋'] },
  { keywords: ['课程', '学习', '教育', '科普', '知识'], emojis: ['📚', '🎓', '💡', '📖', '🧑‍🏫'] },
  { keywords: ['活动', '任务', '挑战', '计划'], emojis: ['🎯', '🏆', '📌', '🗓️', '🚀'] },
  { keywords: ['客服', '帮助', '反馈', '投诉', '建议'], emojis: ['💬', '📞', '🙋', '📮', '🤝'] },
  { keywords: ['设置', '个人', '账号', '隐私', '安全'], emojis: ['⚙️', '👤', '🔒', '🛠️', '📱'] },
  { keywords: ['地图', '导航', '附近', '位置', '门店'], emojis: ['📍', '🗺️', '🧭', '🏪', '📌'] },
  { keywords: ['优惠', '促销', '折扣', '红包', '券'], emojis: ['🎉', '🧧', '💰', '🎁', '🏷️'] },
  { keywords: ['收藏', '关注', '点赞', '喜欢'], emojis: ['❤️', '⭐', '🔖', '👍', '💖'] },
  { keywords: ['通知', '消息', '提醒', '公告'], emojis: ['🔔', '📢', '💌', '📣', '📬'] },
  { keywords: ['扫码', '二维码', '扫一扫'], emojis: ['📷', '🔍', '📱', '✅', '🏷️'] },
  { keywords: ['支付', '钱包', '充值', '余额'], emojis: ['💳', '💰', '🪙', '📲', '✅'] },
];

const EMOJI_FALLBACK = ['⭐', '📋', '🔖', '💡', '🎯', '🌟', '✅', '🏷️'];

function getRecommendedEmojis(title: string): { emojis: string[]; isDefault: boolean } {
  if (!title) return { emojis: EMOJI_FALLBACK.slice(0, 8), isDefault: true };
  const matched: string[] = [];
  for (const group of EMOJI_KEYWORD_MAP) {
    if (group.keywords.some((kw) => title.includes(kw))) {
      for (const e of group.emojis) {
        if (!matched.includes(e)) matched.push(e);
      }
      if (matched.length >= 8) break;
    }
  }
  if (matched.length > 0) return { emojis: matched.slice(0, 8), isDefault: false };
  return { emojis: EMOJI_FALLBACK.slice(0, 8), isDefault: true };
}

// ─── Emoji Categories ─────────────────────────────────────────────────────────

const EMOJI_CATEGORIES: { name: string; emojis: string[] }[] = [
  {
    name: '医疗健康',
    emojis: [
      '🏥', '🩺', '💊', '💉', '🧪', '🔬', '🩸', '🫀', '🫁', '🦷',
      '🦴', '🩻', '🧬', '⚕️', '🛡️', '🚑', '🦽', '😷', '🤧', '🌡️',
      '🤒', '🩹', '🧑‍⚕️', '❤️‍🩹', '🏨', '🧫', '🧲', '💓', '❤️', '🫶',
      '🩼', '🏋️‍♂️',
    ],
  },
  {
    name: '运动健身',
    emojis: [
      '🏃', '💪', '🧘', '🚴', '🏋️', '🏊', '🏀', '⚽', '🏓', '🎾',
      '🥊', '🏄', '🚣', '⛹️', '🤸', '🧗', '⛷️', '🎿', '🏆', '🥇',
      '🥈', '🥉', '🎖️', '🏅',
    ],
  },
  {
    name: '食物饮料',
    emojis: [
      '🍎', '🍊', '🍋', '🍌', '🍇', '🍓', '🍒', '🍑', '🥝', '🍍',
      '🥭', '🍈', '🥗', '🥦', '🥕', '🌽', '🍆', '🥒', '🧅', '🧄',
      '🍲', '🍜', '🍛', '🍱', '🍣', '🍚', '🍙', '🥟', '🫕', '🥩',
      '🍗', '🍖', '🥛', '🫖', '🍵', '☕', '🧃', '🥤', '🍶', '🍺',
      '🍷', '🍹',
    ],
  },
  {
    name: '自然植物',
    emojis: [
      '🌿', '🌸', '🌺', '🌻', '🌹', '🌷', '💐', '🌴', '🌳', '🌲',
      '🍃', '🍂', '🍁', '🌾', '🎍', '🎋', '🎄', '🪴', '🌵', '🌈',
      '🌤️', '☀️', '🌙', '⭐', '🌟', '💫', '✨', '🌊', '🌋', '🏔️',
      '🗻', '☁️', '🌧️', '⛅', '🌅', '🌄',
    ],
  },
  {
    name: '活动物品',
    emojis: [
      '📅', '🗓️', '⏰', '⏳', '📌', '📎', '📍', '🔍', '🔎', '🔑',
      '🔒', '🛠️', '⚙️', '🧰', '📦', '📮', '📬', '💌', '📧', '📩',
      '💼', '📱', '💻', '🖥️', '📷', '📹', '🎬', '🎤', '🎧', '🎵',
      '🎶', '📚', '📖', '📝', '✏️', '📋', '📊', '📈', '📉', '🎯',
      '🎲', '🎮', '🎁', '🎉', '🎊', '🏷️', '🛒', '💡', '🔔', '🔕',
      '📣', '📢', '🪞', '🧹', '🧳', '🧲', '🪜', '💰', '💳', '🪙',
      '📲',
    ],
  },
  {
    name: '符号标志',
    emojis: [
      '✅', '❌', '❓', '❗', '⚠️', '🚫', '⛔', '🔴', '🟢', '🔵',
      '🟡', '✨', '⭐', '🌟', '💯', '🔥', '♻️', '🈲', '🈵', '㊗️',
      '㊙️', '🆘', '🆕', '🆓', '🔝', '🔜', '🔙', '🔚', '🔛', '⬆️',
      '⬇️', '⬅️', '➡️', '↗️', '↘️', '↙️', '↖️', '↕️', '↔️', '🔄',
      '🔃', '♾️', '➕', '➖', '✖️', '➗', '💲', '💱', '📵', '🚷',
      '🚭', '🚯', '🚱', '❤️', '🧡', '💛', '💚', '💙', '💜', '🖤',
      '🤍', '🤎', '💖', '💗', '💝', '💘', '💕', '❣️', '💔', '♥️',
    ],
  },
  {
    name: '动物',
    emojis: [
      '🐶', '🐱', '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐨', '🐯',
      '🦁', '🐮', '🐷', '🐸', '🐵', '🙈', '🙉', '🙊', '🐔', '🐧',
      '🐦', '🐤', '🦆', '🦅', '🦉', '🦇', '🐺', '🐗', '🐴', '🦄',
      '🐝', '🐛', '🦋', '🐌', '🐞', '🐜', '🦟', '🦗', '🕷️', '🦂',
      '🐢', '🐍', '🦎', '🦖', '🦕', '🐙', '🦑', '🦐', '🦞', '🦀',
      '🐡', '🐠', '🐟', '🐬', '🐳', '🐋', '🦈', '🐊', '🦩', '🦚',
      '🦜', '🐓',
    ],
  },
];

// ─── Chinese Label Map for Emoji Search ───────────────────────────────────────

const EMOJI_LABEL_MAP: Record<string, string[]> = {
  '🏥': ['医院', '医疗', '看病', '就医'],
  '🩺': ['听诊器', '诊断', '医生', '检查'],
  '💊': ['药品', '吃药', '药丸', '治疗'],
  '💉': ['注射', '打针', '疫苗', '抽血'],
  '🧪': ['试管', '化验', '实验', '检测'],
  '🔬': ['显微镜', '研究', '化验', '科学'],
  '🩸': ['血液', '抽血', '献血', '血检'],
  '🫀': ['心脏', '心血管', '心跳', '器官'],
  '🫁': ['肺', '呼吸', '肺部', '器官'],
  '🦷': ['牙齿', '口腔', '牙医', '洗牙'],
  '🦴': ['骨骼', '骨科', '骨头', '骨折'],
  '🩻': ['X光', '骨科', '透视', '拍片'],
  '🧬': ['基因', 'DNA', '遗传', '基因检测'],
  '⚕️': ['医疗', '医学', '卫生', '诊疗'],
  '🛡️': ['防护', '保护', '免疫', '保险'],
  '🚑': ['急救', '救护车', '急诊', '120'],
  '🦽': ['轮椅', '康复', '残疾', '辅具'],
  '😷': ['口罩', '防护', '感冒', '传染'],
  '🤧': ['打喷嚏', '感冒', '过敏', '鼻炎'],
  '🌡️': ['温度计', '体温', '发烧', '测温'],
  '🤒': ['发烧', '生病', '不舒服', '感冒'],
  '🩹': ['创可贴', '伤口', '包扎', '外伤'],
  '🧑‍⚕️': ['医生', '护士', '医护', '大夫'],
  '❤️‍🩹': ['康复', '痊愈', '治愈', '恢复'],
  '🏨': ['医院', '住院', '病房', '诊所'],
  '🧫': ['培养皿', '实验', '细菌', '检测'],
  '🧲': ['磁铁', '磁疗', '吸引', '理疗'],
  '💓': ['心跳', '心脏', '健康', '心率'],
  '🫶': ['爱心', '关爱', '呵护', '关怀'],
  '🩼': ['拐杖', '辅助', '康复', '行走'],
  '🏋️‍♂️': ['举重', '力量', '健身', '锻炼'],
  '🏃': ['跑步', '运动', '健身', '锻炼'],
  '💪': ['力量', '强壮', '加油', '健身'],
  '🧘': ['瑜伽', '冥想', '放松', '静心'],
  '🚴': ['骑行', '自行车', '运动', '骑车'],
  '🏋️': ['举重', '健身', '力量', '训练'],
  '🏊': ['游泳', '水上', '运动', '泳池'],
  '🏀': ['篮球', '运动', '球类', '投篮'],
  '⚽': ['足球', '运动', '球类', '踢球'],
  '🏓': ['乒乓球', '运动', '球类', '国球'],
  '🎾': ['网球', '运动', '球类', '球拍'],
  '🥊': ['拳击', '格斗', '运动', '搏击'],
  '🏄': ['冲浪', '水上', '运动', '海浪'],
  '🚣': ['划船', '水上', '运动', '皮划艇'],
  '⛹️': ['篮球', '运动', '健身', '球类'],
  '🤸': ['体操', '翻跟头', '运动', '柔韧'],
  '🧗': ['攀岩', '攀登', '运动', '户外'],
  '⛷️': ['滑雪', '冬季', '运动', '雪地'],
  '🎿': ['滑雪', '冬季', '运动', '雪橇'],
  '🏆': ['奖杯', '冠军', '胜利', '荣誉'],
  '🥇': ['金牌', '第一', '冠军', '奖牌'],
  '🥈': ['银牌', '第二', '亚军', '奖牌'],
  '🥉': ['铜牌', '第三', '季军', '奖牌'],
  '🎖️': ['勋章', '荣誉', '奖励', '表彰'],
  '🏅': ['奖牌', '荣誉', '运动', '比赛'],
  '🍎': ['苹果', '水果', '营养', '健康'],
  '🍊': ['橙子', '水果', '橘子', '柑橘'],
  '🍋': ['柠檬', '水果', '酸', '维C'],
  '🍌': ['香蕉', '水果', '营养', '能量'],
  '🍇': ['葡萄', '水果', '紫色', '酿酒'],
  '🍓': ['草莓', '水果', '甜', '莓果'],
  '🍒': ['樱桃', '水果', '红色', '甜'],
  '🍑': ['桃子', '水果', '蜜桃', '甜'],
  '🥝': ['猕猴桃', '水果', '维C', '奇异果'],
  '🍍': ['菠萝', '水果', '热带', '凤梨'],
  '🥭': ['芒果', '水果', '热带', '甜'],
  '🍈': ['甜瓜', '水果', '哈密瓜', '瓜'],
  '🥗': ['沙拉', '蔬菜', '健康', '减脂'],
  '🥦': ['西兰花', '蔬菜', '绿色', '健康'],
  '🥕': ['胡萝卜', '蔬菜', '维生素', '营养'],
  '🌽': ['玉米', '蔬菜', '粗粮', '营养'],
  '🍆': ['茄子', '蔬菜', '紫色', '烹饪'],
  '🥒': ['黄瓜', '蔬菜', '清爽', '健康'],
  '🧅': ['洋葱', '蔬菜', '调料', '烹饪'],
  '🧄': ['大蒜', '蔬菜', '调料', '杀菌'],
  '🍲': ['火锅', '汤', '炖菜', '美食'],
  '🍜': ['面条', '拉面', '美食', '主食'],
  '🍛': ['咖喱', '米饭', '美食', '套餐'],
  '🍱': ['便当', '盒饭', '套餐', '午餐'],
  '🍣': ['寿司', '日料', '生鱼片', '美食'],
  '🍚': ['米饭', '主食', '白饭', '粮食'],
  '🍙': ['饭团', '日式', '便当', '主食'],
  '🥟': ['饺子', '中餐', '面食', '美食'],
  '🫕': ['奶酪锅', '火锅', '炖', '汤'],
  '🥩': ['牛排', '肉类', '蛋白质', '烹饪'],
  '🍗': ['鸡腿', '肉类', '蛋白质', '美食'],
  '🍖': ['肉骨头', '肉类', '烧烤', '美食'],
  '🥛': ['牛奶', '乳制品', '营养', '饮品'],
  '🫖': ['茶壶', '泡茶', '饮茶', '养生'],
  '🍵': ['绿茶', '茶杯', '饮茶', '养生'],
  '☕': ['咖啡', '饮品', '提神', '下午茶'],
  '🧃': ['果汁', '饮料', '盒装', '饮品'],
  '🥤': ['奶茶', '饮料', '冷饮', '饮品'],
  '🍶': ['清酒', '米酒', '酒', '日式'],
  '🍺': ['啤酒', '饮品', '酒', '聚会'],
  '🍷': ['红酒', '葡萄酒', '酒', '品鉴'],
  '🍹': ['鸡尾酒', '饮品', '酒', '调酒'],
  '🌿': ['草药', '绿色', '植物', '中草药'],
  '🌸': ['樱花', '花朵', '粉色', '春天'],
  '🌺': ['芙蓉', '花朵', '热带', '鲜花'],
  '🌻': ['向日葵', '花朵', '阳光', '快乐'],
  '🌹': ['玫瑰', '花朵', '爱情', '浪漫'],
  '🌷': ['郁金香', '花朵', '春天', '优雅'],
  '💐': ['花束', '鲜花', '送花', '祝福'],
  '🌴': ['椰子树', '热带', '海边', '度假'],
  '🌳': ['大树', '绿色', '自然', '环保'],
  '🌲': ['松树', '常青', '森林', '自然'],
  '🍃': ['叶子', '绿叶', '清新', '自然'],
  '🍂': ['落叶', '秋天', '枫叶', '季节'],
  '🍁': ['枫叶', '秋天', '红叶', '加拿大'],
  '🌾': ['稻穗', '麦子', '丰收', '粮食'],
  '🎍': ['门松', '新年', '日式', '装饰'],
  '🎋': ['七夕', '竹子', '许愿', '节日'],
  '🎄': ['圣诞树', '圣诞', '节日', '装饰'],
  '🪴': ['盆栽', '绿植', '室内', '装饰'],
  '🌵': ['仙人掌', '沙漠', '植物', '多肉'],
  '🌈': ['彩虹', '美好', '希望', '多彩'],
  '🌤️': ['晴天', '天气', '阳光', '好天气'],
  '☀️': ['太阳', '阳光', '晴天', '日照'],
  '🌙': ['月亮', '夜晚', '睡眠', '晚安'],
  '⭐': ['星星', '优秀', '收藏', '推荐'],
  '🌟': ['闪亮', '星星', '出色', '精彩'],
  '💫': ['头晕', '星星', '旋转', '眩晕'],
  '✨': ['闪光', '亮晶晶', '优秀', '推荐'],
  '🌊': ['海浪', '大海', '水', '冲浪'],
  '🌋': ['火山', '喷发', '自然', '地质'],
  '🏔️': ['雪山', '山脉', '高山', '登山'],
  '🗻': ['富士山', '山', '风景', '自然'],
  '☁️': ['云朵', '天气', '多云', '阴天'],
  '🌧️': ['下雨', '雨天', '天气', '雨'],
  '⛅': ['多云', '天气', '阴晴', '白云'],
  '🌅': ['日出', '朝阳', '清晨', '美景'],
  '🌄': ['日落', '山景', '黄昏', '美景'],
  '📅': ['日历', '日期', '预约', '安排'],
  '🗓️': ['日历', '日程', '排期', '计划'],
  '⏰': ['闹钟', '时间', '提醒', '准时'],
  '⏳': ['沙漏', '时间', '等待', '倒计时'],
  '📌': ['图钉', '固定', '标记', '重要'],
  '📎': ['回形针', '附件', '文件', '办公'],
  '📍': ['位置', '地点', '定位', '地图'],
  '🔍': ['搜索', '放大镜', '查找', '检索'],
  '🔎': ['放大镜', '查看', '搜索', '检查'],
  '🔑': ['钥匙', '密码', '安全', '解锁'],
  '🔒': ['锁', '安全', '保密', '加密'],
  '🛠️': ['工具', '维修', '设置', '修理'],
  '⚙️': ['齿轮', '设置', '配置', '系统'],
  '🧰': ['工具箱', '维修', '工具', '装备'],
  '📦': ['包裹', '快递', '打包', '箱子'],
  '📮': ['邮箱', '邮件', '投递', '信箱'],
  '📬': ['邮箱', '收信', '邮件', '通知'],
  '💌': ['情书', '信件', '邮件', '消息'],
  '📧': ['电子邮件', '邮件', '通知', '消息'],
  '📩': ['收件箱', '邮件', '信封', '消息'],
  '💼': ['公文包', '办公', '工作', '商务'],
  '📱': ['手机', '移动', '通讯', '智能手机'],
  '💻': ['电脑', '笔记本', '编程', '办公'],
  '🖥️': ['台式电脑', '显示器', '办公', '电脑'],
  '📷': ['相机', '拍照', '摄影', '扫码'],
  '📹': ['摄像机', '录像', '视频', '拍摄'],
  '🎬': ['电影', '场记板', '拍摄', '影视'],
  '🎤': ['麦克风', '唱歌', '演讲', '录音'],
  '🎧': ['耳机', '音乐', '听歌', '音频'],
  '🎵': ['音乐', '音符', '旋律', '歌曲'],
  '🎶': ['音乐', '旋律', '歌声', '曲子'],
  '📚': ['书本', '学习', '阅读', '教育'],
  '📖': ['书籍', '阅读', '读书', '知识'],
  '📝': ['笔记', '记录', '备忘', '文档'],
  '✏️': ['铅笔', '写字', '编辑', '绘画'],
  '📋': ['剪贴板', '清单', '列表', '任务'],
  '📊': ['柱状图', '统计', '数据', '报表'],
  '📈': ['上升', '增长', '趋势', '统计'],
  '📉': ['下降', '减少', '趋势', '统计'],
  '🎯': ['靶心', '目标', '精准', '命中'],
  '🎲': ['骰子', '游戏', '随机', '娱乐'],
  '🎮': ['游戏', '手柄', '电子游戏', '娱乐'],
  '🎁': ['礼物', '礼品', '惊喜', '赠送'],
  '🎉': ['庆祝', '派对', '恭喜', '活动'],
  '🎊': ['彩带', '庆祝', '节日', '狂欢'],
  '🏷️': ['标签', '价签', '分类', '标记'],
  '🛒': ['购物车', '购物', '商城', '买东西'],
  '💡': ['灯泡', '创意', '想法', '提示'],
  '🔔': ['铃铛', '通知', '提醒', '消息'],
  '🔕': ['静音', '免打扰', '关闭通知', '安静'],
  '📣': ['喇叭', '公告', '宣传', '通知'],
  '📢': ['扩音器', '广播', '通知', '公告'],
  '🪞': ['镜子', '美容', '化妆', '照镜子'],
  '🧹': ['扫帚', '清洁', '打扫', '卫生'],
  '🧳': ['行李箱', '旅行', '出差', '行李'],
  '🪜': ['梯子', '攀爬', '工具', '阶梯'],
  '💰': ['钱袋', '金钱', '财富', '收入'],
  '💳': ['银行卡', '支付', '信用卡', '刷卡'],
  '🪙': ['硬币', '金币', '零钱', '代币'],
  '📲': ['手机', '移动支付', '下载', '应用'],
  '✅': ['完成', '正确', '通过', '确认'],
  '❌': ['错误', '取消', '关闭', '删除'],
  '❓': ['问号', '疑问', '帮助', '问题'],
  '❗': ['感叹号', '注意', '重要', '警告'],
  '⚠️': ['警告', '注意', '危险', '提醒'],
  '🚫': ['禁止', '不允许', '禁令', '停止'],
  '⛔': ['禁止通行', '停止', '禁入', '不可'],
  '🔴': ['红色', '圆点', '停止', '警告'],
  '🟢': ['绿色', '圆点', '通过', '可用'],
  '🔵': ['蓝色', '圆点', '信息', '标记'],
  '🟡': ['黄色', '圆点', '警示', '标记'],
  '💯': ['满分', '一百分', '完美', '优秀'],
  '🔥': ['火', '热门', '火爆', '流行'],
  '♻️': ['回收', '环保', '循环', '可再生'],
  '🆘': ['求救', '紧急', '急救', 'SOS'],
  '🆕': ['新', '新品', '最新', '上新'],
  '🆓': ['免费', '赠送', '不收费', '白送'],
  '🔝': ['置顶', '顶部', '最高', '上升'],
  '🔜': ['即将', '马上', '快了', '下一步'],
  '❤️': ['红心', '爱心', '喜欢', '爱'],
  '🧡': ['橙心', '温暖', '热情', '活力'],
  '💛': ['黄心', '友谊', '快乐', '阳光'],
  '💚': ['绿心', '健康', '自然', '环保'],
  '💙': ['蓝心', '信任', '冷静', '忠诚'],
  '💜': ['紫心', '优雅', '神秘', '浪漫'],
  '🖤': ['黑心', '酷', '暗黑', '个性'],
  '🤍': ['白心', '纯洁', '简约', '干净'],
  '🤎': ['棕心', '大地', '自然', '温暖'],
  '💖': ['闪亮爱心', '喜爱', '心动', '甜蜜'],
  '💗': ['跳动的心', '心动', '喜欢', '粉色'],
  '💝': ['礼物心', '爱心礼物', '心意', '送礼'],
  '💘': ['丘比特', '一箭穿心', '爱情', '心动'],
  '💕': ['双心', '甜蜜', '恋爱', '喜欢'],
  '❣️': ['心形叹号', '心', '重要', '爱'],
  '♥️': ['红心', '爱心', '扑克', '心形'],
  '🐶': ['狗', '宠物', '小狗', '汪汪'],
  '🐱': ['猫', '宠物', '小猫', '喵喵'],
  '🐭': ['老鼠', '鼠标', '小鼠', '啮齿'],
  '🐹': ['仓鼠', '宠物', '可爱', '小仓鼠'],
  '🐰': ['兔子', '小兔', '可爱', '宠物'],
  '🦊': ['狐狸', '动物', '聪明', '狡猾'],
  '🐻': ['熊', '棕熊', '动物', '可爱'],
  '🐼': ['熊猫', '大熊猫', '国宝', '可爱'],
  '🐨': ['考拉', '树袋熊', '澳洲', '可爱'],
  '🐯': ['老虎', '虎', '猛兽', '威猛'],
  '🦁': ['狮子', '猛兽', '丛林之王', '勇敢'],
  '🐮': ['牛', '奶牛', '牛年', '勤劳'],
  '🐷': ['猪', '小猪', '可爱', '粉嫩'],
  '🐸': ['青蛙', '蛙', '动物', '绿色'],
  '🐵': ['猴子', '灵长类', '调皮', '可爱'],
  '🙈': ['不看', '害羞', '捂眼猴', '非礼勿视'],
  '🙉': ['不听', '捂耳猴', '非礼勿听', '猴子'],
  '🙊': ['不说', '捂嘴猴', '非礼勿言', '猴子'],
  '🐔': ['鸡', '公鸡', '母鸡', '家禽'],
  '🐧': ['企鹅', '南极', '可爱', '冰雪'],
  '🐦': ['鸟', '小鸟', '飞鸟', '雀'],
  '🐤': ['小鸡', '雏鸟', '可爱', '黄色'],
  '🦆': ['鸭子', '鸭', '水禽', '嘎嘎'],
  '🦅': ['老鹰', '雄鹰', '猛禽', '自由'],
  '🦉': ['猫头鹰', '夜行', '智慧', '鸟类'],
  '🦇': ['蝙蝠', '夜行', '飞行', '洞穴'],
  '🐺': ['狼', '野狼', '动物', '嚎叫'],
  '🐗': ['野猪', '猪', '动物', '野生'],
  '🐴': ['马', '骏马', '奔跑', '动物'],
  '🦄': ['独角兽', '梦幻', '魔法', '可爱'],
  '🐝': ['蜜蜂', '勤劳', '蜂蜜', '昆虫'],
  '🐛': ['虫子', '毛毛虫', '昆虫', '可爱'],
  '🦋': ['蝴蝶', '美丽', '昆虫', '飞舞'],
  '🐌': ['蜗牛', '慢', '壳', '爬行'],
  '🐞': ['瓢虫', '七星瓢虫', '昆虫', '幸运'],
  '🐜': ['蚂蚁', '勤劳', '昆虫', '团结'],
  '🦟': ['蚊子', '叮咬', '昆虫', '烦人'],
  '🦗': ['蟋蟀', '昆虫', '鸣叫', '秋天'],
  '🕷️': ['蜘蛛', '蛛网', '节肢', '八脚'],
  '🦂': ['蝎子', '毒', '节肢', '沙漠'],
  '🐢': ['乌龟', '长寿', '慢', '爬行'],
  '🐍': ['蛇', '爬行', '蟒', '灵蛇'],
  '🦎': ['蜥蜴', '爬行', '壁虎', '变色龙'],
  '🦖': ['恐龙', '霸王龙', '史前', '巨大'],
  '🦕': ['恐龙', '长颈龙', '史前', '草食'],
  '🐙': ['章鱼', '八爪鱼', '海洋', '软体'],
  '🦑': ['鱿鱼', '乌贼', '海洋', '软体'],
  '🦐': ['虾', '海鲜', '水产', '美食'],
  '🦞': ['龙虾', '海鲜', '高档', '美食'],
  '🦀': ['螃蟹', '海鲜', '横行', '水产'],
  '🐡': ['河豚', '鱼', '海洋', '有毒'],
  '🐠': ['热带鱼', '鱼', '海洋', '彩色'],
  '🐟': ['鱼', '水产', '海鲜', '游泳'],
  '🐬': ['海豚', '聪明', '海洋', '可爱'],
  '🐳': ['鲸鱼', '喷水', '海洋', '巨大'],
  '🐋': ['座头鲸', '鲸', '海洋', '蓝鲸'],
  '🦈': ['鲨鱼', '凶猛', '海洋', '大白鲨'],
  '🐊': ['鳄鱼', '凶猛', '爬行', '沼泽'],
  '🦩': ['火烈鸟', '粉色', '鸟类', '优雅'],
  '🦚': ['孔雀', '美丽', '开屏', '鸟类'],
  '🦜': ['鹦鹉', '学舌', '彩色', '鸟类'],
  '🐓': ['公鸡', '打鸣', '鸡', '家禽'],
  '🧧': ['红包', '新年', '吉祥', '中医'],
  '🏮': ['灯笼', '中国', '节日', '红灯笼'],
  '📜': ['卷轴', '古典', '处方', '古方'],
  '🏪': ['便利店', '商店', '药房', '门店'],
  '🏦': ['银行', '金融', '理财', '存钱'],
  '📄': ['文档', '文件', '表格', '记录'],
  '🏘️': ['社区', '小区', '居民区', '住宅'],
  '🏠': ['家', '房子', '居家', '住所'],
  '👴': ['老人', '爷爷', '养老', '长辈'],
  '🤝': ['握手', '合作', '互助', '友好'],
  '😁': ['笑脸', '开心', '微笑', '大笑'],
  '🪥': ['牙刷', '刷牙', '口腔', '清洁'],
  '👁️': ['眼睛', '观察', '视力', '眼科'],
  '👓': ['眼镜', '近视', '配镜', '视力'],
  '🧴': ['护肤', '乳液', '保湿', '美容'],
  '🤰': ['孕妇', '怀孕', '孕期', '妈妈'],
  '👶': ['婴儿', '宝宝', '新生儿', '母婴'],
  '🧒': ['儿童', '小孩', '孩子', '少年'],
  '🍼': ['奶瓶', '婴儿', '喂奶', '母婴'],
  '🎈': ['气球', '生日', '庆祝', '快乐'],
  '🍯': ['蜂蜜', '甜蜜', '养生', '滋补'],
  '⚖️': ['天平', '平衡', '体重', '公正'],
  '🌬️': ['吹风', '风', '呼吸', '空气'],
  '💨': ['风', '速度', '飘', '排气'],
  '🎗️': ['丝带', '公益', '抗癌', '粉红丝带'],
  '🫃': ['腹部', '胃', '消化', '肚子'],
  '⚡': ['闪电', '电', '能量', '快速'],
  '🌼': ['花', '小花', '雏菊', '花粉'],
  '🦠': ['病毒', '细菌', '微生物', '传染'],
  '🌞': ['太阳', '阳光', '早安', '每日'],
  '✍️': ['书写', '签名', '填写', '记录'],
  '🎓': ['毕业', '学历', '教育', '学位'],
  '🧑‍🏫': ['老师', '教师', '授课', '教学'],
  '🚀': ['火箭', '启动', '加速', '飞速'],
  '🙋': ['举手', '提问', '自荐', '帮助'],
  '👤': ['用户', '个人', '头像', '账号'],
  '🗺️': ['地图', '世界', '旅行', '导航'],
  '🧭': ['指南针', '方向', '导航', '探索'],
  '👍': ['点赞', '好', '赞', '棒'],
  '🔖': ['书签', '收藏', '标签', '保存'],
  '😊': ['微笑', '开心', '友好', '快乐'],
  '💆': ['按摩', '放松', '舒适', '头部'],
  '😴': ['睡觉', '困了', '睡眠', '休息'],
  '🛌': ['床', '睡觉', '休息', '卧室'],
  '💤': ['睡眠', '打呼', '休息', 'ZZZ'],
  '👨‍👩‍👧': ['家庭', '一家人', '亲子', '全家福'],
  '👨‍⚕️': ['男医生', '大夫', '专家', '主任'],
  '💬': ['聊天', '对话', '消息', '沟通'],
  '🗂️': ['文件夹', '分类', '归档', '整理'],
  '🍽️': ['餐具', '用餐', '刀叉', '吃饭'],
  '🔄': ['刷新', '重复', '循环', '更新'],
  '🔃': ['刷新', '重载', '旋转', '更新'],
  '💔': ['心碎', '伤心', '分手', '难过'],
  '🈲': ['禁止', '中文', '限制', '不可'],
  '🈵': ['满', '已满', '中文', '全满'],
  '㊗️': ['祝', '祝福', '恭喜', '庆祝'],
  '㊙️': ['秘密', '保密', '机密', '隐私'],
  '🔙': ['返回', '后退', '回去', '上一步'],
  '🔚': ['结束', '终止', '完毕', 'END'],
  '🔛': ['开启', '打开', '启用', 'ON'],
  '⬆️': ['向上', '上升', '提高', '增加'],
  '⬇️': ['向下', '下降', '降低', '减少'],
  '⬅️': ['向左', '左边', '返回', '后退'],
  '➡️': ['向右', '右边', '前进', '下一步'],
  '↗️': ['右上', '上升', '增长', '趋势'],
  '↘️': ['右下', '下降', '趋势', '减少'],
  '↙️': ['左下', '下降', '方向', '趋势'],
  '↖️': ['左上', '方向', '上升', '返回'],
  '↕️': ['上下', '纵向', '高度', '垂直'],
  '↔️': ['左右', '横向', '宽度', '水平'],
  '♾️': ['无穷', '无限', '永恒', '循环'],
  '➕': ['加号', '增加', '添加', '更多'],
  '➖': ['减号', '减少', '删除', '移除'],
  '✖️': ['乘号', '错误', '关闭', '取消'],
  '➗': ['除号', '除法', '分割', '平均'],
  '💲': ['美元', '金钱', '价格', '货币'],
  '💱': ['汇率', '换汇', '外币', '兑换'],
  '📵': ['禁止手机', '关机', '静音', '禁用'],
  '🚷': ['禁止行人', '禁入', '限制', '不可进'],
  '🚭': ['禁止吸烟', '无烟', '戒烟', '健康'],
  '🚯': ['禁止乱扔', '垃圾', '环保', '清洁'],
  '🚱': ['非饮用水', '禁止', '不可饮', '水'],
};

// ─── Helper ───────────────────────────────────────────────────────────────────

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

// ─── Emoji Picker Modal ──────────────────────────────────────────────────────

function EmojiPickerModal({
  open,
  onOk,
  onCancel,
  menuName,
  defaultEmoji,
}: {
  open: boolean;
  onOk: (emoji: string) => void;
  onCancel: () => void;
  menuName: string;
  defaultEmoji: string;
}) {
  const [selected, setSelected] = useState<string>('');
  const [activeCategory, setActiveCategory] = useState(0);
  const [searchText, setSearchText] = useState('');
  const [searchResults, setSearchResults] = useState<string[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (open) {
      setSelected(defaultEmoji || '');
      setActiveCategory(0);
      setSearchText('');
      setSearchResults([]);
      setIsSearching(false);
    }
  }, [open, defaultEmoji]);

  const handleSearch = (value: string) => {
    setSearchText(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!value.trim()) {
      setIsSearching(false);
      setSearchResults([]);
      return;
    }
    debounceRef.current = setTimeout(() => {
      const kw = value.trim().toLowerCase();
      const results: string[] = [];
      for (const [emoji, labels] of Object.entries(EMOJI_LABEL_MAP)) {
        if (labels.some((l) => l.includes(kw))) {
          results.push(emoji);
        }
      }
      setSearchResults(results);
      setIsSearching(true);
    }, 300);
  };

  const recommendation = getRecommendedEmojis(menuName);

  const renderEmojiGrid = (emojis: string[]) => (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(10, 1fr)',
        gap: 4,
        maxHeight: 300,
        overflowY: 'auto',
        padding: 4,
      }}
    >
      {emojis.map((emoji, idx) => (
        <button
          key={`${emoji}-${idx}`}
          type="button"
          onClick={() => setSelected(emoji)}
          style={{
            width: 36,
            height: 36,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 20,
            border: selected === emoji ? '2px solid #1677ff' : '1px solid transparent',
            borderRadius: 6,
            backgroundColor: selected === emoji ? '#e6f4ff' : 'transparent',
            cursor: 'pointer',
            transition: 'all 0.15s',
          }}
          onMouseEnter={(e) => {
            if (selected !== emoji) {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#f5f5f5';
            }
          }}
          onMouseLeave={(e) => {
            if (selected !== emoji) {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent';
            }
          }}
        >
          {emoji}
        </button>
      ))}
    </div>
  );

  return (
    <Modal
      title="选择 Emoji 图标"
      open={open}
      onOk={() => selected && onOk(selected)}
      onCancel={onCancel}
      width={520}
      okButtonProps={{ disabled: !selected }}
      destroyOnClose
    >
      {/* Search */}
      <Input.Search
        placeholder="搜索 Emoji（输入中文关键词，如：医院、苹果）"
        value={searchText}
        onChange={(e) => handleSearch(e.target.value)}
        allowClear
        style={{ marginBottom: 16 }}
      />

      {!isSearching && (
        <>
          {/* Recommendation Area */}
          <div
            style={{
              background: '#f0f8ff',
              padding: 12,
              borderRadius: 8,
              marginBottom: 16,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8 }}>
              {menuName
                ? `✨ 为「${menuName}」推荐${recommendation.isDefault ? '（通用推荐）' : ''}`
                : '✨ 推荐'}
            </div>
            {menuName ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {recommendation.emojis.map((emoji, idx) => (
                  <button
                    key={`rec-${emoji}-${idx}`}
                    type="button"
                    onClick={() => setSelected(emoji)}
                    style={{
                      width: 36,
                      height: 36,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 20,
                      border: selected === emoji ? '2px solid #1677ff' : '1px solid #d9d9d9',
                      borderRadius: 6,
                      backgroundColor: selected === emoji ? '#e6f4ff' : '#fff',
                      cursor: 'pointer',
                    }}
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 13, color: '#999' }}>
                请先输入菜单名称以获取推荐
              </div>
            )}
          </div>

          {/* Category Tabs */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
            {EMOJI_CATEGORIES.map((cat, idx) => (
              <button
                key={cat.name}
                type="button"
                onClick={() => setActiveCategory(idx)}
                style={{
                  padding: '4px 12px',
                  fontSize: 13,
                  border: activeCategory === idx ? '1px solid #1677ff' : '1px solid #d9d9d9',
                  borderRadius: 16,
                  backgroundColor: activeCategory === idx ? '#e6f4ff' : '#fff',
                  color: activeCategory === idx ? '#1677ff' : '#333',
                  cursor: 'pointer',
                  fontWeight: activeCategory === idx ? 500 : 400,
                }}
              >
                {cat.name}
              </button>
            ))}
          </div>

          {/* Emoji Grid for active category */}
          {renderEmojiGrid(EMOJI_CATEGORIES[activeCategory].emojis)}
        </>
      )}

      {/* Search Results */}
      {isSearching && (
        <div>
          {searchResults.length > 0 ? (
            renderEmojiGrid(searchResults)
          ) : (
            <div
              style={{
                textAlign: 'center',
                padding: '32px 0',
                color: '#999',
                fontSize: 14,
              }}
            >
              未找到匹配的 Emoji，请尝试其他关键词
            </div>
          )}
        </div>
      )}

      {/* Selected Indicator */}
      <div
        style={{
          marginTop: 12,
          padding: '8px 0',
          borderTop: '1px solid #f0f0f0',
          fontSize: 14,
          color: '#666',
        }}
      >
        {selected ? (
          <span>
            已选择：<span style={{ fontSize: 24, verticalAlign: 'middle', marginLeft: 4 }}>{selected}</span>
          </span>
        ) : (
          '请点击上方 Emoji 进行选择'
        )}
      </div>
    </Modal>
  );
}

// ─── Page Component ───────────────────────────────────────────────────────────

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
  const [emojiPickerOpen, setEmojiPickerOpen] = useState(false);
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

  const handleEmojiSelected = (emoji: string) => {
    setSelectedEmoji(emoji);
    form.setFieldsValue({ icon_content: emoji });
    setEmojiPickerOpen(false);
  };

  const handleClearEmoji = () => {
    setSelectedEmoji('');
    form.setFieldsValue({ icon_content: '' });
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
            <Radio.Group onChange={(e) => {
              setIconType(e.target.value);
              if (e.target.value !== 'emoji') {
                setSelectedEmoji('');
                form.setFieldsValue({ icon_content: '' });
              }
            }}>
              <Radio value="emoji">Emoji</Radio>
              <Radio value="image">图片</Radio>
            </Radio.Group>
          </Form.Item>
          {iconType === 'emoji' ? (
            <>
              {/* Emoji Preview + Select Button + Clear */}
              <Form.Item
                label="图标内容"
                required
                style={{ marginBottom: 16 }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <div
                    style={{
                      width: 72,
                      height: 72,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      border: selectedEmoji ? '1px solid #d9d9d9' : '2px dashed #d9d9d9',
                      borderRadius: 8,
                      backgroundColor: '#fafafa',
                      fontSize: 48,
                      lineHeight: 1,
                      flexShrink: 0,
                    }}
                  >
                    {selectedEmoji || (
                      <SmileOutlined style={{ fontSize: 28, color: '#bbb' }} />
                    )}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <Button
                      type="primary"
                      icon={<SmileOutlined />}
                      onClick={() => setEmojiPickerOpen(true)}
                    >
                      选择图标
                    </Button>
                    {selectedEmoji && (
                      <Button
                        type="link"
                        size="small"
                        danger
                        icon={<CloseCircleOutlined />}
                        onClick={handleClearEmoji}
                        style={{ padding: 0, height: 'auto' }}
                      >
                        清除
                      </Button>
                    )}
                  </div>
                </div>
              </Form.Item>
              <Form.Item
                name="icon_content"
                rules={[{ required: true, message: '请选择一个 Emoji 图标' }]}
                style={{ display: 'none' }}
              >
                <Input />
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

      {/* Emoji Picker Modal */}
      <EmojiPickerModal
        open={emojiPickerOpen}
        onOk={handleEmojiSelected}
        onCancel={() => setEmojiPickerOpen(false)}
        menuName={watchedName || ''}
        defaultEmoji={selectedEmoji}
      />
    </div>
  );
}
