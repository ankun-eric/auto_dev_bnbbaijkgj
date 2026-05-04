const { post, get } = require('../../utils/request');
const { generateId } = require('../../utils/util');
// [2026-05-05 全端图片附件 BasePath 治理 v1.0] 数字人静默/说话视频 URL 来自后端，可能是裸 /uploads/...
const { resolveAssetUrl } = require('../../utils/asset-url');

Page({
  data: {
    callId: '',
    digitalHumanId: '',
    sessionId: '',
    digitalHuman: null,
    currentVideoUrl: '',
    videoMuted: true,
    callStatus: 'connecting',
    statusText: '正在连接...',
    durationText: '00:00',
    dialogs: [],
    scrollToDialog: '',
    isRecording: false,
    showPermissionDialog: false,
    statusBarHeight: 44
  },

  _recorderManager: null,
  _audioContext: null,
  _durationTimer: null,
  _callSeconds: 0,
  _tempAudioPath: '',
  _networkListener: null,

  onLoad(options) {
    const { digitalHumanId = '', sessionId = '' } = options;
    this.setData({ digitalHumanId, sessionId });

    const sysInfo = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
    this.setData({ statusBarHeight: sysInfo.statusBarHeight || 44 });

    this._initRecorder();
    this._requestMicPermission(() => {
      this._loadDigitalHuman();
      this._startCall();
    });

    wx.onNetworkStatusChange((res) => {
      if (!res.isConnected && this.data.callStatus === 'connected') {
        this._addDialog('system', '网络已断开，通话中断');
        this.setData({ callStatus: 'disconnected', statusText: '网络已断开' });
        this._stopDurationTimer();
      }
    });
  },

  onUnload() {
    this._cleanup();
  },

  _cleanup() {
    this._stopDurationTimer();
    if (this._recorderManager) {
      try { this._recorderManager.stop(); } catch (_) {}
    }
    if (this._audioContext) {
      try { this._audioContext.stop(); this._audioContext.destroy(); } catch (_) {}
    }
  },

  _initRecorder() {
    const rm = wx.getRecorderManager();

    rm.onStop((res) => {
      this._tempAudioPath = res.tempFilePath;
      this.setData({ isRecording: false });
      if (this._tempAudioPath) {
        this._sendVoiceMessage(this._tempAudioPath);
      }
    });

    rm.onError((err) => {
      console.log('recorder error', err);
      this.setData({ isRecording: false });
      wx.showToast({ title: '录音失败，请重试', icon: 'none' });
    });

    this._recorderManager = rm;
  },

  _requestMicPermission(successCb) {
    wx.getSetting({
      success: (res) => {
        if (res.authSetting['scope.record']) {
          successCb();
          return;
        }
        wx.authorize({
          scope: 'scope.record',
          success: () => successCb(),
          fail: () => this.setData({ showPermissionDialog: true })
        });
      }
    });
  },

  dismissPermission() {
    this.setData({ showPermissionDialog: false });
    wx.navigateBack();
  },

  onPermissionSetting(e) {
    if (e.detail.authSetting['scope.record']) {
      this.setData({ showPermissionDialog: false });
      this._loadDigitalHuman();
      this._startCall();
    } else {
      wx.showToast({ title: '需要麦克风权限才能通话', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1500);
    }
  },

  async _loadDigitalHuman() {
    if (!this.data.digitalHumanId) return;
    try {
      const res = await get(`/api/chat/digital-human/${this.data.digitalHumanId}`, {}, { showLoading: false, suppressErrorToast: true });
      if (res) {
        // [2026-05-05 全端图片附件 BasePath 治理 v1.0]
        // 把数字人物料（静默/说话视频）的 URL 在数据入口处一次性补齐为绝对 URL，
        // 后续 _switchToSilentVideo / _switchToSpeakingVideo 都基于 digitalHuman 上的这些字段。
        if (res.silent_video_url) res.silent_video_url = resolveAssetUrl(res.silent_video_url);
        if (res.speaking_video_url) res.speaking_video_url = resolveAssetUrl(res.speaking_video_url);
        if (res.avatar_url) res.avatar_url = resolveAssetUrl(res.avatar_url);
        this.setData({
          digitalHuman: res,
          currentVideoUrl: res.silent_video_url || ''
        });
      }
    } catch (e) {
      console.log('load digital human error', e);
    }
  },

  async _startCall() {
    this.setData({ callStatus: 'connecting', statusText: '正在连接...' });
    try {
      const payload = {};
      if (this.data.digitalHumanId) payload.digital_human_id = parseInt(this.data.digitalHumanId);
      if (this.data.sessionId) payload.chat_session_id = parseInt(this.data.sessionId) || undefined;

      const res = await post('/api/chat/voice-call/start', payload, { showLoading: false, suppressErrorToast: true });
      if (res && res.id) {
        this.setData({
          callId: res.id,
          callStatus: 'connected',
          statusText: '通话中'
        });
        this._startDurationTimer();
        this._addDialog('ai', '您好，我是您的AI健康顾问，请问有什么可以帮您？');
      } else {
        this.setData({ callStatus: 'error', statusText: '连接失败' });
        wx.showToast({ title: '连接失败，请重试', icon: 'none' });
      }
    } catch (e) {
      this.setData({ callStatus: 'error', statusText: '连接失败' });
      wx.showToast({ title: '连接失败，请稍后重试', icon: 'none' });
    }
  },

  _startDurationTimer() {
    this._callSeconds = 0;
    this._durationTimer = setInterval(() => {
      this._callSeconds++;
      const min = Math.floor(this._callSeconds / 60).toString().padStart(2, '0');
      const sec = (this._callSeconds % 60).toString().padStart(2, '0');
      this.setData({ durationText: `${min}:${sec}` });
    }, 1000);
  },

  _stopDurationTimer() {
    if (this._durationTimer) {
      clearInterval(this._durationTimer);
      this._durationTimer = null;
    }
  },

  toggleRecording() {
    if (this.data.callStatus !== 'connected') return;
    if (this.data.isRecording) {
      this._stopRecording();
    } else {
      this._startRecording();
    }
  },

  _startRecording() {
    this.setData({ isRecording: true });
    this._recorderManager.start({
      duration: 30000,
      sampleRate: 16000,
      numberOfChannels: 1,
      encodeBitRate: 48000,
      format: 'mp3'
    });
  },

  _stopRecording() {
    this._recorderManager.stop();
  },

  async _sendVoiceMessage(audioPath) {
    this._addDialog('user', '语音消息发送中...');
    this._switchToSpeakingVideo();

    try {
      const userDialogIdx = this.data.dialogs.length - 1;

      const app = getApp();
      const token = app.globalData.token;
      const headers = {};
      if (token) headers.Authorization = `Bearer ${token}`;

      const uploadRes = await new Promise((resolve, reject) => {
        wx.uploadFile({
          url: app.globalData.baseUrl + `/api/search/asr/recognize`,
          filePath: audioPath,
          name: 'audio_file',
          header: headers,
          formData: { format: 'mp3', sample_rate: '16000' },
          success: (res) => {
            try {
              const data = JSON.parse(res.data);
              if (res.statusCode === 200) resolve(data);
              else reject(data);
            } catch (_) { reject(res); }
          },
          fail: reject
        });
      });

      const userText = (uploadRes && (uploadRes.text || (uploadRes.data && uploadRes.data.text))) || '(语音)';

      const dialogs = [...this.data.dialogs];
      if (dialogs[userDialogIdx]) {
        dialogs[userDialogIdx].text = userText;
      }
      this.setData({ dialogs });

      if (userText && userText !== '(语音)') {
        const msgRes = await post(`/api/chat/voice-call/${this.data.callId}/message`, {
          user_text: userText,
        }, { showLoading: false, suppressErrorToast: true });
        const aiText = (msgRes && msgRes.ai_text) || '抱歉，我没有听清楚，请再说一遍。';
        this._addDialog('ai', aiText);
      } else {
        this._addDialog('ai', '抱歉，我没有听清楚，请再说一遍。');
      }
      this._switchToSilentVideo();
    } catch (e) {
      console.log('send voice error', e);
      this._addDialog('ai', '抱歉，语音处理出现问题，请重试。');
      this._switchToSilentVideo();
    }
  },

  _playAiAudio(audioUrl) {
    if (!audioUrl) {
      this._switchToSilentVideo();
      return;
    }
    if (this._audioContext) {
      try { this._audioContext.stop(); this._audioContext.destroy(); } catch (_) {}
    }
    const ctx = wx.createInnerAudioContext();
    // [2026-05-05 全端图片附件 BasePath 治理 v1.0] 兜底：AI 音频地址也可能是裸 /uploads/...
    ctx.src = resolveAssetUrl(audioUrl);
    ctx.onEnded(() => {
      this._switchToSilentVideo();
      ctx.destroy();
    });
    ctx.onError(() => {
      this._switchToSilentVideo();
      ctx.destroy();
    });
    ctx.play();
    this._audioContext = ctx;
  },

  _switchToSpeakingVideo() {
    const dh = this.data.digitalHuman;
    if (dh && dh.speaking_video_url) {
      this.setData({ currentVideoUrl: dh.speaking_video_url });
    }
  },

  _switchToSilentVideo() {
    const dh = this.data.digitalHuman;
    if (dh && dh.silent_video_url) {
      this.setData({ currentVideoUrl: dh.silent_video_url });
    }
  },

  _addDialog(role, text) {
    const id = generateId();
    const dialogs = [...this.data.dialogs, { id, role, text }];
    this.setData({ dialogs, scrollToDialog: `dialog-${id}` });
  },

  async hangUp() {
    wx.showModal({
      title: '结束通话',
      content: '确定要结束当前通话吗？',
      confirmColor: '#ff4d4f',
      success: async (res) => {
        if (!res.confirm) return;
        this._stopDurationTimer();
        this.setData({ callStatus: 'ended', statusText: '通话已结束', isRecording: false });

        if (this._recorderManager) {
          try { this._recorderManager.stop(); } catch (_) {}
        }

        if (this.data.callId) {
          try {
            await post(`/api/chat/voice-call/${this.data.callId}/end`, {
              dialog_content: this.data.dialogs.filter(d => d.role !== 'system').map(d => ({
                role: d.role === 'ai' ? 'assistant' : d.role,
                content: d.text
              }))
            }, { showLoading: false, suppressErrorToast: true });
          } catch (e) {
            console.log('end call error', e);
          }
        }

        setTimeout(() => wx.navigateBack(), 800);
      }
    });
  }
});
