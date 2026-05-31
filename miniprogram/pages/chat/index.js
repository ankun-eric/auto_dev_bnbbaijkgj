const { post, get, put, del, uploadFile } = require('../../utils/request');
const { generateId } = require('../../utils/util');
const { checkFileSize, uploadWithProgress } = require('../../utils/upload-utils');
const { compressImage } = require('../../utils/image-compress');
// [2026-05-05 全端图片附件 BasePath 治理 v1.0] 把后端"裸 /uploads/..."补齐为带 baseUrl 的绝对 URL
const { resolveAssetUrl, resolveAssetUrls } = require('../../utils/asset-url');
// [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
// 统一按钮意图解析（与后端 button_intent_resolver.py / H5 button-intent.ts 完全一致）
const { resolveButtonIntent: _resolveBtnIntent } = require('../../utils/buttonIntent');

const RELATION_COLORS = {
  '本人': '#52c41a',
  '爸爸': '#1890ff', '妈妈': '#1890ff',
  '儿子': '#eb2f96', '女儿': '#eb2f96',
  '爷爷': '#fa8c16', '奶奶': '#fa8c16',
  '外公': '#fa8c16', '外婆': '#fa8c16'
};
function getRelationColor(name) {
  return RELATION_COLORS[name] || '#8c8c8c';
}

const plugin = requirePlugin('WechatSI');

const FONT_SIZE_OPTIONS = [
  { level: 'standard', label: '标准', size: '28rpx' },
  { level: 'large', label: '大', size: '36rpx' },
  { level: 'extra_large', label: '超大', size: '44rpx' }
];

Page({
  data: {
    messages: [],
    inputValue: '',
    scrollToId: '',
    inputFocus: false,
    chatId: '',
    chatType: 'general',
    drawerShow: false,
    allSessions: [],
    showFontPopover: false,
    fontSizeLevel: 'standard',
    fontSizeOptions: FONT_SIZE_OPTIONS,
    msgFontSize: '28rpx',
    voiceMode: false,
    isRecording: false,
    showRecordOverlay: false,
    recordCancelling: false,
    recordingTime: 0,
    consultTarget: { name: '本人', color: '#52c41a' },
    showTargetPicker: false,
    familyMembers: [],
    // [PRD-432] 当前会话绑定的咨询对象 family_member_id；本人=0
    currentConsultantId: 0,
    functionButtons: [],
    isSymptomLocked: false,
    // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查抽屉状态
    hscDrawerShow: false,
    hscTemplate: null,
    hscButton: null,
    hscBodyParts: [],
    hscDurations: [],
    hscSelectedPartId: null,
    hscSelectedPartIcon: '',
    hscSelectedPartName: '',
    hscCurrentSymptoms: [],
    hscSelectedSymptoms: [],
    hscSelectedDuration: '',
    hscLoading: false,
    hscErrorMsg: '',
    hscHighlightMissing: false,
    // [PRD-HSC-SYMPTOM-DESC 2026-05-16] 症状描述（选填，最多 50 字）
    symptomDescription: '',
    uploadPercent: -1,
    showUploadProgress: false,

    // Module 5: Drug recognize quick button
    showDrugCard: false,
    drugCardData: null,
    drugCardExpanded: false,
    drugImageUploading: false,
    drugIdentifyDisabled: false,

    // Type-lock & summary bar
    isTypeLocked: false,
    summaryBarText: '',
    lockedFamilyMemberId: null,

    // Drug identify card (顶部卡片，与 H5/Flutter 对齐)
    drugIdentifyMember: '',
    drugIdentifyDrugNames: '',
    drugIdentifyBannerVisible: false,

    // Module 6: SSE streaming
    streamingMsgId: '',
    streamingText: '',
    showCursor: false,
    isStreaming: false,

    // Module 7: Action buttons on latest AI reply
    latestAiMsgId: '',

    // Module 8: TTS
    isTtsPlaying: false,
    ttsMsgId: '',

    // [2026-04-23 报告分支] 报告解读/对比场景的顶部报告卡片
    reportList: [],

    // [2026-04-25] 报告解读异步化：失败状态
    interpretFailed: false,
    interpretPending: false,

    // [2026-04-25 PRD F5] OCR 详情默认隐藏 + 兜底入口
    firstAiMsgId: '',
    ocrDetailExpanded: false,
    ocrDetailLoaded: false,
    ocrDetailLoading: false,
    ocrDetailText: '',

    // [PRD-420 2026-05-08] 添加家庭成员弹层（与 H5 ConsultTargetPicker 对齐）
    showAddMember: false,
    relationTypes: [],
    selectedRelation: null,
    addForm: {
      nickname: '',
      gender: '',
      birthday: '',
      height: '',
      weight: '',
      medicalHistories: [],
      medicalOther: '',
      allergies: [],
      allergyOther: ''
    },
    addLoading: false,
    canSaveMember: false,
    todayStr: '',
    // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31]
    // 名额已满弹框 + 成员已添加成功🎉弹框
    showQuotaFull: false,
    quotaFullMax: 0,
    showAddedDialog: false,
    addedNickname: '',
    addedMemberId: '',
    medicalOptions: ['高血压', '糖尿病', '心脏病', '哮喘', '甲状腺疾病', '肝病', '肾病', '痛风'],
    allergyOptions: ['青霉素', '花粉', '海鲜', '牛奶', '尘螨', '坚果', '磺胺类', '头孢类'],

    // [PRD-425] AI 对话首页顶栏改造
    aiSignature: '小康',                // 顶栏标题（取 ai_chat.signature，默认"小康"）
    aiSignatureDisplay: '小康',         // 显示用（超 8 字截断）
    unreadCount: -1,                    // -1=不显示徽标；0=小红点；1~99=数字；>=100="99+"
    unreadDisplay: '',                  // 已格式化的徽标文本（如"5"、"99+"）

    // [PRD-AI-HOME-OPTIM-V4 2026-05-21]
    v4SwitchUndoVisible: false,         // 5 秒撤销横条可见
    v4SwitchUndoText: '',
    v4SwitchUndoSnapshot: null,         // 切换前快照
    v4RefreshPaused: false,             // 撤销期内暂停 60min 计时
    v4FloatingPanelOpen: false,         // 右下角小康头像悬浮球展开面板
    v4FloatingFirstGuideVisible: false, // 首次引导气泡
  },

  _recognizeManager: null,
  _recordTimer: null,
  _touchStartY: 0,
  _touchStartTime: 0,
  _discardNextResult: false,
  _btnCacheExpire: 0,
  _audioContext: null,
  _cursorTimer: null,
  _sseRequestTask: null,

  onLoad(options) {
    // [2026-04-23 报告分支] 新增 report_id / report_ids / auto_start 参数
    const { type = 'health_qa', chatId, question, member, family_member_id, constitution_type, summary, drug_name,
            report_id, report_ids, auto_start } = options;
    this.setData({ chatType: type, chatId: chatId || generateId() });

    const isSymptom = type === 'symptom' || type === 'symptom_check';
    if (isSymptom) {
      const relation = member ? decodeURIComponent(member).split('·')[0].trim() : '本人';
      this.setData({
        isSymptomLocked: true,
        consultTarget: { name: relation || '本人', color: getRelationColor(relation || '本人') }
      });
    }

    if (type === 'drug_identify' || type === 'constitution') {
      this.setData({ isTypeLocked: true });
      if (family_member_id) {
        this.setData({ lockedFamilyMemberId: family_member_id });
      }
      if (summary) {
        this.setData({ summaryBarText: decodeURIComponent(summary) });
      }
    }

    if (type === 'drug_identify') {
      const memberLabel = member ? decodeURIComponent(member) : '';
      const drugNamesStr = drug_name ? decodeURIComponent(drug_name) : '';
      this.setData({
        drugIdentifyMember: memberLabel,
        drugIdentifyDrugNames: drugNamesStr,
        drugIdentifyBannerVisible: !!(memberLabel || drugNamesStr)
      });
    }

    // [2026-04-23 报告分支] 报告解读/对比：锁定类型，加载报告卡片数据
    if (type === 'report_interpret' || type === 'report_compare') {
      this.setData({ isTypeLocked: true, chatType: type });
      // [Bug-04] URL 带 family_member_id 时立即把咨询人锁定为报告所属人
      if (family_member_id) {
        this._lockConsultTargetByMemberId(family_member_id);
      }
      this._loadReportsBrief({ chatId, reportId: report_id, reportIds: report_ids });
      if (auto_start === '1' && chatId) {
        // [2026-04-25] 报告解读异步订阅：进入页面即订阅后端 worker 推流
        this._pendingAutoStart = true;
        setTimeout(() => this._startReportInterpretSse(chatId), 300);
      }
    }

    wx.showShareMenu({ withShareTicket: true, menus: ['shareAppMessage', 'shareTimeline'] });

    const typeNames = {
      health_qa: '健康问答', general: '健康问答',
      symptom_check: '健康自查', symptom: '健康自查',
      tcm: '中医养生',
      drug_query: '用药参考', nutrition: '用药参考',
      drug_identify: '用药识别',
      constitution: '体质调理',
      // [2026-04-23 报告分支]
      report_interpret: 'AI 报告解读',
      report_compare: '报告对比'
    };
    wx.setNavigationBarTitle({ title: typeNames[type] || 'AI健康咨询' });

    this.addMessage('assistant', `您好！我是宾尼小康AI健康助手，很高兴为您提供${typeNames[type] || '健康'}咨询服务。\n\n请描述您的症状或健康问题，我会为您提供专业的分析和建议。`);

    this.loadFontSetting();
    this.loadFamilyMembers();
    this.loadFunctionButtons();
    // [PRD-425] 加载 AI 助手昵称（signature）与通知中心未读总数，用于顶栏徽标
    this.loadAiSignatureAndUnread();

    if (type === 'drug_identify' || type === 'constitution') {
      this._lockConsultTargetByMemberId(family_member_id);
    }

    if (question) {
      setTimeout(() => {
        this.setData({ inputValue: decodeURIComponent(question) });
        this.sendMessage();
      }, 500);
    }

    if (chatId) {
      this.loadChatHistory(chatId);
    }

    if (chatId && !isSymptom) {
      this.restoreSessionMember(chatId);
    }

    // [PRD-AI-HOME-OPTIM-V4 M3] 进入页面 800ms 后展示一次悬浮球引导气泡（仅首次）
    this.showV4FloatingFirstGuide();

    // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 消费 globalData.pendingQnChatMessages
    // 把后端 chat_messages 序列（card → text → followup_chips）按顺序注入到对话流
    try {
      const app = getApp();
      const pending = app && app.globalData && app.globalData.pendingQnChatMessages;
      if (pending && Array.isArray(pending.chat_messages) && pending.chat_messages.length > 0) {
        setTimeout(() => {
          this._injectQnChatMessages(pending);
          if (app && app.globalData) app.globalData.pendingQnChatMessages = null;
        }, 200);
      }
    } catch (e) {
      console.warn('[chat] consume pendingQnChatMessages failed', e);
    }
  },

  // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 注入问卷结果三连消息
  _injectQnChatMessages(pending) {
    const seq = pending.chat_messages || [];
    const fallbackCard = pending.result_card_payload || null;
    seq.forEach((m) => {
      if (m.type === 'questionnaire_result_card') {
        this.addMessage('assistant', '', {
          type: 'questionnaire_result_card',
          qnResultPayload: m.card || fallbackCard,
          qnAnswerId: pending.answer_id,
          qnQuestionnaireCode: pending.questionnaire_code,
        });
      } else if (m.type === 'text') {
        this.addMessage('assistant', m.text || '', {
          type: 'text',
          mainContent: m.text || '',
        });
      } else if (m.type === 'followup_chips') {
        this.addMessage('assistant', '', {
          type: 'followup_chips',
          followupChips: Array.isArray(m.chips) ? m.chips : [],
          chipsDisabled: false,
          qnAnswerId: pending.answer_id,
          qnQuestionnaireCode: pending.questionnaire_code,
        });
      }
    });
  },

  // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 卡片"查看详情"按钮点击
  onQnViewDetail(e) {
    const detail = e && e.detail ? e.detail : {};
    const payload = detail.payload || {};
    const target = detail.target || {};
    let mpPath = target.mp_path;
    if (!mpPath && payload.questionnaire_code === 'tcm_constitution') {
      const tcmId = payload.diagnosis_id || target.diagnosis_id || payload.result_id || payload.answer_id;
      if (tcmId) {
        mpPath = `/pages/tcm-constitution-result/index?id=${tcmId}`;
      }
    }
    if (mpPath) {
      wx.navigateTo({ url: mpPath });
    }
  },

  // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] chips 点击 → 调用 followup-chip 接口
  async onFollowupChipTap(e) {
    try {
      const msgId = e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.msgid;
      const chip = e && e.detail ? e.detail.chip : null;
      if (!chip) return;
      const messages = (this.data.messages || []).map((m) => {
        if (m.id === msgId) return Object.assign({}, m, { chipsDisabled: true });
        return m;
      });
      this.setData({ messages });
      // 拉到对应 message 上的 answer_id
      const cur = (this.data.messages || []).find((m) => m.id === msgId);
      const answerId = cur && cur.qnAnswerId;
      const r = await post('/api/questionnaire/followup-chip', {
        answer_id: answerId,
        chip_code: chip.code,
        chip_label: chip.label,
      }, { showLoading: false, suppressErrorToast: true });
      const aiText = (r && r.ai_text) || `本次回答结合您的档案。${chip.label} 暂无更详细资料。`;
      this.addMessage('assistant', aiText, { type: 'text', mainContent: aiText });
    } catch (err) {
      console.warn('[chat] followup-chip failed', err);
      wx.showToast({ title: '请求失败', icon: 'none' });
    }
  },

  onUnload() {
    if (this._recordTimer) {
      clearInterval(this._recordTimer);
      this._recordTimer = null;
    }
    this._recognizeManager = null;
    this._stopTts();
    // [PRD-AI-HOME-OPTIM-V4 2026-05-21] 清理撤销计时器
    if (this._v4UndoTimer) {
      clearTimeout(this._v4UndoTimer);
      this._v4UndoTimer = null;
    }
    if (this._cursorTimer) {
      clearInterval(this._cursorTimer);
      this._cursorTimer = null;
    }
    if (this._sseRequestTask) {
      this._sseRequestTask.abort();
      this._sseRequestTask = null;
    }
  },

  // ========================
  // Module 9: Share
  // ========================
  onShareAppMessage() {
    const chatId = this.data.chatId;
    return {
      title: '宾尼小康AI健康咨询',
      path: `/pages/chat/index?chatId=${chatId}&type=${this.data.chatType}`
    };
  },

  async shareToFriend(e) {
    // [PRD-433] 支持卡片底部按钮传入 data-msgid，否则回退到 latestAiMsgId
    const msgId = (e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.msgid) || this.data.latestAiMsgId;
    if (!msgId) {
      wx.showToast({ title: '暂无可分享的AI回复', icon: 'none' });
      return;
    }
    try {
      const res = await post('/api/chat/share', {
        session_id: this.data.chatId,
        message_id: msgId
      }, { showLoading: true, suppressErrorToast: false });

      const shareUrl = res.share_url || res.url || '';
      if (shareUrl) {
        wx.setClipboardData({
          data: shareUrl,
          success: () => wx.showToast({ title: '分享链接已复制', icon: 'success' })
        });
      } else {
        wx.showToast({ title: '分享成功', icon: 'success' });
      }
    } catch (err) {
      wx.showToast({ title: '生成分享链接失败', icon: 'none' });
    }
  },

  async generateShareImage() {
    wx.showLoading({ title: '生成图片中...', mask: true });
    try {
      const query = wx.createSelectorQuery();
      query.select('#share-canvas').fields({ node: true, size: true }).exec((res) => {
        if (!res || !res[0]) {
          wx.hideLoading();
          wx.showToast({ title: '生成失败', icon: 'none' });
          return;
        }
        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        const width = 600;
        const height = 800;
        canvas.width = width;
        canvas.height = height;

        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, width, height);

        ctx.fillStyle = '#52c41a';
        ctx.fillRect(0, 0, width, 80);
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 32px sans-serif';
        ctx.fillText('宾尼小康 AI健康咨询', 30, 52);

        ctx.fillStyle = '#333333';
        ctx.font = '24px sans-serif';
        const msgs = this.data.messages.filter(m => m.role !== 'loading').slice(-5);
        let y = 120;
        msgs.forEach(msg => {
          const prefix = msg.role === 'user' ? '我: ' : 'AI: ';
          const text = prefix + (msg.content || '').substring(0, 80);
          ctx.fillText(text, 30, y);
          y += 40;
        });

        ctx.fillStyle = '#999999';
        ctx.font = '20px sans-serif';
        ctx.fillText('长按识别小程序码查看完整对话', 30, height - 40);

        wx.canvasToTempFilePath({
          canvas,
          success: (imgRes) => {
            wx.hideLoading();
            wx.previewImage({ urls: [imgRes.tempFilePath] });
          },
          fail: () => {
            wx.hideLoading();
            wx.showToast({ title: '生成失败', icon: 'none' });
          }
        });
      });
    } catch (e) {
      wx.hideLoading();
      wx.showToast({ title: '生成失败', icon: 'none' });
    }
  },

  // ========================
  // Module 7: Copy / TTS / Share buttons
  // ========================
  copyMessage(e) {
    const msgId = e.currentTarget.dataset.msgid;
    const msg = this.data.messages.find(m => m.id === msgId);
    if (!msg) return;
    const text = msg.mainContent || msg.content || '';
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: '已复制', icon: 'success' })
    });
  },

  // ========================
  // Module 8: TTS
  // ========================
  toggleTts(e) {
    const msgId = e.currentTarget.dataset.msgid;
    if (this.data.isTtsPlaying && this.data.ttsMsgId === msgId) {
      this._stopTts();
      return;
    }
    const msg = this.data.messages.find(m => m.id === msgId);
    if (!msg) return;
    const text = msg.mainContent || msg.content || '';
    this._playTts(text, msgId);
  },

  async _playTts(text, msgId) {
    this._stopTts();

    if (!this._audioContext) {
      this._audioContext = wx.createInnerAudioContext();
      this._audioContext.onEnded(() => {
        this.setData({ isTtsPlaying: false, ttsMsgId: '' });
      });
      this._audioContext.onError(() => {
        this.setData({ isTtsPlaying: false, ttsMsgId: '' });
        wx.showToast({ title: '播报失败', icon: 'none' });
      });
    }

    this.setData({ isTtsPlaying: true, ttsMsgId: msgId });

    try {
      const res = await post('/api/tts/synthesize', {
        text: text.substring(0, 500)
      }, { showLoading: false, suppressErrorToast: true });
      const audioUrl = res && res.audio_url;
      if (!audioUrl) {
        this.setData({ isTtsPlaying: false, ttsMsgId: '' });
        wx.showToast({ title: '语音合成失败', icon: 'none' });
        return;
      }
      const app = getApp();
      this._audioContext.src = `${app.globalData.baseUrl}${audioUrl}`;
      this._audioContext.play();
    } catch (e) {
      this.setData({ isTtsPlaying: false, ttsMsgId: '' });
      wx.showToast({ title: '播报失败', icon: 'none' });
    }
  },

  _stopTts() {
    if (this._audioContext) {
      this._audioContext.stop();
    }
    this.setData({ isTtsPlaying: false, ttsMsgId: '' });
  },

  // ========================
  // Module 5: Drug recognize quick button
  // ========================
  onDrugRecognizeTap() {
    if (this.data.drugIdentifyDisabled) {
      wx.showToast({ title: '正在识别中，请稍候', icon: 'none' });
      return;
    }
    wx.showActionSheet({
      itemList: ['拍照', '从相册选择'],
      success: (res) => {
        const sourceType = res.tapIndex === 0 ? ['camera'] : ['album'];
        wx.chooseMedia({
          count: 1,
          mediaType: ['image'],
          sourceType,
          success: (mediaRes) => {
            const filePath = mediaRes.tempFiles[0].tempFilePath;
            this._uploadDrugImage(filePath);
          }
        });
      }
    });
  },

  async _uploadDrugImage(filePath) {
    try {
      filePath = await compressImage(filePath);
    } catch (_) { /* 压缩失败回退原图 */ }
    const sizeCheck = await checkFileSize(filePath, 'drug_identify');
    if (!sizeCheck.ok) {
      wx.showToast({ title: `文件大小超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
      return;
    }

    const id = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const messages = [...this.data.messages, { id, role: 'user', content: '', image: filePath, time, _ts: now.getTime(), references: [] }];
    this.setData({ messages, scrollToId: `msg-${id}`, drugImageUploading: true });

    const loadingId = this.addMessage('loading', '');

    try {
      const res = await uploadWithProgress('/api/ocr/recognize', filePath, {
        formData: { scene_name: '拍照识药' },
        onProgress: (percent) => this.setData({ uploadPercent: percent, showUploadProgress: true })
      });

      this.setData({ showUploadProgress: false, uploadPercent: -1, drugImageUploading: false });
      this.removeMessage(loadingId);

      const drugData = res.drugs || res.drug_info || null;
      if (drugData) {
        this.setData({ showDrugCard: true, drugCardData: drugData, drugCardExpanded: false });
      }

      const reply = (res && res.ai_reply) || (res && res.content) || '已收到药品图片，正在识别中...';
      this.addMessage('assistant', reply);
    } catch (e) {
      this.setData({ showUploadProgress: false, uploadPercent: -1, drugImageUploading: false });
      this.removeMessage(loadingId);
      this.addMessage('assistant', '药品识别失败，请重试。');
    }
  },

  toggleDrugCard() {
    this.setData({ drugCardExpanded: !this.data.drugCardExpanded });
  },

  // ========================
  // Module 6: SSE Streaming
  // ========================
  // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
  // 第三参数 extras：透传 intent / image_urls / button_id / button_type / report_meta
  // 给后端通用 SSE 分发器，使报告解读/识药按钮在同一会话内由对应引擎处理。
  _startSseStream(sessionId, content, extras) {
    const app = getApp();
    const url = `${app.globalData.baseUrl}/api/chat/sessions/${sessionId}/stream`;
    const token = app.globalData.token;

    const msgId = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;

    const prev = this.data.messages.length > 0 ? this.data.messages[this.data.messages.length - 1] : null;
    const showDivider = !prev || (prev._ts && (now.getTime() - prev._ts) > 5 * 60 * 1000);
    const messages = [...this.data.messages, {
      id: msgId, role: 'assistant', content: '', time,
      _ts: now.getTime(),
      references: [],
      showTimeDivider: !!showDivider,
      timeDividerText: time,
      isStreaming: true
    }];
    this.setData({
      messages,
      scrollToId: `msg-${msgId}`,
      streamingMsgId: msgId,
      streamingText: '',
      isStreaming: true,
      showCursor: false,
      latestAiMsgId: ''
    });

    // [PRD-433 F-10] 流式输出去光标：不再启动光标闪烁
    // this._startCursorBlink();

    let fullText = '';

    // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
    // 合并 SSE 通用 intent 协议字段（向后兼容：不传时行为不变）
    const _body = Object.assign(
      { content, session_type: this.data.chatType },
      extras && extras.intent ? { intent: extras.intent } : {},
      extras && extras.image_urls ? { image_urls: extras.image_urls } : {},
      extras && extras.button_id ? { button_id: extras.button_id } : {},
      extras && extras.button_type ? { button_type: extras.button_type } : {},
      extras && extras.report_meta ? { report_meta: extras.report_meta } : {},
      // [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
      // 后台 3 层按钮配置透传，前后端双保险解析
      extras && extras.ai_function_type ? { ai_function_type: extras.ai_function_type } : {},
      extras && extras.capture_purpose ? { capture_purpose: extras.capture_purpose } : {},
    );
    this._sseRequestTask = wx.request({
      url,
      method: 'POST',
      data: _body,
      header: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'Authorization': token ? `Bearer ${token}` : ''
      },
      enableChunked: true,
      responseType: 'text',
      success: () => {},
      fail: (err) => {
        if (err.errMsg && err.errMsg.indexOf('abort') >= 0) return;
        this._finishStreaming(msgId, fullText || '抱歉，网络出现了问题，请稍后重试。');
      }
    });

    if (this._sseRequestTask) {
      this._sseRequestTask.onChunkReceived((resp) => {
        try {
          const text = this._decodeChunk(resp.data);
          const lines = text.split('\n');
          for (const line of lines) {
            if (line.startsWith('data:')) {
              const dataStr = line.substring(5).trim();
              if (dataStr === '[DONE]') {
                this._finishStreaming(msgId, fullText);
                return;
              }
              try {
                const parsed = JSON.parse(dataStr);
                const delta = parsed.delta || parsed.content || parsed.text || '';
                if (delta) {
                  fullText += delta;
                  this._updateStreamingMessage(msgId, fullText);
                }
              } catch (pe) {
                fullText += dataStr;
                this._updateStreamingMessage(msgId, fullText);
              }
            }
          }
        } catch (e) {
          console.log('SSE chunk parse error', e);
        }
      });
    }
  },

  _decodeChunk(arrayBuffer) {
    if (typeof arrayBuffer === 'string') return arrayBuffer;
    try {
      const uint8 = new Uint8Array(arrayBuffer);
      let str = '';
      for (let i = 0; i < uint8.length; i++) {
        str += String.fromCharCode(uint8[i]);
      }
      return decodeURIComponent(escape(str));
    } catch (e) {
      return '';
    }
  },

  _updateStreamingMessage(msgId, text) {
    const idx = this.data.messages.findIndex(m => m.id === msgId);
    if (idx < 0) return;
    this.setData({
      [`messages[${idx}].content`]: text,
      streamingText: text,
      scrollToId: `msg-${msgId}`
    });
  },

  _finishStreaming(msgId, text) {
    if (this._cursorTimer) {
      clearInterval(this._cursorTimer);
      this._cursorTimer = null;
    }

    const idx = this.data.messages.findIndex(m => m.id === msgId);
    if (idx >= 0) {
      let parsed = {};
      if (text && text.includes('---disclaimer---')) {
        const parts = text.split('---disclaimer---');
        parsed.mainContent = parts[0].trim();
        parsed.disclaimer = parts[1] ? parts[1].trim() : '';
      }
      this.setData({
        [`messages[${idx}].content`]: text,
        [`messages[${idx}].isStreaming`]: false,
        [`messages[${idx}].mainContent`]: parsed.mainContent || '',
        [`messages[${idx}].disclaimer`]: parsed.disclaimer || '',
        streamingMsgId: '',
        streamingText: '',
        isStreaming: false,
        showCursor: false,
        latestAiMsgId: msgId
      });
    }

    this._sseRequestTask = null;
  },

  _startCursorBlink() {
    if (this._cursorTimer) clearInterval(this._cursorTimer);
    this._cursorTimer = setInterval(() => {
      this.setData({ showCursor: !this.data.showCursor });
    }, 500);
  },

  // ========================
  // Font settings
  // ========================
  async loadFontSetting() {
    try {
      const res = await get('/api/user/font-setting', {}, { showLoading: false, suppressErrorToast: true });
      const level = res && res.font_size_level ? res.font_size_level : 'standard';
      this.applyFontLevel(level);
    } catch (e) {
      this.applyFontLevel('standard');
    }
  },

  applyFontLevel(level) {
    const sizeMap = { standard: '28rpx', large: '36rpx', extra_large: '44rpx' };
    this.setData({
      fontSizeLevel: level,
      msgFontSize: sizeMap[level] || '28rpx'
    });
  },

  toggleFontPopover() {
    this.setData({ showFontPopover: !this.data.showFontPopover });
  },

  closeFontPopover() {
    this.setData({ showFontPopover: false });
  },

  async onFontOptionTap(e) {
    const level = e.currentTarget.dataset.level;
    if (level === this.data.fontSizeLevel) {
      this.setData({ showFontPopover: false });
      return;
    }
    this.applyFontLevel(level);
    this.setData({ showFontPopover: false });

    const labelMap = { standard: '标准', large: '大', extra_large: '超大' };
    wx.showToast({ title: `已切换为${labelMap[level]}字体`, icon: 'success' });

    try {
      await put('/api/user/font-setting', { font_size_level: level }, { showLoading: false, suppressErrorToast: true });
    } catch (e) {
      console.log('save font setting error', e);
    }
  },

  // ========================
  // Chat history & sessions
  // ========================
  async loadChatHistory(chatId) {
    try {
      // const res = await get(`/api/chat/${chatId}/messages`);
      // this.setData({ messages: res.data });
    } catch (e) {
      console.log('loadChatHistory error', e);
    }
  },

  async loadSessions() {
    try {
      const res = await get('/api/chat-sessions', { page: 1, page_size: 100 }, { showLoading: false, suppressErrorToast: true });
      const sessions = Array.isArray(res) ? res : (res.items || res.data || []);
      this.setData({ allSessions: sessions });
    } catch (e) {
      console.log('loadSessions error', e);
    }
  },

  openDrawer() {
    this.loadSessions();
    this.setData({ drawerShow: true });
  },

  onDrawerClose() {
    this.setData({ drawerShow: false });
  },

  onSessionTap(e) {
    const { session } = e.detail;
    this.setData({ drawerShow: false });

    const typeNames = {
      health_qa: '健康问答', general: '健康问答',
      symptom_check: '健康自查', symptom: '健康自查',
      tcm: '中医养生',
      drug_query: '用药参考', nutrition: '用药参考'
    };
    const type = session.session_type || 'health_qa';
    this.setData({
      chatId: session.id,
      chatType: type,
      messages: [],
      latestAiMsgId: ''
    });
    wx.setNavigationBarTitle({ title: typeNames[type] || 'AI健康咨询' });
    this.addMessage('assistant', `您好！我是宾尼小康AI健康助手，很高兴为您提供${typeNames[type] || '健康'}咨询服务。\n\n请描述您的症状或健康问题，我会为您提供专业的分析和建议。`);
    this.loadChatHistory(session.id);
  },

  onDrawerNewChat() {
    this.setData({ drawerShow: false });
    const typeNames = {
      health_qa: '健康问答', general: '健康问答',
      symptom_check: '健康自查', symptom: '健康自查',
      tcm: '中医养生',
      drug_query: '用药参考', nutrition: '用药参考'
    };
    const type = 'health_qa';
    this.setData({
      chatId: generateId(),
      chatType: type,
      messages: [],
      latestAiMsgId: ''
    });
    wx.setNavigationBarTitle({ title: typeNames[type] });
    this.addMessage('assistant', `您好！我是宾尼小康AI健康助手，很高兴为您提供${typeNames[type]}咨询服务。\n\n请描述您的症状或健康问题，我会为您提供专业的分析和建议。`);
  },

  onDrawerRefresh() {
    this.loadSessions();
  },

  onDrawerShare(e) {
    const { session, shareToken, shareUrl } = e.detail;
    wx.setClipboardData({
      data: shareUrl || shareToken,
      success: () => wx.showToast({ title: '分享链接已复制', icon: 'success' })
    });
  },

  // ========================
  // Family members
  // ========================
  async loadFamilyMembers() {
    try {
      const res = await get('/api/family/members', {}, { showLoading: false, suppressErrorToast: true });
      const items = res && res.items ? res.items : [];
      const members = items.map(m => ({
        id: m.id,
        name: m.relation_type_name || m.nickname || '本人',
        color: getRelationColor(m.relation_type_name || ''),
        is_self: m.is_self
      }));
      if (!members.some(m => m.is_self)) {
        members.unshift({ id: 0, name: '本人', color: '#52c41a', is_self: true });
      }
      this.setData({ familyMembers: members });
    } catch (e) {
      console.log('loadFamilyMembers error', e);
    }
  },

  async loadFunctionButtons() {
    const now = Date.now();
    if (this._btnCacheExpire > now && this.data.functionButtons.length) return;
    try {
      const res = await get('/api/chat/function-buttons', {}, { showLoading: false, suppressErrorToast: true });
      const buttons = Array.isArray(res) ? res : (res.items || res.data || []);
      // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 过滤逻辑改为按 is_recommended OR is_capsule（任一开关开启即可见）
      // 兜底：若后端新字段都没下发（老接口），退化为按 is_enabled 过滤
      const hasNewFields = buttons.some((b) => typeof b.is_recommended === 'boolean' || typeof b.is_capsule === 'boolean');
      const filtered = hasNewFields
        ? buttons.filter((b) => !!b.is_recommended || !!b.is_capsule)
        : buttons.filter((b) => b.is_enabled);
      this.setData({ functionButtons: filtered });
      this._btnCacheExpire = now + 5 * 60 * 1000;
    } catch (e) {
      console.log('loadFunctionButtons error', e);
    }
  },

  // [PRD-425] 加载 AI 助手昵称（ai_chat.signature）与通知中心未读总数
  async loadAiSignatureAndUnread() {
    // 1) 获取 signature；接口异常 → 兜底"小康"
    try {
      const res = await get('/api/ai-home-config', {}, { showLoading: false, suppressErrorToast: true });
      const cfg = res?.data?.config || res?.config || res || {};
      const sig = (cfg?.ai_chat?.signature || '').trim() || '小康';
      const display = sig.length > 8 ? sig.slice(0, 8) + '…' : sig;
      this.setData({ aiSignature: sig, aiSignatureDisplay: display });
    } catch (e) {
      this.setData({ aiSignature: '小康', aiSignatureDisplay: '小康' });
    }

    // 2) 获取通知中心未读总数；接口异常 → 不显示徽标（unreadCount = -1）
    try {
      const res = await get('/api/v1/notifications/unread-count', {}, { showLoading: false, suppressErrorToast: true });
      const cnt = (res?.data?.unreadCount ?? res?.unreadCount);
      if (typeof cnt === 'number' && cnt >= 0) {
        const display = cnt >= 100 ? '99+' : String(cnt);
        this.setData({ unreadCount: cnt, unreadDisplay: display });
      }
    } catch (e) {
      // 静默：保持 unreadCount = -1，前端不显示徽标
    }
  },

  // [PRD-425] 点击顶栏未读徽标 → 跳转通知中心
  onTopBarBadgeTap() {
    if (this.data.unreadCount < 0) return;
    wx.navigateTo({ url: '/pages/messages/index' }).catch(() => {
      // 如果通知中心路径不存在则吞掉错误
    });
  },

  onFunctionButtonTap(e) {
    const btn = e.currentTarget.dataset.button;
    if (!btn) return;
    const params = btn.params || {};

    switch (btn.button_type) {
      case 'digital_human_call':
        wx.navigateTo({
          url: `/pages/digital-human-call/index?digitalHumanId=${params.digital_human_id || ''}&sessionId=${this.data.chatId}`
        });
        break;

      case 'photo_upload':
        wx.chooseMedia({
          count: 1,
          mediaType: ['image'],
          sourceType: ['album', 'camera'],
          success: (res) => {
            const filePath = res.tempFiles[0].tempFilePath;
            this._uploadAndSendImage(filePath);
          }
        });
        break;

      // [PRD-PROMPT-CONFIG-V1 2026-05-14] 报告解读专属按钮：复用拍照上传交互，
      // 上传成功后调用 /api/report-interpret/start 跳转到对话页
      case 'report_interpret':
        wx.chooseMedia({
          count: 1,
          mediaType: ['image'],
          sourceType: ['album', 'camera'],
          success: (res) => {
            const filePath = res.tempFiles[0].tempFilePath;
            this._uploadAndStartReportInterpret(filePath, btn);
          }
        });
        break;

      // [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
      // 新体系 ai_function 按钮分发：根据 ai_function_type + capture_purpose 路由。
      // 由 resolveButtonIntent 统一映射到专用引擎，本入口在小程序内点击新体系按钮时被命中。
      case 'ai_function': {
        const _afType = btn.ai_function_type || '';
        const _cp = btn.capture_purpose || '';
        // 图像采集类（image_capture / 老 photo_upload）：复用拍照上传链路
        if (_afType === 'image_capture' || _afType === 'photo_upload'
            || _afType === 'report_interpret' || _afType === 'medicine_recognize') {
          wx.chooseMedia({
            count: 1,
            mediaType: ['image'],
            sourceType: ['album', 'camera'],
            success: (res) => {
              const filePath = res.tempFiles[0].tempFilePath;
              this._uploadAndStartReportInterpret(filePath, btn);
            }
          });
        } else if (_afType === 'ai_dialog_trigger' || _afType === 'quick_ask') {
          // 触发预设话术
          const triggerMsg = (btn.preset_prompt || btn.auto_user_message || params.message || btn.name || '').trim();
          if (triggerMsg) {
            this.setData({ inputValue: triggerMsg });
            this.sendMessage();
          }
        } else if (_afType === 'file_upload') {
          wx.chooseMessageFile({
            count: 1,
            type: 'file',
            success: (res) => {
              const filePath = res.tempFiles[0].path;
              const fileName = res.tempFiles[0].name;
              this._uploadAndSendFile(filePath, fileName);
            }
          });
        } else {
          // 兜底：未识别子类型，按拍照上传处理
          wx.chooseMedia({
            count: 1,
            mediaType: ['image'],
            sourceType: ['album', 'camera'],
            success: (res) => {
              const filePath = res.tempFiles[0].tempFilePath;
              this._uploadAndStartReportInterpret(filePath, btn);
            }
          });
        }
        // 顺带保留 capture_purpose 引用，避免编译器警告（也方便后续扩展）
        void _cp;
        break;
      }

      case 'file_upload':
        wx.chooseMessageFile({
          count: 1,
          type: 'file',
          success: (res) => {
            const filePath = res.tempFiles[0].path;
            const fileName = res.tempFiles[0].name;
            this._uploadAndSendFile(filePath, fileName);
          }
        });
        break;

      case 'ai_dialog_trigger': {
        const triggerMsg = params.message || btn.name;
        this.setData({ inputValue: triggerMsg });
        this.sendMessage();
        break;
      }

      case 'drug_identify':
        this._handleDrugIdentifyButton(btn);
        break;

      case 'external_link':
        if (params.url) {
          if (params.url.startsWith('/pages/')) {
            wx.navigateTo({ url: params.url });
          } else {
            wx.navigateTo({ url: `/pages/webview/index?url=${encodeURIComponent(params.url)}` });
          }
        }
        break;

      // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查
      case 'health_self_check':
        this.openHealthSelfCheckDrawer(btn);
        break;

      default:
        wx.showToast({ title: '暂不支持该功能', icon: 'none' });
    }
  },

  // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 打开健康自查抽屉，加载模板
  openHealthSelfCheckDrawer(btn) {
    const tplId = btn.health_check_template_id;
    if (!tplId) {
      wx.showToast({ title: '该功能暂不可用，请联系管理员', icon: 'none' });
      return;
    }
    this.setData({
      hscDrawerShow: true,
      hscButton: btn,
      hscLoading: true,
      hscErrorMsg: '',
      hscTemplate: null,
      hscBodyParts: [],
      hscDurations: [],
      hscSelectedPartId: null,
      hscSelectedPartIcon: '',
      hscSelectedPartName: '',
      hscCurrentSymptoms: [],
      hscSelectedSymptoms: [],
      hscSelectedDuration: '',
      hscHighlightMissing: false,
      symptomDescription: '',
    });
    get(`/api/health-self-check/template/${tplId}`).then((res) => {
      const data = (res && res.data) ? res.data : res;
      if (!data || !data.enabled) {
        this.setData({ hscLoading: false, hscErrorMsg: '该功能暂不可用，请联系管理员' });
        return;
      }
      this.setData({
        hscLoading: false,
        hscTemplate: data,
        hscBodyParts: data.body_parts_detail || [],
        hscDurations: data.duration_options || [],
      });
    }).catch(() => {
      this.setData({ hscLoading: false, hscErrorMsg: '模板加载失败，请稍后重试' });
    });
  },

  onHscClose() {
    this.setData({ hscDrawerShow: false, symptomDescription: '' });
  },

  // [PRD-HSC-SYMPTOM-DESC 2026-05-16] 症状描述输入回调（input 原生 maxlength=50 兜底）
  onHscSymptomDescInput(e) {
    let v = (e && e.detail && typeof e.detail.value === 'string') ? e.detail.value : '';
    if (v.length > 50) v = v.slice(0, 50);
    this.setData({ symptomDescription: v });
  },

  onHscPickPart(e) {
    const id = e.currentTarget.dataset.id;
    const part = (this.data.hscBodyParts || []).find((p) => p.id === id);
    if (!part) return;
    this.setData({
      hscSelectedPartId: id,
      hscSelectedPartName: part.name,
      hscSelectedPartIcon: part.icon || '',
      hscCurrentSymptoms: part.symptoms || [],
      hscSelectedSymptoms: [],
    });
  },

  onHscToggleSymptom(e) {
    const sym = e.currentTarget.dataset.sym;
    const arr = (this.data.hscSelectedSymptoms || []).slice();
    const idx = arr.indexOf(sym);
    if (idx >= 0) arr.splice(idx, 1); else arr.push(sym);
    this.setData({ hscSelectedSymptoms: arr });
  },

  onHscPickDuration(e) {
    this.setData({ hscSelectedDuration: e.currentTarget.dataset.d });
  },

  onHscSubmit() {
    const { hscSelectedPartId, hscSelectedSymptoms, hscSelectedDuration,
      hscBodyParts, hscButton, hscTemplate } = this.data;
    if (!hscSelectedPartId || !hscSelectedSymptoms.length || !hscSelectedDuration) {
      this.setData({ hscHighlightMissing: true });
      wx.showToast({ title: '请完成全部三项后再开始分析', icon: 'none' });
      return;
    }
    const part = (hscBodyParts || []).find((p) => p.id === hscSelectedPartId);
    if (!part || !hscButton || !hscTemplate) return;
    // [BUG-FIX 2026-05-16] 拆分展示模型与接口请求模型：
    // - displayPayload：用于卡片气泡展示（保留 body_part 对象、archive_name 等）
    // - requestBody：用于发给后端（仅 body_part_id 整数，符合 HealthSelfCheckStartRequest schema）
    const archiveName = this.data.consultTarget && this.data.consultTarget.name ? this.data.consultTarget.name : '本人';
    // [PRD-HSC-SYMPTOM-DESC 2026-05-16] 症状描述（选填）一并带上
    const symptomDescription = (this.data.symptomDescription || '').trim();
    const displayPayload = {
      template_id: hscTemplate.id,
      button_id: hscButton.id,
      archive_id: null,
      archive_name: archiveName,
      archive_age: null,
      archive_gender: null,
      body_part: { id: part.id, name: part.name, icon: part.icon || '' },
      symptoms: hscSelectedSymptoms,
      duration: hscSelectedDuration,
      symptomDescription: symptomDescription,
    };
    const requestBody = {
      template_id: hscTemplate.id,
      button_id: hscButton.id,
      archive_id: null,
      body_part_id: part.id,
      symptoms: hscSelectedSymptoms,
      duration: hscSelectedDuration,
      symptom_description: symptomDescription || null,
    };
    this.setData({ hscDrawerShow: false, symptomDescription: '' });
    const ts = Date.now();
    const cardMsg = {
      id: `hsc-${ts}`,
      role: 'user',
      type: 'health_self_check_card',
      content: '',
      hscPayload: {
        archive_name: displayPayload.archive_name,
        archive_age: displayPayload.archive_age,
        archive_gender: displayPayload.archive_gender,
        body_part: displayPayload.body_part,
        symptoms: displayPayload.symptoms,
        duration: displayPayload.duration,
        symptomDescription: displayPayload.symptomDescription,
        button_id: displayPayload.button_id,
        template_id: displayPayload.template_id,
      },
      created_at: new Date().toISOString(),
    };
    const aiPlaceholder = {
      id: `a-hsc-${ts}`,
      role: 'assistant',
      type: 'text',
      content: '',
      isLoading: true,
      created_at: new Date().toISOString(),
    };
    const messages = (this.data.messages || []).concat([cardMsg, aiPlaceholder]);
    this.setData({ messages, scrollToId: aiPlaceholder.id });
    this._startHscStream(requestBody, aiPlaceholder.id);
  },

  // [PRD-HSC-SSE 2026-05-16] SSE 流式分析（带兜底）
  _startHscStream(requestBody, aiMsgId) {
    const app = getApp();
    const baseUrl = (app && app.globalData && app.globalData.baseUrl) || '';
    const token = (app && app.globalData && app.globalData.token) || '';
    const header = {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
      'Client-Type': 'miniprogram-user',
      'X-Client-Type': 'miniprogram-user',
      'X-Client-Source': 'miniprogram-customer',
    };
    if (token) header['Authorization'] = `Bearer ${token}`;

    // 字节缓冲（多 chunk 拼接，避免中文 UTF-8 边界截断）+ 已 decode 文本缓冲（按 \n\n 分包）
    let byteBuf = new Uint8Array(0);
    let textBuf = '';
    let accumulated = '';
    let streamStarted = false;
    let finished = false;

    const that = this;

    const concatU8 = (a, b) => {
      const out = new Uint8Array(a.length + b.length);
      out.set(a, 0);
      out.set(b, a.length);
      return out;
    };

    // UTF-8 解码（小程序无 TextDecoder；用兼容实现）
    const u8ToString = (u8) => {
      try {
        if (typeof TextDecoder !== 'undefined') {
          return new TextDecoder('utf-8').decode(u8);
        }
      } catch (_) { /* ignore */ }
      // 退路 1：wx.arrayBufferToBase64 + decodeURIComponent(escape(atob(...)))
      try {
        const ab = u8.buffer.slice(u8.byteOffset, u8.byteOffset + u8.byteLength);
        const b64 = wx.arrayBufferToBase64(ab);
        // base64 -> binary string
        const bin = (function (s) {
          const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
          let str = '';
          s = s.replace(/=+$/, '');
          for (let i = 0, bc = 0, bs = 0; i < s.length; i++) {
            const c = chars.indexOf(s.charAt(i));
            if (c < 0) continue;
            bs = bc % 4 ? bs * 64 + c : c;
            if (bc++ % 4) str += String.fromCharCode(255 & (bs >> ((-2 * bc) & 6)));
          }
          return str;
        })(b64);
        return decodeURIComponent(escape(bin));
      } catch (_) {
        let s = '';
        for (let i = 0; i < u8.length; i++) s += String.fromCharCode(u8[i]);
        return s;
      }
    };

    // 找到尾部不完整 UTF-8 序列的起始位置，确保 decode 不截断多字节
    const findSafeEnd = (u8) => {
      let i = u8.length;
      const max = Math.min(4, u8.length);
      for (let k = 1; k <= max; k++) {
        const b = u8[u8.length - k];
        if ((b & 0x80) === 0) { return i; } // ASCII，安全
        if ((b & 0xC0) === 0xC0) {
          // 多字节序列首字节
          let expected = 0;
          if ((b & 0xE0) === 0xC0) expected = 2;
          else if ((b & 0xF0) === 0xE0) expected = 3;
          else if ((b & 0xF8) === 0xF0) expected = 4;
          if (k < expected) return u8.length - k; // 尾部不完整
          return i;
        }
      }
      return i;
    };

    const parseEvent = (raw) => {
      // raw 形如 "event: delta\ndata: {...}"
      let type = 'message';
      const dataLines = [];
      const lines = raw.split('\n');
      for (const line of lines) {
        if (!line) continue;
        if (line.startsWith('event:')) {
          type = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim());
        }
      }
      const dataStr = dataLines.join('\n');
      let data = null;
      if (dataStr) {
        try { data = JSON.parse(dataStr); } catch (_) { data = dataStr; }
      }
      return { type, data };
    };

    const updateAiContent = (text, loading) => {
      const msgs = (that.data.messages || []).map((m) =>
        m.id === aiMsgId ? { ...m, content: text, isLoading: !!loading } : m,
      );
      that.setData({ messages: msgs });
    };

    const handleEvent = (evt) => {
      if (!evt || !evt.type) return;
      if (evt.type === 'meta') {
        streamStarted = true;
        // meta 不强制处理
      } else if (evt.type === 'delta') {
        streamStarted = true;
        const c = (evt.data && typeof evt.data.content === 'string') ? evt.data.content : '';
        if (c) {
          accumulated += c;
          updateAiContent(accumulated, true);
        }
      } else if (evt.type === 'done') {
        finished = true;
        const full = (evt.data && typeof evt.data.full_content === 'string')
          ? evt.data.full_content
          : accumulated;
        accumulated = full;
        updateAiContent(full || '分析失败，请稍后重试', false);
      }
    };

    const fallbackToSync = () => {
      if (finished) return;
      // 走原同步接口 + 伪流式 reveal，UX 不退化
      post('/api/health-self-check/start', requestBody, { showLoading: false, suppressErrorToast: true }).then((res) => {
        const data = (res && res.data) ? res.data : res;
        const fullText = (data && data.ai_content) || '';
        if (!fullText) {
          updateAiContent('分析失败，请稍后重试', false);
          finished = true;
          return;
        }
        // 伪流式：每 ~40ms 追加若干字符
        let idx = 0;
        const step = Math.max(2, Math.ceil(fullText.length / 60));
        const timer = setInterval(() => {
          idx = Math.min(fullText.length, idx + step);
          updateAiContent(fullText.slice(0, idx), idx < fullText.length);
          if (idx >= fullText.length) {
            clearInterval(timer);
            finished = true;
          }
        }, 40);
      }).catch(() => {
        updateAiContent('分析失败，请点击重试', false);
        finished = true;
      });
    };

    let task = null;
    try {
      task = wx.request({
        url: baseUrl + '/api/health-self-check/start-stream',
        method: 'POST',
        data: requestBody,
        header,
        enableChunked: true,
        responseType: 'arraybuffer',
        success(res) {
          // 流式场景下 success 里 data 通常无用；判断状态码即可
          if (res && res.statusCode && res.statusCode !== 200) {
            if (!streamStarted) fallbackToSync();
            else if (!finished) updateAiContent(accumulated || '分析失败，请稍后重试', false);
          } else if (!finished) {
            // 走到这里说明连接结束但没收到 done：用已累计的内容收尾
            if (accumulated) updateAiContent(accumulated, false);
            else if (!streamStarted) fallbackToSync();
            else updateAiContent('分析失败，请稍后重试', false);
            finished = true;
          }
        },
        fail() {
          if (!streamStarted && !finished) fallbackToSync();
          else if (!finished) {
            updateAiContent(accumulated || '分析失败，请稍后重试', false);
            finished = true;
          }
        },
      });
      if (task && typeof task.onChunkReceived === 'function') {
        task.onChunkReceived((resp) => {
          try {
            const ab = resp && resp.data;
            if (!ab) return;
            const u8 = new Uint8Array(ab);
            byteBuf = concatU8(byteBuf, u8);
            // 仅 decode 到安全边界，避免 UTF-8 截断
            const safe = findSafeEnd(byteBuf);
            if (safe > 0) {
              const chunkText = u8ToString(byteBuf.slice(0, safe));
              byteBuf = byteBuf.slice(safe);
              textBuf += chunkText;
            }
            // 按 \n\n 拆 event
            let sepIdx;
            while ((sepIdx = textBuf.indexOf('\n\n')) !== -1) {
              const rawEvent = textBuf.slice(0, sepIdx);
              textBuf = textBuf.slice(sepIdx + 2);
              if (rawEvent.trim()) {
                handleEvent(parseEvent(rawEvent));
              }
            }
          } catch (_) { /* ignore chunk parse error */ }
        });
      } else {
        // 基础库不支持 onChunkReceived → 直接兜底
        try { task && task.abort && task.abort(); } catch (_) { /* ignore */ }
        fallbackToSync();
      }
    } catch (_) {
      fallbackToSync();
    }
  },

  _handleDrugIdentifyButton(btn) {
    if (this.data.drugIdentifyDisabled) {
      wx.showToast({ title: '正在识别中，请稍候', icon: 'none' });
      return;
    }
    const params = btn.params || {};
    const tipText = params.photo_tip_text || '请拍摄药品包装、说明书等清晰照片';
    const maxCount = params.max_photo_count || 5;

    wx.showModal({
      title: '拍照识药',
      content: tipText,
      showCancel: false,
      confirmText: '我知道了',
      success: () => {
        wx.showActionSheet({
          itemList: ['拍照', '从相册选择'],
          success: (res) => {
            if (res.tapIndex === 0) {
              wx.chooseMedia({
                count: 1,
                mediaType: ['image'],
                sourceType: ['camera'],
                success: (mediaRes) => {
                  this._processDrugIdentifyImages(mediaRes.tempFiles.map(f => f.tempFilePath));
                }
              });
            } else {
              wx.chooseMedia({
                count: maxCount,
                mediaType: ['image'],
                sourceType: ['album'],
                success: (mediaRes) => {
                  this._processDrugIdentifyImages(mediaRes.tempFiles.map(f => f.tempFilePath));
                }
              });
            }
          }
        });
      }
    });
  },

  async _processDrugIdentifyImages(filePaths) {
    if (!filePaths || !filePaths.length) return;
    this.setData({ drugIdentifyDisabled: true });

    const compressed = [];
    for (const p of filePaths) {
      try {
        compressed.push(await compressImage(p));
      } catch (_) {
        compressed.push(p);
      }
    }
    filePaths = compressed;

    const id = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const messages = [...this.data.messages, { id, role: 'user', content: `[拍照识药] 共${filePaths.length}张`, image: filePaths[0], time, _ts: now.getTime(), references: [] }];
    this.setData({ messages, scrollToId: `msg-${id}` });

    const loadingId = this.addMessage('loading', '');
    let allOcrText = '';

    try {
      for (let i = 0; i < filePaths.length; i++) {
        const sizeCheck = await checkFileSize(filePaths[i], 'drug_identify');
        if (!sizeCheck.ok) {
          wx.showToast({ title: `第${i + 1}张图片超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
          continue;
        }
        const ocrRes = await uploadWithProgress('/api/ocr/recognize', filePaths[i], {
          formData: { scene_name: '拍照识药' },
          onProgress: (percent) => {
            const overall = Math.round(((i + percent / 100) / filePaths.length) * 100);
            this.setData({ uploadPercent: overall, showUploadProgress: true });
          }
        });
        const text = (ocrRes && (ocrRes.text || ocrRes.ocr_text || ocrRes.content)) || '';
        if (text) allOcrText += (allOcrText ? '\n' : '') + text;
      }
      this.setData({ showUploadProgress: false, uploadPercent: -1 });

      if (!allOcrText) {
        this.removeMessage(loadingId);
        this.addMessage('assistant', '未能识别到药品文字信息，请拍摄更清晰的照片重试。');
        this.setData({ drugIdentifyDisabled: false });
        return;
      }

      this.removeMessage(loadingId);

      const analyzeLoadingId = this.addMessage('loading', '');
      const analyzeRes = await post('/api/drug-identify/analyze', {
        ocr_text: allOcrText,
        session_id: this.data.chatId,
        family_member_id: this.data.lockedFamilyMemberId || undefined
      }, { showLoading: false, suppressErrorToast: true });

      this.removeMessage(analyzeLoadingId);

      const drugData = analyzeRes && (analyzeRes.drugs || analyzeRes.drug_info);
      if (drugData) {
        this.setData({ showDrugCard: true, drugCardData: drugData, drugCardExpanded: false });
      }

      const reply = (analyzeRes && (analyzeRes.ai_reply || analyzeRes.content)) || '药品信息已识别，请查看上方药品卡片。';
      this.addMessage('assistant', reply);

      if (analyzeRes && analyzeRes.follow_up_question) {
        setTimeout(() => {
          this.setData({ inputValue: analyzeRes.follow_up_question });
          this.sendMessage();
        }, 1000);
      }
    } catch (e) {
      this.setData({ showUploadProgress: false, uploadPercent: -1 });
      this.removeMessage(loadingId);
      this.addMessage('assistant', '药品识别失败，请重试。');
    } finally {
      this.setData({ drugIdentifyDisabled: false });
    }
  },

  // [2026-04-25] 报告解读异步订阅：进入 report_interpret/report_compare 页面时调用
  _startReportInterpretSse(sessionId) {
    const app = getApp();
    const baseUrl = app.globalData.baseUrl;
    const token = app.globalData.token;
    const url = `${baseUrl}/api/report/interpret/session/${sessionId}/stream?auto_start=1`;

    this.setData({ interpretPending: true, interpretFailed: false });

    const msgId = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const prevR = this.data.messages.length > 0 ? this.data.messages[this.data.messages.length - 1] : null;
    const showDividerR = !prevR || (prevR._ts && (now.getTime() - prevR._ts) > 5 * 60 * 1000);
    const messages = [...this.data.messages, {
      id: msgId, role: 'assistant', content: '', time,
      _ts: now.getTime(),
      references: [],
      showTimeDivider: !!showDividerR,
      timeDividerText: time,
      isStreaming: true
    }];
    this.setData({
      messages,
      scrollToId: `msg-${msgId}`,
      streamingMsgId: msgId,
      streamingText: '',
      isStreaming: true,
      showCursor: false,
      // [2026-04-25 PRD F5] 记录第一条 AI 解读消息 id，用于在该条消息底部挂载 OCR 详情入口
      firstAiMsgId: this.data.firstAiMsgId || msgId,
      // 重置 OCR 详情状态（新解读未完成前不展示入口）
      ocrDetailExpanded: false,
      ocrDetailLoaded: false,
      ocrDetailLoading: false,
      ocrDetailText: ''
    });
    // [PRD-433 F-10] 流式输出去光标
    // this._startCursorBlink();

    let fullText = '';
    let currentEvent = '';
    let leftover = '';

    const task = wx.request({
      url,
      method: 'GET',
      header: {
        'Accept': 'text/event-stream',
        'Authorization': token ? `Bearer ${token}` : ''
      },
      enableChunked: true,
      responseType: 'text',
      success: () => {},
      fail: (err) => {
        if (err.errMsg && err.errMsg.indexOf('abort') >= 0) return;
        this._finishStreaming(msgId, fullText || '网络异常，请稍后重试');
        this.setData({ interpretPending: false });
      }
    });

    this._sseRequestTask = task;

    if (task) {
      task.onChunkReceived((resp) => {
        try {
          const text = leftover + this._decodeChunk(resp.data);
          const lines = text.split('\n');
          leftover = lines.pop() || '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7).trim();
              continue;
            }
            if (!line.startsWith('data:')) continue;
            const dataStr = line.startsWith('data: ') ? line.slice(6) : line.slice(5).trim();
            let data = {};
            try { data = JSON.parse(dataStr); } catch { data = { raw: dataStr }; }

            if (currentEvent === 'message.delta' || data.type === 'delta') {
              const d = data.delta || data.content || '';
              if (d) {
                fullText += d;
                this._updateStreamingMessage(msgId, fullText);
              }
            } else if (currentEvent === 'message.done' || data.type === 'done') {
              const final = data.content || fullText;
              fullText = final;
              this._updateStreamingMessage(msgId, fullText);
            } else if (currentEvent === 'status') {
              if (data.interpret_status === 'failed') {
                this.setData({ interpretFailed: true, interpretPending: false });
              } else if (data.interpret_status === 'done') {
                this.setData({ interpretFailed: false, interpretPending: false });
              }
            } else if (currentEvent === 'error' || data.type === 'error') {
              this.setData({ interpretFailed: true, interpretPending: false });
            } else if (currentEvent === 'done') {
              this._finishStreaming(msgId, fullText);
              this.setData({ interpretPending: false });
            }
            currentEvent = '';
          }
        } catch (e) {
          console.log('[report SSE] parse error', e);
        }
      });
    }
  },

  // [2026-04-25 PRD F5-3] 切换 OCR 详情展开/收起
  async onToggleOcrDetail() {
    const sid = this.data.chatId;
    if (!sid) return;
    const next = !this.data.ocrDetailExpanded;
    this.setData({ ocrDetailExpanded: next });
    // [F5-7] 埋点（不阻塞）
    try {
      post('/api/report/interpret/ocr-detail/click', {
        session_id: Number(sid),
        action: next ? 'view' : 'collapse'
      }, { showLoading: false, suppressErrorToast: true });
    } catch (_) { /* ignore */ }
    if (!next) return;
    if (this.data.ocrDetailLoaded || this.data.ocrDetailLoading) return;
    this.setData({ ocrDetailLoading: true });
    try {
      const res = await get(`/api/report/interpret/session/${sid}/ocr-detail`, {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      this.setData({
        ocrDetailText: String(data.ocr_text || ''),
        ocrDetailLoaded: true
      });
    } catch (_) {
      this.setData({ ocrDetailText: '' });
    } finally {
      this.setData({ ocrDetailLoading: false });
    }
  },

  // [2026-04-25] 用户点"重新解读"按钮
  async onRetryInterpret() {
    const sid = this.data.chatId;
    if (!sid) return;
    try {
      await post(`/api/report/interpret/session/${sid}/retry`, {}, { showLoading: true });
      // 清理失败状态 + 重新订阅
      this.setData({ interpretFailed: false, messages: this.data.messages.filter(m => !m.isStreaming) });
      this._startReportInterpretSse(sid);
    } catch (e) {
      wx.showToast({ title: e.message || '重试失败，请稍后再试', icon: 'none' });
    }
  },

  // [2026-04-23 报告分支] 加载报告简要信息，用于顶部报告卡片
  async _loadReportsBrief({ chatId, reportId, reportIds }) {
    try {
      let reports = [];
      if (chatId) {
        const sess = await get(`/api/chat/sessions/${chatId}`, {}, { showLoading: false, suppressErrorToast: true });
        if (sess && Array.isArray(sess.reports_brief)) {
          reports = sess.reports_brief;
        }
      } else if (reportId) {
        const rep = await get(`/api/checkup/reports/${reportId}`, {}, { showLoading: false, suppressErrorToast: true });
        if (rep) reports = [rep];
      } else if (reportIds) {
        const ids = String(reportIds).split(',').map(s => parseInt(s, 10)).filter(Boolean);
        for (const rid of ids) {
          const rep = await get(`/api/checkup/reports/${rid}`, {}, { showLoading: false, suppressErrorToast: true });
          if (rep) reports.push(rep);
        }
      }
      const normalized = reports.map(r => {
        const rawUrls = Array.isArray(r.file_urls) && r.file_urls.length > 0
          ? r.file_urls.filter(Boolean)
          : (r.file_url ? [r.file_url] : []);
        const rawThumbs = Array.isArray(r.thumbnail_urls) && r.thumbnail_urls.length > 0
          ? r.thumbnail_urls.filter(Boolean)
          : rawUrls;
        // [2026-05-05 全端图片附件 BasePath 治理 v1.0] 将裸 /uploads/... 补齐为带 baseUrl 的绝对 URL
        const urls = resolveAssetUrls(rawUrls);
        const thumbs = resolveAssetUrls(rawThumbs);
        return {
          id: r.id,
          title: r.title || '体检报告',
          file_urls: urls,
          thumbnail_urls: thumbs,
          display_thumbs: thumbs.slice(0, 4),
          total: urls.length
        };
      });
      this.setData({ reportList: normalized });

      // [Bug-04] 报告加载完成后，若尚未锁定咨询人，则用首份报告的所属人补锁一次
      if (!this.data.lockedFamilyMemberId && reports && reports.length > 0) {
        const firstMemberId = reports[0].family_member_id || reports[0].member_id || null;
        if (firstMemberId) {
          this._lockConsultTargetByMemberId(firstMemberId);
        }
      }
    } catch (e) {
      console.warn('[reports_brief] load failed', e);
    }
  },

  // [2026-04-23 报告分支] 点击报告卡片缩略图：多图预览
  onReportImageTap(e) {
    const { urls, current } = e.currentTarget.dataset;
    if (!urls || urls.length === 0) return;
    wx.previewImage({ current: current || urls[0], urls });
  },

  async _lockConsultTargetByMemberId(memberId) {
    if (!memberId) return;
    await this.loadFamilyMembers();
    const member = this.data.familyMembers.find(m => String(m.id) === String(memberId));
    if (member) {
      this.setData({
        consultTarget: { name: member.name, color: member.color },
        isTypeLocked: true,
        lockedFamilyMemberId: memberId,
        currentConsultantId: Number(memberId) || 0
      });
    }
  },

  // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
  // 报告解读按钮改造：不再新建独立 report_interpret 会话 + 跳转，
  // 改为在当前会话内通过 SSE intent='report_interpret' 把图片提交给后端引擎。
  // 与 H5 / Flutter 三端协议保持一致。
  // [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
  // 通用化：支持任意 button_type / ai_function_type / capture_purpose 组合，
  // 通过 resolveButtonIntent 统一映射到 SSE intent（report_interpret / drug_identify / null）。
  async _uploadAndStartReportInterpret(filePath, btn) {
    // 兼容旧签名：btn 可能是 buttonId (number) 或完整 button 对象
    const buttonObj = (btn && typeof btn === 'object') ? btn : { id: btn, button_type: 'report_interpret' };
    const buttonId = buttonObj.id || null;
    const buttonType = buttonObj.button_type || null;
    const aiFunctionType = buttonObj.ai_function_type || null;
    const capturePurpose = buttonObj.capture_purpose || null;
    const resolvedIntent = _resolveBtnIntent({
      button_type: buttonType,
      ai_function_type: aiFunctionType,
      capture_purpose: capturePurpose,
    });

    // 根据解析结果决定用户气泡文案
    let userBubbleText = '我上传了一张图片，请你帮我看看';
    if (resolvedIntent === 'report_interpret') {
      userBubbleText = '我上传了一份体检报告，请帮我解读';
    } else if (resolvedIntent === 'drug_identify') {
      userBubbleText = '我上传了一张药品图片，请帮我识别';
    }

    try {
      filePath = await compressImage(filePath);
    } catch (_) { /* 压缩失败回退原图 */ }
    wx.showLoading({ title: '上传中...', mask: true });
    try {
      const uploadRes = await uploadWithProgress('/api/upload/image', filePath, {});
      const imageUrl = (uploadRes && (uploadRes.url || uploadRes.image_url)) || '';
      if (!imageUrl) {
        wx.hideLoading();
        wx.showToast({ title: '图片上传失败', icon: 'none' });
        return;
      }
      wx.hideLoading();
      // 在当前会话内插入用户图片气泡 + 触发 SSE
      const id = generateId();
      const now = new Date();
      const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
      this.setData({
        messages: [...this.data.messages, {
          id, role: 'user', content: '', image: imageUrl, time, _ts: now.getTime(), references: [],
        }],
        scrollToId: `msg-${id}`,
      });
      // 确保会话存在
      let sid = this.data.chatId;
      if (!sid) {
        try {
          const { request: apiReq } = require('../../utils/request.js');
          const sess = await apiReq({
            url: '/api/chat/sessions',
            method: 'POST',
            data: { session_type: 'health_qa' },
          });
          sid = sess && (sess.id || sess.session_id);
          if (sid) {
            this.setData({ chatId: sid });
          }
        } catch (_) { /* ignore */ }
      }
      if (!sid) {
        wx.showToast({ title: '创建会话失败', icon: 'none' });
        return;
      }
      this._startSseStream(sid, userBubbleText, {
        intent: resolvedIntent || undefined,
        image_urls: [imageUrl],
        button_id: buttonId,
        button_type: buttonType,
        // [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
        // 后台新体系按钮 3 层配置透传给后端，让后端双保险兜底解析
        ai_function_type: aiFunctionType,
        capture_purpose: capturePurpose,
      });
    } catch (e) {
      wx.hideLoading();
      wx.showToast({ title: '上传后启动失败', icon: 'none' });
    }
  },

  async _uploadAndSendImage(filePath) {
    try {
      filePath = await compressImage(filePath);
    } catch (_) { /* 压缩失败回退原图 */ }
    const sizeCheck = await checkFileSize(filePath, 'chat_image');
    if (!sizeCheck.ok) {
      wx.showToast({ title: `文件大小超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
      return;
    }

    const id = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const messages = [...this.data.messages, { id, role: 'user', content: '', image: filePath, time, _ts: now.getTime(), references: [] }];
    this.setData({ messages, scrollToId: `msg-${id}`, showUploadProgress: true, uploadPercent: 0 });

    const loadingId = this.addMessage('loading', '');
    try {
      const uploadRes = await uploadWithProgress('/api/chat/upload-image', filePath, {
        formData: { session_id: this.data.chatId },
        onProgress: (percent) => this.setData({ uploadPercent: percent })
      });
      this.setData({ showUploadProgress: false, uploadPercent: -1 });
      this.removeMessage(loadingId);
      const reply = (uploadRes && uploadRes.ai_reply) || '已收到您上传的图片，正在分析中...';
      this.addMessage('assistant', reply);
    } catch (e) {
      this.setData({ showUploadProgress: false, uploadPercent: -1 });
      this.removeMessage(loadingId);
      this.addMessage('assistant', '图片上传失败，请稍后重试。');
    }
  },

  async _uploadAndSendFile(filePath, fileName) {
    const sizeCheck = await checkFileSize(filePath, 'chat_file');
    if (!sizeCheck.ok) {
      wx.showToast({ title: `文件大小超过限制（最大 ${sizeCheck.maxMb} MB）`, icon: 'none', duration: 2500 });
      return;
    }

    this.addMessage('user', `[文件] ${fileName}`);
    this.setData({ showUploadProgress: true, uploadPercent: 0 });
    const loadingId = this.addMessage('loading', '');
    try {
      const uploadRes = await uploadWithProgress('/api/chat/upload-file', filePath, {
        formData: { session_id: this.data.chatId, file_name: fileName },
        onProgress: (percent) => this.setData({ uploadPercent: percent })
      });
      this.setData({ showUploadProgress: false, uploadPercent: -1 });
      this.removeMessage(loadingId);
      const reply = (uploadRes && uploadRes.ai_reply) || '已收到您上传的文件，正在分析中...';
      this.addMessage('assistant', reply);
    } catch (e) {
      this.setData({ showUploadProgress: false, uploadPercent: -1 });
      this.removeMessage(loadingId);
      this.addMessage('assistant', '文件上传失败，请稍后重试。');
    }
  },

  // ========================
  // Consult target
  // ========================
  toggleTargetPicker() {
    if (this.data.isSymptomLocked || this.data.isTypeLocked) {
      wx.showToast({
        title: '当前咨询对象已锁定，如需为其他人咨询请返回重新发起',
        icon: 'none',
        duration: 2500
      });
      return;
    }
    if (!this.data.familyMembers.length) {
      this.loadFamilyMembers();
    }
    this.setData({ showTargetPicker: !this.data.showTargetPicker });
  },

  async restoreSessionMember(chatId) {
    try {
      const res = await get(`/api/chat-sessions/${chatId}`, {}, { showLoading: false, suppressErrorToast: true });
      if (res && (res.session_type === 'symptom_check' || res.session_type === 'symptom')) {
        const relation = res.family_member_relation || '本人';
        this.setData({
          isSymptomLocked: true,
          consultTarget: { name: relation, color: getRelationColor(relation) }
        });
      }
      // [Bug-04] 历史会话恢复：报告解读/对比同步锁定咨询人为报告所属人
      if (res && (res.session_type === 'report_interpret' || res.session_type === 'report_compare')) {
        this.setData({ isTypeLocked: true });
        const memberId = res.family_member_id || (res.family_member && res.family_member.id) || null;
        if (memberId) {
          this._lockConsultTargetByMemberId(memberId);
        }
      }
      // drug_identify 卡片 backend 兜底（仅当 URL 参数为空时填充）
      if (res && (res.session_type === 'drug_identify' || res.session_type === 'drug_query')) {
        const updates = {};
        if (!this.data.drugIdentifyMember) {
          const memberInfo = res.family_member_relation || (res.family_member && res.family_member.nickname) || '';
          if (memberInfo) updates.drugIdentifyMember = memberInfo;
        }
        if (!this.data.drugIdentifyDrugNames) {
          const apiDrugs = res.drug_names || res.title || '';
          if (apiDrugs) updates.drugIdentifyDrugNames = apiDrugs;
        }
        if (Object.keys(updates).length > 0) {
          updates.drugIdentifyBannerVisible = true;
          this.setData(updates);
        }
      }
    } catch (e) {
      console.log('restoreSessionMember error', e);
    }
  },

  onSelectTarget(e) {
    const member = e.currentTarget.dataset.member;
    const prevName = (this.data.consultTarget && this.data.consultTarget.name) || '本人';
    const targetName = member.name || '本人';
    // 保存撤销快照
    const snapshot = {
      consultTarget: this.data.consultTarget,
      messages: (this.data.messages || []).slice(),
      chatId: this.data.chatId,
      currentConsultantId: this.data.currentConsultantId,
      expiresAt: Date.now() + 5000,
    };
    this.setData({
      consultTarget: { name: targetName, color: member.color },
      showTargetPicker: false,
    });
    // 仅当确实切换了人才显示三重提示
    if (prevName === targetName) return;
    this.showV4SwitchTripleHints(targetName, snapshot);
    // 切换咨询人埋点
    try {
      post('/api/ai-home/track', {
        event: 'switch_consultant',
        platform: 'miniprogram',
        payload: { from_name: prevName, to_name: targetName },
      }, { showLoading: false, suppressErrorToast: true }).catch(() => {});
    } catch (e) { /* 静默 */ }
  },

  // [PRD-AI-HOME-OPTIM-V4 M2 · 2026-05-21] 切换咨询人三重提示（小程序）
  // 1. 中央 Toast（wx.showToast 中央位置）2 秒
  // 2. 系统消息气泡（永久留痕）插入到 messages
  // 3. 顶部撤销横条 5 秒（v4SwitchUndoVisible），点击恢复
  showV4SwitchTripleHints(targetName, snapshot) {
    // F-切人-01：Toast 浮层（小程序原生 Toast 居中）
    try {
      wx.showToast({
        title: `已切换为 ${targetName} 咨询`,
        icon: 'none',
        duration: 2000,
      });
    } catch (e) { /* 静默 */ }
    // F-切人-02：系统消息气泡（永久留痕）
    const sysMsg = {
      id: `sys-switch-${Date.now()}`,
      role: 'assistant',
      type: 'system_switch_notice',
      content: `—— 现在开始为 ${targetName} 提供健康咨询 ——`,
      time: '',
      _ts: Date.now(),
    };
    this.setData({
      messages: [...(this.data.messages || []), sysMsg],
      // F-切人-03：撤销横条状态
      v4SwitchUndoVisible: true,
      v4SwitchUndoText: `已切换为 ${targetName} 咨询，已为您开启新对话`,
      v4SwitchUndoSnapshot: snapshot,
      v4RefreshPaused: true,
    });
    // 5 秒后自动消失
    if (this._v4UndoTimer) clearTimeout(this._v4UndoTimer);
    this._v4UndoTimer = setTimeout(() => {
      this.setData({
        v4SwitchUndoVisible: false,
        v4SwitchUndoSnapshot: null,
        v4RefreshPaused: false,
      });
      try {
        post('/api/ai-home/track', {
          event: 'switch_undo_expired',
          platform: 'miniprogram',
          payload: {},
        }, { showLoading: false, suppressErrorToast: true }).catch(() => {});
      } catch (e) { /* 静默 */ }
    }, 5000);
  },

  // [PRD-AI-HOME-OPTIM-V4 M2] 5 秒撤销点击：恢复切换前快照
  onV4SwitchUndoTap() {
    const snap = this.data.v4SwitchUndoSnapshot;
    if (!snap || Date.now() > snap.expiresAt) return;
    if (this._v4UndoTimer) {
      clearTimeout(this._v4UndoTimer);
      this._v4UndoTimer = null;
    }
    this.setData({
      consultTarget: snap.consultTarget,
      messages: snap.messages,
      chatId: snap.chatId,
      currentConsultantId: snap.currentConsultantId,
      v4SwitchUndoVisible: false,
      v4SwitchUndoSnapshot: null,
      v4RefreshPaused: false,
    });
    try {
      post('/api/ai-home/track', {
        event: 'switch_undo_clicked',
        platform: 'miniprogram',
        payload: {},
      }, { showLoading: false, suppressErrorToast: true }).catch(() => {});
    } catch (e) { /* 静默 */ }
  },

  // [PRD-AI-HOME-OPTIM-V4 M3] 悬浮球点击：toggle 展开面板
  onV4FloatingBallTap() {
    const next = !this.data.v4FloatingPanelOpen;
    this.setData({ v4FloatingPanelOpen: next, v4FloatingFirstGuideVisible: false });
    if (next) {
      try {
        post('/api/ai-home/track', {
          event: 'floating_ball_clicked',
          platform: 'miniprogram',
          payload: {},
        }, { showLoading: false, suppressErrorToast: true }).catch(() => {});
      } catch (e) { /* 静默 */ }
    }
  },

  closeV4FloatingPanel() {
    this.setData({ v4FloatingPanelOpen: false });
  },

  // [PRD-AI-HOME-OPTIM-V4 M3] 悬浮球面板内功能入口点击：复用顶部功能按钮处理
  onV4PanelEntryTap(e) {
    const btn = e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.button;
    this.setData({ v4FloatingPanelOpen: false });
    if (!btn) return;
    try {
      post('/api/ai-home/track', {
        event: 'floating_ball_panel_action',
        platform: 'miniprogram',
        payload: { entry_name: btn.name || String(btn.id || '') },
      }, { showLoading: false, suppressErrorToast: true }).catch(() => {});
    } catch (e) { /* 静默 */ }
    // 复用既有的功能按钮点击入口
    try {
      this.onFunctionButtonTap({ currentTarget: { dataset: { button: btn } } });
    } catch (err) { /* 静默 */ }
  },

  // [PRD-AI-HOME-OPTIM-V4 M3] 首次引导气泡（onLoad 内调用一次）
  showV4FloatingFirstGuide() {
    try {
      const SHOWN_KEY = 'aihome_v4_floating_ball_guide_shown';
      const shown = wx.getStorageSync(SHOWN_KEY);
      if (shown === '1') return;
      setTimeout(() => {
        this.setData({ v4FloatingFirstGuideVisible: true });
        try {
          post('/api/ai-home/track', {
            event: 'first_guide_shown',
            platform: 'miniprogram',
            payload: {},
          }, { showLoading: false, suppressErrorToast: true }).catch(() => {});
        } catch (e) { /* 静默 */ }
        setTimeout(() => {
          this.setData({ v4FloatingFirstGuideVisible: false });
          try { wx.setStorageSync(SHOWN_KEY, '1'); } catch (e) { /* 静默 */ }
        }, 3000);
      }, 800);
    } catch (e) { /* 静默 */ }
  },

  // ============================================================
  // [PRD-420 2026-05-08] 添加家庭成员（关系九宫格 + 信息表单）
  // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31]
  //   点"+ 新建家庭成员"时先查配额：满了直接弹"名额已满"框，不打开添加表单；
  //   quota_max 实时来自后端 /api/family/member/quota，绝不写死
  // ============================================================
  async openAddMemberPopup() {
    // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31 修复版] 完善档案拦截前移：
    //   点"新增咨询人 / 添加成员"时，第一步先查本人 needComplete。
    //   needComplete=true：弹"完善本人资料"提示 → 跳转到健康档案页（小程序的
    //   现成"完善本人资料"抽屉在 health-profile 页承接，UI 与该端一致）。
    //   complete=false：才继续走查名额、开表单的逻辑。
    try {
      const sres = await get('/api/health-profile/self', {}, { showLoading: false, suppressErrorToast: true });
      const sdata = (sres && (sres.data || sres)) || {};
      const need = !!sdata.needComplete;
      if (need) {
        this.setData({ showTargetPicker: false });
        wx.showModal({
          title: '请先完善本人资料',
          content: '为了给您提供更精准的健康服务，添加家庭成员前请先完善您的基本资料（姓名、性别、出生日期）。',
          confirmText: '去完善',
          cancelText: '稍后',
          success: (mr) => {
            if (mr.confirm) {
              wx.switchTab({
                url: '/pages/health-profile/index',
                fail() {
                  wx.navigateTo({ url: '/pages/health-profile/index' });
                },
              });
            }
          },
        });
        return;
      }
    } catch (e) {
      // 接口异常时不阻断：继续走原查名额流程
    }
    // 先查配额
    try {
      const r = await get('/api/family/member/quota', {}, { showLoading: false, suppressErrorToast: true });
      const data = (r && (r.data || r)) || {};
      const qMax = Number(data.quota_max == null ? 0 : data.quota_max);
      const qRemaining = Number(data.quota_remaining == null ? 0 : data.quota_remaining);
      if (qMax !== -1 && qRemaining <= 0) {
        this.setData({
          showTargetPicker: false,
          showQuotaFull: true,
          quotaFullMax: qMax,
        });
        return;
      }
    } catch (e) {
      // 接口异常时降级：放行让用户进入表单（与原行为一致）
    }
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    this.setData({
      showAddMember: true,
      showTargetPicker: false,
      selectedRelation: null,
      todayStr,
      addForm: {
        nickname: '',
        gender: '',
        birthday: '',
        height: '',
        weight: '',
        medicalHistories: [],
        medicalOther: '',
        allergies: [],
        allergyOther: ''
      },
      canSaveMember: false
    });
    await this._loadRelationTypes();
  },

  // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31] 名额已满弹框 - 暂不升级
  onQuotaFullSkip() {
    this.setData({ showQuotaFull: false });
  },

  // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31] 名额已满弹框 - 去升级
  onQuotaFullUpgrade() {
    this.setData({ showQuotaFull: false });
    wx.navigateTo({
      url: '/pages/member-center/index',
      fail() {
        wx.showToast({ title: '会员中心未配置', icon: 'none' });
      },
    });
  },

  // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31] 成员已添加成功🎉弹框 - 暂不邀请
  onAddedDialogSkip() {
    this.setData({ showAddedDialog: false, addedNickname: '', addedMemberId: '' });
  },

  // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31 修复版] 成员已添加成功🎉弹框 - 去邀请 TA
  // 三端口径统一：邀请前必先有档案、必有成员 id；无 id 视为异常，直接给出提示，
  // 不再跳无 id 兜底页。
  onAddedDialogInvite() {
    const mid = this.data.addedMemberId;
    this.setData({ showAddedDialog: false, addedNickname: '', addedMemberId: '' });
    if (!mid) {
      wx.showToast({ title: '成员信息缺失，请从档案列表进入邀请', icon: 'none' });
      return;
    }
    wx.navigateTo({
      url: `/pages/family-invite/index?member_id=${mid}`,
      fail() {
        wx.showToast({ title: '邀请页未配置', icon: 'none' });
      },
    });
  },

  closeAddMemberPopup() {
    if (this._isAddFormDirty()) {
      const that = this;
      wx.showModal({
        title: '确认离开？',
        content: '未保存的内容将丢失',
        confirmText: '确认离开',
        cancelText: '取消',
        success: (res) => {
          if (res.confirm) {
            that.setData({ showAddMember: false, selectedRelation: null });
          }
        }
      });
      return;
    }
    this.setData({ showAddMember: false, selectedRelation: null });
  },

  _isAddFormDirty() {
    const f = this.data.addForm;
    return !!(
      this.data.selectedRelation ||
      (f.nickname && f.nickname.trim()) ||
      f.gender ||
      f.birthday ||
      f.height ||
      f.weight ||
      (f.medicalHistories && f.medicalHistories.length) ||
      f.medicalOther ||
      (f.allergies && f.allergies.length) ||
      f.allergyOther
    );
  },

  async _loadRelationTypes() {
    try {
      const res = await get('/api/relation-types', {}, { showLoading: false, suppressErrorToast: true });
      const items = (res && res.items) ? res.items : (Array.isArray(res) ? res : []);
      const RELATION_EMOJI = {
        '本人': '👤', '爸爸': '👨', '妈妈': '👩', '老公': '🧑', '老婆': '👰',
        '儿子': '👦', '女儿': '👧', '哥哥': '👱‍♂️', '弟弟': '🧑',
        '姐姐': '👱‍♀️', '妹妹': '👧', '爷爷': '👴', '奶奶': '👵',
        '外公': '👴', '外婆': '👵', '其他': '🧑'
      };
      const list = items
        .filter((rt) => rt && rt.name !== '本人')
        .map((rt) => Object.assign({}, rt, { emoji: RELATION_EMOJI[rt.name] || '🧑' }));
      this.setData({ relationTypes: list });
    } catch (e) {
      this.setData({ relationTypes: [] });
    }
  },

  onSelectRelation(e) {
    const rt = e.currentTarget.dataset.rt;
    const cur = this.data.selectedRelation;
    // 再次点击同一关系即取消
    if (cur && cur.id === rt.id) {
      this.setData({ selectedRelation: null });
    } else {
      this.setData({ selectedRelation: rt });
    }
    this._refreshCanSave();
  },

  onAddInput(e) {
    const field = e.currentTarget.dataset.field;
    const value = e.detail.value;
    const addForm = Object.assign({}, this.data.addForm, { [field]: value });
    this.setData({ addForm });
    this._refreshCanSave();
  },

  onSelectGender(e) {
    const gender = e.currentTarget.dataset.gender;
    this.setData({ addForm: Object.assign({}, this.data.addForm, { gender }) });
    this._refreshCanSave();
  },

  onPickBirthday(e) {
    this.setData({ addForm: Object.assign({}, this.data.addForm, { birthday: e.detail.value }) });
    this._refreshCanSave();
  },

  onToggleMedical(e) {
    const opt = e.currentTarget.dataset.opt;
    const list = (this.data.addForm.medicalHistories || []).slice();
    const idx = list.indexOf(opt);
    if (idx >= 0) list.splice(idx, 1);
    else list.push(opt);
    this.setData({ addForm: Object.assign({}, this.data.addForm, { medicalHistories: list }) });
  },

  onToggleAllergy(e) {
    const opt = e.currentTarget.dataset.opt;
    const list = (this.data.addForm.allergies || []).slice();
    const idx = list.indexOf(opt);
    if (idx >= 0) list.splice(idx, 1);
    else list.push(opt);
    this.setData({ addForm: Object.assign({}, this.data.addForm, { allergies: list }) });
  },

  _refreshCanSave() {
    const rel = this.data.selectedRelation;
    const f = this.data.addForm;
    const ok = !!(
      rel &&
      f.nickname && f.nickname.trim() &&
      f.gender &&
      f.birthday
    );
    this.setData({ canSaveMember: ok });
  },

  async onSaveNewMember() {
    if (!this.data.canSaveMember || this.data.addLoading) return;
    const rel = this.data.selectedRelation;
    const f = this.data.addForm;

    const nickname = (f.nickname || '').trim();
    if (nickname.length < 1 || nickname.length > 20) {
      wx.showToast({ title: '姓名为 1~20 个字符', icon: 'none' });
      return;
    }
    if (f.height) {
      const h = Number(f.height);
      if (!isFinite(h) || h < 30 || h > 250) {
        wx.showToast({ title: '身高范围 30~250cm', icon: 'none' });
        return;
      }
    }
    if (f.weight) {
      const w = Number(f.weight);
      if (!isFinite(w) || w < 1 || w > 500) {
        wx.showToast({ title: '体重范围 1~500kg', icon: 'none' });
        return;
      }
    }

    this.setData({ addLoading: true });
    const body = {
      nickname,
      name: nickname,
      relationship_type: rel.name,
      relation_type_id: rel.id,
      gender: f.gender,
      birthday: f.birthday
    };
    if (f.height) body.height = Number(f.height);
    if (f.weight) body.weight = Number(f.weight);
    const med = (f.medicalHistories || []).slice();
    if (f.medicalOther && f.medicalOther.trim()) med.push(f.medicalOther.trim());
    if (med.length) body.medical_histories = med;
    const aller = (f.allergies || []).slice();
    if (f.allergyOther && f.allergyOther.trim()) aller.push(f.allergyOther.trim());
    if (aller.length) body.allergies = aller;

    try {
      const r = await post('/api/family/members', body, { showLoading: false });
      // 刷新列表 + 自动选中新成员
      await this.loadFamilyMembers();
      // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31]
      // 保存成功后弹"成员已添加成功🎉"框（可跳过 / 去邀请 TA）
      let newMemberId = '';
      try {
        const rd = (r && (r.data || r)) || {};
        newMemberId = rd.id || rd.member_id || (rd.data && (rd.data.id || rd.data.member_id)) || '';
      } catch (_) {}
      this.setData({
        showAddMember: false,
        selectedRelation: null,
        addLoading: false,
        consultTarget: { name: rel.name, color: getRelationColor(rel.name) },
        showAddedDialog: true,
        addedNickname: nickname,
        addedMemberId: newMemberId,
      });
    } catch (e) {
      this.setData({ addLoading: false });
      wx.showToast({ title: '添加失败，请重试', icon: 'none' });
    }
  },

  // ========================
  // Voice input
  // ========================
  _initRecognizeManager() {
    const manager = plugin.getRecordRecognitionManager();

    manager.onStart = () => {
      let t = 0;
      this._recordTimer = setInterval(() => {
        t++;
        this.setData({ recordingTime: t });
        if (t >= 30) {
          this._finishRecording();
        }
      }, 1000);
    };

    manager.onStop = (res) => {
      if (this._recordTimer) {
        clearInterval(this._recordTimer);
        this._recordTimer = null;
      }
      if (this._discardNextResult) {
        this._discardNextResult = false;
        return;
      }
      const text = res.result ? res.result.replace(/[\u3002\uff1b\uff0c\uff1a\u201c\u201d\u2018\u2019\uff08\uff09\u3001\uff1f\u300a\u300b\uff01\u3010\u3011\u2026\u2014\uff5e\u00b7.,!?;:'"()\[\]{}\-_\/\\@#\$%\^&\*\+=~`<>]/g, '').trim() : '';
      if (text) {
        this.setData({ inputValue: text });
        this.sendMessage();
      } else {
        wx.showToast({ title: '未识别到语音内容，请重试', icon: 'none' });
      }
    };

    manager.onError = () => {
      if (this._recordTimer) {
        clearInterval(this._recordTimer);
        this._recordTimer = null;
      }
      this.setData({
        isRecording: false,
        showRecordOverlay: false,
        recordCancelling: false,
        voiceMode: false
      });
      wx.showToast({ title: '语音服务暂不可用，已切换为键盘输入', icon: 'none' });
    };

    this._recognizeManager = manager;
  },

  toggleVoiceMode() {
    if (this.data.voiceMode) {
      this.setData({ voiceMode: false, inputFocus: true });
      return;
    }
    this._checkRecordAuth(() => {
      this.setData({ voiceMode: true, inputFocus: false });
    });
  },

  _checkRecordAuth(successCb) {
    wx.getSetting({
      success: (res) => {
        if (res.authSetting['scope.record']) {
          if (!this._recognizeManager) this._initRecognizeManager();
          successCb();
          return;
        }
        wx.authorize({
          scope: 'scope.record',
          success: () => {
            if (!this._recognizeManager) this._initRecognizeManager();
            successCb();
          },
          fail: () => {
            wx.showModal({
              title: '允许访问麦克风',
              content: '请授权麦克风，以便AI发送语音消息',
              cancelText: '取消',
              confirmText: '去授权',
              success: (modalRes) => {
                if (modalRes.confirm) {
                  wx.openSetting({
                    success: (settingRes) => {
                      if (settingRes.authSetting['scope.record']) {
                        if (!this._recognizeManager) this._initRecognizeManager();
                        successCb();
                      } else {
                        wx.showToast({ title: '请在设置中开启麦克风权限', icon: 'none' });
                      }
                    }
                  });
                } else {
                  wx.showToast({ title: '请在设置中开启麦克风权限', icon: 'none' });
                }
              }
            });
          }
        });
      }
    });
  },

  onRecordTouchStart(e) {
    this._touchStartY = e.touches[0].clientY;
    this._touchStartTime = Date.now();
    this.setData({
      isRecording: true,
      showRecordOverlay: true,
      recordCancelling: false,
      recordingTime: 0
    });
    if (!this._recognizeManager) this._initRecognizeManager();
    this._recognizeManager.start({ lang: 'zh_CN' });
  },

  onRecordTouchMove(e) {
    if (!this.data.isRecording) return;
    const moveY = this._touchStartY - e.touches[0].clientY;
    this.setData({ recordCancelling: moveY > 80 });
  },

  onRecordTouchEnd() {
    if (!this.data.isRecording) return;
    const duration = Date.now() - this._touchStartTime;
    if (duration < 500) {
      this._cancelRecording();
      wx.showToast({ title: '录音时间太短', icon: 'none' });
      return;
    }
    if (this.data.recordCancelling) {
      this._cancelRecording();
    } else {
      this._finishRecording();
    }
  },

  _finishRecording() {
    if (this._recordTimer) {
      clearInterval(this._recordTimer);
      this._recordTimer = null;
    }
    this.setData({
      isRecording: false,
      showRecordOverlay: false,
      recordCancelling: false
    });
    if (this._recognizeManager) {
      this._recognizeManager.stop();
    }
  },

  _cancelRecording() {
    if (this._recordTimer) {
      clearInterval(this._recordTimer);
      this._recordTimer = null;
    }
    this.setData({
      isRecording: false,
      showRecordOverlay: false,
      recordCancelling: false
    });
    this._discardNextResult = true;
    if (this._recognizeManager) {
      this._recognizeManager.stop();
    }
  },

  preventTouchMove() {},

  // ========================
  // Message handling
  // ========================
  onInput(e) {
    this.setData({ inputValue: e.detail.value });
  },

  async sendMessage() {
    const content = this.data.inputValue.trim();
    if (!content) return;

    // Stop TTS when user sends new message
    this._stopTts();

    this.addMessage('user', content);
    this.setData({ inputValue: '', latestAiMsgId: '' });

    // Try SSE streaming first, fallback to normal request
    try {
      this._startSseStream(this.data.chatId, content);
    } catch (e) {
      // Fallback: normal request
      const loadingId = this.addMessage('loading', '');
      try {
        await this.mockDelay(1000 + Math.random() * 1500);
        this.removeMessage(loadingId);
        const { reply, knowledgeHits } = this.getMockReply(content);
        const msgId = this.addMessage('assistant', reply, knowledgeHits && knowledgeHits.length ? { knowledgeHits } : {});
        this.setData({ latestAiMsgId: msgId });
      } catch (err) {
        this.removeMessage(loadingId);
        this.addMessage('assistant', '抱歉，网络出现了问题，请稍后重试。');
      }
    }
  },

  _parseMessage(content) {
    const parts = content.split('---disclaimer---');
    return {
      mainContent: parts[0].trim(),
      disclaimer: parts.length > 1 ? parts[1].trim() : ''
    };
  },

  addMessage(role, content, extra = {}) {
    const id = generateId();
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const msgData = {
      id,
      role,
      content,
      time,
      _ts: now.getTime(),
      // [PRD-433 F-14] references 字段容错：默认空数组
      references: (extra && Array.isArray(extra.references)) ? extra.references : [],
      ...extra
    };
    if (role === 'assistant' && content && content.includes('---disclaimer---')) {
      const parsed = this._parseMessage(content);
      msgData.mainContent = parsed.mainContent;
      msgData.disclaimer = parsed.disclaimer;
    }
    // [PRD-433 F-09] 时间分隔条：与上一条消息间隔 > 5 分钟才插入
    const prev = this.data.messages.length > 0 ? this.data.messages[this.data.messages.length - 1] : null;
    if (!prev || (prev._ts && (now.getTime() - prev._ts) > 5 * 60 * 1000)) {
      msgData.showTimeDivider = true;
      msgData.timeDividerText = time;
    } else {
      msgData.showTimeDivider = false;
    }
    if (role === 'assistant' && content) {
      this.setData({ latestAiMsgId: id });
    }
    const messages = [...this.data.messages, msgData];
    this.setData({ messages, scrollToId: `msg-${id}` });
    return id;
  },

  onKnowledgeFeedback(e) {
    const { feedback, hit_log_id: hitLogId } = e.detail || {};
    console.log('knowledge feedback', feedback, hitLogId);
  },

  removeMessage(id) {
    const messages = this.data.messages.filter(m => m.id !== id);
    this.setData({ messages });
  },

  chooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const tempFilePath = res.tempFiles[0].tempFilePath;
        const id = generateId();
        const now = new Date();
        const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
        const messages = [...this.data.messages, { id, role: 'user', content: '', image: tempFilePath, time, _ts: now.getTime(), references: [] }];
        this.setData({ messages, scrollToId: `msg-${id}` });

        const loadingId = this.addMessage('loading', '');
        setTimeout(() => {
          this.removeMessage(loadingId);
          this.addMessage('assistant', '我已收到您上传的图片。根据图片信息，建议您：\n\n1. 注意保持良好的生活习惯\n2. 如症状持续请及时就医\n3. 可以详细描述您的不适症状，我会为您提供更准确的分析');
        }, 2000);
      }
    });
  },

  previewImage(e) {
    const url = e.currentTarget.dataset.url;
    wx.previewImage({ current: url, urls: [url] });
  },

  mockDelay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  },

  getMockReply(question) {
    const demoHits =
      question.includes('知识库') || question.includes('维生素')
        ? [
            {
              entry_id: 'demo-1',
              kb_id: 0,
              type: 'qa',
              question: '示例：维生素C有什么作用？',
              title: '知识库参考',
              hit_log_id: 0,
              content_json: {
                text: '维生素C有助于增强免疫力、促进胶原蛋白合成，并帮助铁的吸收。日常可通过新鲜蔬果适量补充。',
                images: [],
                products: [
                  {
                    name: '维生素C咀嚼片（示例）',
                    price: '68',
                    image: '',
                    url: ''
                  }
                ]
              }
            }
          ]
        : null;

    if (question.includes('头痛') || question.includes('头疼')) {
      return {
        reply:
          '根据您描述的头痛症状，可能的原因有：\n\n1. **紧张性头痛**：压力大、睡眠不足\n2. **偏头痛**：单侧搏动性疼痛\n3. **颈椎问题**：长时间低头导致\n\n建议：\n• 保持充足睡眠\n• 适当休息，减少用眼\n• 若持续加重请及时就医\n\n请问您头痛的位置是哪里？持续多长时间了？',
        knowledgeHits: demoHits
      };
    }
    if (question.includes('感冒') || question.includes('发烧')) {
      return {
        reply:
          '感冒症状的自我调理建议：\n\n1. 多休息，保证充足睡眠\n2. 多喝温水，促进新陈代谢\n3. 饮食清淡，多吃蔬果\n4. 注意保暖，避免再次受凉\n\n⚠️ 如果体温超过38.5°C或持续3天以上，建议及时就医。\n\n请问您目前有哪些具体症状？体温多少度？',
        knowledgeHits: demoHits
      };
    }
    if (question.includes('失眠') || question.includes('睡不着')) {
      return {
        reply:
          '失眠的调理建议：\n\n1. **作息规律**：固定起床和就寝时间\n2. **睡前放松**：可以尝试深呼吸、冥想\n3. **环境改善**：保持卧室安静、黑暗、凉爽\n4. **避免刺激**：睡前2小时不使用电子设备\n5. **饮食注意**：避免咖啡因和酒精\n\n如果失眠超过一个月，建议寻求专业医生帮助。',
        knowledgeHits: demoHits
      };
    }
    return {
      reply:
        '感谢您的描述。根据您提供的信息，我有以下建议：\n\n1. 建议保持良好的作息习惯\n2. 注意饮食均衡，适当运动\n3. 如症状持续或加重，请及时到医院就诊\n\n您可以进一步描述：\n• 症状持续时间\n• 是否有加重或缓解的因素\n• 既往病史和用药情况\n\n这样我能为您提供更准确的分析。',
      knowledgeHits: demoHits
    };
  }
});
