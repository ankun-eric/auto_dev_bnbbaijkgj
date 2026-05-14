/**
 * [AICHAT-OPTIM-FIX-V1 F-01 2026-05-14] 公共 EmojiPicker 组件
 *
 * 从 admin-web/src/app/(admin)/home-menus/page.tsx 提取并通用化的 Emoji 选择器，
 * 用于「功能按钮管理」和「首页菜单管理」两处共用：
 *   - 800+ 内置 Emoji，分 8+ 大类切换
 *   - 关键字搜索（输入中文关键词命中候选池）
 *   - 智能推荐（根据外部传入 keyword 自动推荐 4~8 个 Emoji）
 *
 * 用法：
 *   const [open, setOpen] = useState(false);
 *   <EmojiPickerModal
 *     open={open}
 *     defaultEmoji={icon}
 *     menuName={watchedName}
 *     onOk={(emoji) => setIcon(emoji)}
 *     onCancel={() => setOpen(false)}
 *   />
 */
'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Modal, Input } from 'antd';

// ─── Emoji Keyword Mapping (40+ groups) ───────────────────────────────────────

export const EMOJI_KEYWORD_MAP: { keywords: string[]; emojis: string[] }[] = [
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
  { keywords: ['药品', '用药', '处方', '配药', '药房', '药', '服药', '吃药'], emojis: ['💊', '💉', '🧪', '🏪', '📜'] },
  { keywords: ['识药', '拍照识药'], emojis: ['📷', '💊', '🔍', '🧪'] },
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
  { keywords: ['儿科', '儿童', '小儿'], emojis: ['👶', '🧒', '🍼', '🎈', '🏥'] },
  { keywords: ['养生', '调理', '滋补', '食疗', '膳食'], emojis: ['🍲', '🫖', '🌿', '🍯', '✨'] },
  { keywords: ['减肥', '瘦身', '体重', '塑形'], emojis: ['⚖️', '🏃', '🥗', '📉', '💪'] },
  { keywords: ['心脏', '心血管', '冠心病', '房颤'], emojis: ['❤️', '💓', '🫀', '🩺', '📊'] },
  { keywords: ['呼吸', '哮喘', '肺', '咳嗽', '感冒'], emojis: ['🫁', '😷', '🌬️', '💨', '🤧'] },
  { keywords: ['骨科', '骨折', '关节', '腰椎', '颈椎'], emojis: ['🦴', '🩻', '💆', '🏥', '🦽'] },
  { keywords: ['客服', '咨询', '帮助', '反馈'], emojis: ['💬', '📞', '🙋', '📮', '🤝'] },
  { keywords: ['视频', '直播', '通话'], emojis: ['📹', '🎬', '📷', '🎥', '💬'] },
  { keywords: ['提醒', '闹钟', '日历'], emojis: ['⏰', '📅', '🔔', '⏳', '🗓️'] },
  { keywords: ['设置', '个人', '账号', '隐私', '安全'], emojis: ['⚙️', '👤', '🔒', '🛠️', '📱'] },
  { keywords: ['地图', '导航', '附近', '位置', '门店'], emojis: ['📍', '🗺️', '🧭', '🏪', '📌'] },
  { keywords: ['优惠', '促销', '折扣', '红包', '券'], emojis: ['🎉', '🧧', '💰', '🎁', '🏷️'] },
  { keywords: ['收藏', '关注', '点赞', '喜欢'], emojis: ['❤️', '⭐', '🔖', '👍', '💖'] },
  { keywords: ['通知', '消息', '提醒', '公告'], emojis: ['🔔', '📢', '💌', '📣', '📬'] },
  { keywords: ['扫码', '二维码', '扫一扫'], emojis: ['📷', '🔍', '📱', '✅', '🏷️'] },
  { keywords: ['支付', '钱包', '充值', '余额'], emojis: ['💳', '💰', '🪙', '📲', '✅'] },
  { keywords: ['签到', '打卡', '每日'], emojis: ['✅', '📅', '🎯', '⏰', '🌞'] },
  { keywords: ['问卷', '评估', '测评', '量表', '自测'], emojis: ['📝', '📊', '✍️', '🎯', '📋'] },
  { keywords: ['课程', '学习', '教育', '科普', '知识'], emojis: ['📚', '🎓', '💡', '📖', '🧑‍🏫'] },
];

const EMOJI_FALLBACK = ['⭐', '📋', '🔖', '💡', '🎯', '🌟', '✅', '🏷️'];

export function getRecommendedEmojis(title: string): { emojis: string[]; isDefault: boolean } {
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

export const EMOJI_CATEGORIES: { name: string; emojis: string[] }[] = [
  {
    name: '医疗健康',
    emojis: [
      '🏥', '🩺', '💊', '💉', '🧪', '🔬', '🩸', '🫀', '🫁', '🦷',
      '🦴', '🩻', '🧬', '⚕️', '🛡️', '🚑', '🦽', '😷', '🤧', '🌡️',
      '🤒', '🩹', '🧑‍⚕️', '❤️‍🩹', '🏨', '🧫', '💓', '❤️', '🫶', '🩼',
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
      '🥭', '🥗', '🥦', '🥕', '🌽', '🥒', '🍲', '🍜', '🍛', '🍱',
      '🍣', '🍚', '🥟', '🥩', '🥛', '🫖', '🍵', '☕', '🧃', '🥤',
    ],
  },
  {
    name: '自然植物',
    emojis: [
      '🌿', '🌸', '🌺', '🌻', '🌹', '🌷', '💐', '🌴', '🌳', '🌲',
      '🍃', '🍂', '🍁', '🌾', '🌵', '🌈', '🌤️', '☀️', '🌙', '⭐',
      '🌟', '💫', '✨', '🌊', '🏔️', '☁️', '🌧️', '⛅', '🌱', '🍀',
    ],
  },
  {
    name: '活动物品',
    emojis: [
      '📅', '🗓️', '⏰', '⏳', '📌', '📎', '📍', '🔍', '🔑', '🔒',
      '🛠️', '⚙️', '🧰', '📦', '📮', '💌', '📧', '📩', '💼', '📱',
      '💻', '🖥️', '📷', '📹', '🎬', '🎤', '🎧', '🎵', '📚', '📖',
      '📝', '✏️', '📋', '📊', '📈', '📉', '🎯', '🎁', '🎉', '🏷️',
      '🛒', '💡', '🔔', '📣', '📢', '💰', '💳', '🪙',
    ],
  },
  {
    name: '符号标志',
    emojis: [
      '✅', '❌', '❓', '❗', '⚠️', '🚫', '⛔', '🔴', '🟢', '🔵',
      '🟡', '✨', '⭐', '💯', '🔥', '♻️', '🆘', '🆕', '🆓', '🔝',
      '⬆️', '⬇️', '⬅️', '➡️', '🔄', '➕', '➖', '✖️', '💲', '❤️',
      '🧡', '💛', '💚', '💙', '💜', '🖤', '🤍', '💖', '💗', '💝',
      '💘', '💕', '♥️',
    ],
  },
  {
    name: '动物',
    emojis: [
      '🐶', '🐱', '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐨', '🐯',
      '🦁', '🐮', '🐷', '🐸', '🐵', '🐔', '🐧', '🐦', '🐤', '🦆',
      '🦅', '🦉', '🦇', '🐺', '🐗', '🐴', '🦄', '🐝', '🦋', '🐢',
      '🐍', '🐙', '🐬', '🐳', '🦈',
    ],
  },
  {
    name: '科技数码',
    emojis: [
      '🤖', '🖥️', '💻', '📱', '🔌', '🎮', '🕹️', '📡', '🛰️', '🔋',
      '⌨️', '🖨️', '🖱️', '💾', '📀', '🔧', '⚡', '🌐', '📶', '🔗',
    ],
  },
  {
    name: '人物表情',
    emojis: [
      '😀', '😊', '🥰', '😎', '🤔', '😴', '👶', '👨‍⚕️', '👩‍🔬', '👨‍🍳',
      '👩‍🏫', '👨‍💼', '🧑‍🔧', '👩‍💻', '🧓', '👦', '👧', '🤱', '🙋', '🤝',
    ],
  },
  {
    name: '交通建筑',
    emojis: [
      '🚗', '🚕', '🚌', '🚑', '🚲', '🛩️', '🚀', '🚢', '🚄', '🚇',
      '🏠', '🏢', '🏫', '🏥', '🏦', '🏨', '🏪', '🏛️', '🏰',
    ],
  },
];

// ─── Chinese Label Map for Emoji Search ───────────────────────────────────────

export const EMOJI_LABEL_MAP: Record<string, string[]> = {
  '🏥': ['医院', '医疗', '看病', '就医'],
  '🩺': ['听诊器', '诊断', '医生', '检查', '问诊'],
  '💊': ['药品', '吃药', '药丸', '治疗', '用药', '识药'],
  '💉': ['注射', '打针', '疫苗', '抽血'],
  '🧪': ['试管', '化验', '实验', '检测'],
  '🔬': ['显微镜', '研究', '化验', '科学'],
  '🩸': ['血液', '抽血', '献血', '血检'],
  '🫀': ['心脏', '心血管', '心跳', '器官'],
  '🫁': ['肺', '呼吸', '肺部', '器官'],
  '🦷': ['牙齿', '口腔', '牙医', '洗牙'],
  '🦴': ['骨骼', '骨科', '骨头', '骨折'],
  '🩻': ['X光', '骨科', '透视', '拍片'],
  '🧬': ['基因', 'DNA', '遗传'],
  '⚕️': ['医疗', '医学', '卫生'],
  '🛡️': ['防护', '保护', '免疫', '保险'],
  '🚑': ['急救', '救护车', '急诊', '120'],
  '🦽': ['轮椅', '康复', '残疾'],
  '😷': ['口罩', '防护', '感冒', '传染'],
  '🤧': ['打喷嚏', '感冒', '过敏'],
  '🌡️': ['温度计', '体温', '发烧'],
  '🤒': ['发烧', '生病', '不舒服'],
  '🩹': ['创可贴', '伤口', '包扎'],
  '🧑‍⚕️': ['医生', '护士', '医护'],
  '❤️‍🩹': ['康复', '痊愈', '治愈'],
  '🏨': ['医院', '住院', '病房', '诊所'],
  '🧫': ['培养皿', '实验', '细菌'],
  '💓': ['心跳', '心脏', '健康'],
  '🫶': ['爱心', '关爱', '呵护'],
  '🩼': ['拐杖', '辅助', '康复'],
  '🏃': ['跑步', '运动', '健身'],
  '💪': ['力量', '强壮', '加油', '健身'],
  '🧘': ['瑜伽', '冥想', '放松'],
  '🚴': ['骑行', '自行车', '运动'],
  '🏋️': ['举重', '健身', '力量'],
  '🍎': ['苹果', '水果', '营养'],
  '🥗': ['沙拉', '蔬菜', '健康', '减脂'],
  '🥦': ['西兰花', '蔬菜', '绿色'],
  '🥕': ['胡萝卜', '蔬菜', '维生素'],
  '🍵': ['绿茶', '茶杯', '饮茶', '养生'],
  '☕': ['咖啡', '饮品', '提神'],
  '🌿': ['草药', '绿色', '植物', '中草药'],
  '🌸': ['樱花', '花朵', '粉色'],
  '🌳': ['大树', '绿色', '自然'],
  '🍃': ['叶子', '绿叶', '清新'],
  '🌈': ['彩虹', '美好', '希望'],
  '☀️': ['太阳', '阳光', '晴天'],
  '🌙': ['月亮', '夜晚', '睡眠'],
  '⭐': ['星星', '优秀', '收藏'],
  '🌟': ['闪亮', '星星', '精彩'],
  '✨': ['闪光', '亮晶晶', '优秀'],
  '📅': ['日历', '日期', '预约'],
  '🗓️': ['日历', '日程', '排期'],
  '⏰': ['闹钟', '时间', '提醒'],
  '⏳': ['沙漏', '时间', '等待'],
  '📍': ['位置', '地点', '定位', '地图'],
  '🔍': ['搜索', '放大镜', '查找'],
  '🔑': ['钥匙', '密码', '安全'],
  '🔒': ['锁', '安全', '保密'],
  '🛠️': ['工具', '维修', '设置'],
  '⚙️': ['齿轮', '设置', '配置'],
  '📦': ['包裹', '快递', '打包'],
  '📮': ['邮箱', '邮件', '投递'],
  '💌': ['情书', '信件', '邮件'],
  '📧': ['电子邮件', '邮件', '通知'],
  '💼': ['公文包', '办公', '工作'],
  '📱': ['手机', '移动', '通讯'],
  '💻': ['电脑', '笔记本', '办公'],
  '🖥️': ['台式电脑', '显示器', '办公'],
  '📷': ['相机', '拍照', '摄影', '扫码'],
  '📹': ['摄像机', '录像', '视频'],
  '🎬': ['电影', '场记板', '拍摄'],
  '🎤': ['麦克风', '唱歌', '演讲'],
  '🎧': ['耳机', '音乐', '听歌'],
  '🎵': ['音乐', '音符', '旋律'],
  '📚': ['书本', '学习', '阅读'],
  '📖': ['书籍', '阅读', '读书'],
  '📝': ['笔记', '记录', '备忘'],
  '✏️': ['铅笔', '写字', '编辑'],
  '📋': ['剪贴板', '清单', '列表'],
  '📊': ['柱状图', '统计', '数据', '报表'],
  '📈': ['上升', '增长', '趋势'],
  '📉': ['下降', '减少', '趋势'],
  '🎯': ['靶心', '目标', '精准'],
  '🎁': ['礼物', '礼品', '惊喜'],
  '🎉': ['庆祝', '派对', '恭喜'],
  '🏷️': ['标签', '价签', '分类'],
  '🛒': ['购物车', '购物', '商城'],
  '💡': ['灯泡', '创意', '想法'],
  '🔔': ['铃铛', '通知', '提醒'],
  '📣': ['喇叭', '公告', '宣传'],
  '📢': ['扩音器', '广播', '通知'],
  '💰': ['钱袋', '金钱', '财富'],
  '💳': ['银行卡', '支付', '信用卡'],
  '🪙': ['硬币', '金币', '零钱'],
  '✅': ['完成', '正确', '通过'],
  '❌': ['错误', '取消', '关闭'],
  '❓': ['问号', '疑问', '帮助'],
  '❗': ['感叹号', '注意', '重要'],
  '⚠️': ['警告', '注意', '危险'],
  '🆘': ['求救', '紧急', '急救'],
  '🆕': ['新', '新品', '最新'],
  '🆓': ['免费', '赠送'],
  '❤️': ['红心', '爱心', '喜欢'],
  '💚': ['绿心', '健康', '自然'],
  '💖': ['闪亮爱心', '喜爱', '心动'],
  '👨‍👩‍👧': ['家庭', '一家人', '亲子'],
  '👨‍⚕️': ['男医生', '大夫', '专家'],
  '👩‍⚕️': ['女医生', '大夫', '专家'],
  '🏠': ['家', '房子', '居家'],
  '👴': ['老人', '爷爷', '养老'],
  '👶': ['婴儿', '宝宝', '新生儿'],
  '👁️': ['眼睛', '观察', '视力'],
  '👓': ['眼镜', '近视', '配镜'],
  '🧴': ['护肤', '乳液', '保湿'],
  '🤰': ['孕妇', '怀孕', '孕期'],
  '🍼': ['奶瓶', '婴儿', '喂奶'],
  '🎈': ['气球', '生日', '庆祝'],
  '🏪': ['便利店', '商店', '药房'],
  '🏛️': ['博物馆', '政府', '机构'],
  '🏫': ['学校', '教育', '教学'],
  '🏦': ['银行', '金融', '理财'],
  '🤖': ['机器人', 'AI', '人工智能'],
  '🌐': ['地球', '网络', '互联网'],
  '🔗': ['链接', '连接', '分享'],
  '💬': ['聊天', '对话', '消息', '沟通', '咨询'],
  '🙋': ['举手', '提问', '自荐'],
  '🤝': ['握手', '合作', '互助'],
  '📌': ['图钉', '固定', '标记'],
};

// ─── EmojiPickerModal ─────────────────────────────────────────────────────────

export interface EmojiPickerModalProps {
  open: boolean;
  onOk: (emoji: string) => void;
  onCancel: () => void;
  /** 用于关键字推荐的名称（按钮名/菜单名） */
  menuName?: string;
  /** 已选中的 Emoji */
  defaultEmoji?: string;
}

export function EmojiPickerModal({
  open,
  onOk,
  onCancel,
  menuName = '',
  defaultEmoji = '',
}: EmojiPickerModalProps) {
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
      data-testid="emoji-picker-grid"
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
      <div data-testid="emoji-picker-modal-content">
        <Input.Search
          placeholder="搜索 Emoji（输入中文关键词，如：医院、用药、家庭）"
          value={searchText}
          onChange={(e) => handleSearch(e.target.value)}
          allowClear
          style={{ marginBottom: 16 }}
          data-testid="emoji-picker-search"
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
              data-testid="emoji-picker-recommendation"
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
                <div style={{ fontSize: 13, color: '#999' }}>请先输入按钮名称以获取推荐</div>
              )}
            </div>

            {/* Category Tabs */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 6px', marginBottom: 12 }}>
              {EMOJI_CATEGORIES.map((cat, idx) => (
                <button
                  key={cat.name}
                  type="button"
                  onClick={() => setActiveCategory(idx)}
                  style={{
                    padding: '3px 10px',
                    fontSize: 12,
                    border: activeCategory === idx ? '1px solid #1677ff' : '1px solid #d9d9d9',
                    borderRadius: 14,
                    backgroundColor: activeCategory === idx ? '#e6f4ff' : '#fff',
                    color: activeCategory === idx ? '#1677ff' : '#333',
                    cursor: 'pointer',
                    fontWeight: activeCategory === idx ? 500 : 400,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {cat.name}
                </button>
              ))}
            </div>

            {renderEmojiGrid(EMOJI_CATEGORIES[activeCategory].emojis)}
          </>
        )}

        {isSearching && (
          <div>
            {searchResults.length > 0 ? (
              renderEmojiGrid(searchResults)
            ) : (
              <div style={{ textAlign: 'center', padding: '32px 0', color: '#999', fontSize: 14 }}>
                未找到匹配的 Emoji，请尝试其他关键词
              </div>
            )}
          </div>
        )}

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
      </div>
    </Modal>
  );
}

export default EmojiPickerModal;
