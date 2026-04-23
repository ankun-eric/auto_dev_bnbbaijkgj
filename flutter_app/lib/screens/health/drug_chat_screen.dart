// [2026-04-23 v1.2] 用药对话页：融合卡片平铺 + 首条 AI 建议 + 重新生成 + 再加一个药

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:image_picker/image_picker.dart';

import '../../config/api_config.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/drug/drug_merge_card_flat.dart';

const _kDrugPink = Color(0xFFEB2F96);
const _kDrugPurple = Color(0xFF722ED1);
const _kTextDark = Color(0xFF333333); // ≈ Colors.grey.shade800
const _kMaxDrugs = 2;
const _kRegenDebounceSec = 10;

class DrugChatScreen extends StatefulWidget {
  const DrugChatScreen({super.key});

  @override
  State<DrugChatScreen> createState() => _DrugChatScreenState();
}

class _DrugChatScreenState extends State<DrugChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final ImagePicker _picker = ImagePicker();
  final ApiService _api = ApiService();

  String _sessionId = '';
  String _drugName = '用药参考';
  int? _recordId;
  int? _familyMemberId;

  // 融合卡片数据
  List<DrugCardItem> _drugs = [];
  String _memberName = '本人';
  int? _memberAge;
  String? _memberRelation;

  // 消息
  List<Map<String, dynamic>> _messages = [];
  int? _openingMessageId;
  bool _isLoadingInit = true;
  bool _isSending = false;

  // 重新生成防抖
  DateTime? _lastRegenTime;
  bool _isRegenerating = false;

  // 追加药
  bool _isAppendingDrug = false;

  bool _didInit = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_didInit) return;
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is Map) {
      _sessionId = args['sessionId']?.toString() ?? '';
      _drugName = args['drugName']?.toString() ?? '用药参考';
      _recordId = args['recordId'] is int
          ? args['recordId']
          : int.tryParse(args['recordId']?.toString() ?? '');
      _familyMemberId = args['familyMemberId'] is int
          ? args['familyMemberId']
          : int.tryParse(args['familyMemberId']?.toString() ?? '');
    }
    _didInit = true;

    if (_sessionId.isEmpty) {
      setState(() => _isLoadingInit = false);
      return;
    }

    // 延迟 300ms 调 init，确保首帧渲染完成
    Future.delayed(const Duration(milliseconds: 300), _loadInit);
  }

  Future<void> _loadInit() async {
    if (!mounted) return;
    setState(() => _isLoadingInit = true);

    // 并行拉取：init + 历史消息
    try {
      final sid = int.tryParse(_sessionId);
      if (sid == null) {
        setState(() => _isLoadingInit = false);
        return;
      }
      final results = await Future.wait([
        _api.drugChatInit(sid, memberId: _familyMemberId),
        _api.getChatMessages(_sessionId),
      ]);
      if (!mounted) return;

      final initResp = results[0];
      final msgResp = results[1];

      // 历史消息
      List<Map<String, dynamic>> historyMsgs = [];
      if (msgResp.statusCode == 200) {
        final data = msgResp.data;
        final raw = data is Map && data.containsKey('data') ? data['data'] : data;
        final list = raw is List
            ? raw
            : (raw is Map ? (raw['items'] as List? ?? []) : []);
        historyMsgs = list.cast<Map<String, dynamic>>();
      }

      // init 响应
      if (initResp.statusCode == 200) {
        final d = initResp.data is Map ? Map<String, dynamic>.from(initResp.data) : <String, dynamic>{};
        final drugList = (d['drug_list'] as List?) ?? [];
        final memberInfo = d['member_info'] is Map
            ? Map<String, dynamic>.from(d['member_info'])
            : <String, dynamic>{};
        final opening = d['opening_message'] is Map
            ? Map<String, dynamic>.from(d['opening_message'])
            : <String, dynamic>{};

        setState(() {
          _drugs = drugList
              .whereType<Map>()
              .map((e) => DrugCardItem.fromJson(Map<String, dynamic>.from(e)))
              .toList();
          _memberName = memberInfo['nickname']?.toString().isNotEmpty == true
              ? memberInfo['nickname'].toString()
              : '本人';
          _memberAge = memberInfo['age'] is int
              ? memberInfo['age'] as int
              : int.tryParse(memberInfo['age']?.toString() ?? '');
          _memberRelation = memberInfo['relationship_type']?.toString();

          // 合并：若首条 assistant 消息已存在于 historyMsgs 中（同 message_id），直接使用；
          // 否则把 opening 作为首条 assistant 消息 "插入到顶部"。
          final openingMsgId = opening['message_id'];
          _openingMessageId = openingMsgId is int
              ? openingMsgId
              : int.tryParse(openingMsgId?.toString() ?? '');
          final openingContent = opening['content_markdown']?.toString() ?? '';

          final alreadyHas = _openingMessageId != null &&
              historyMsgs.any((m) =>
                  (m['id'] is int ? m['id'] : int.tryParse(m['id']?.toString() ?? '')) ==
                  _openingMessageId);

          if (alreadyHas) {
            _messages = historyMsgs;
            // 更新匹配消息内容为最新版本
            final idx = _messages.indexWhere((m) =>
                (m['id'] is int ? m['id'] : int.tryParse(m['id']?.toString() ?? '')) ==
                _openingMessageId);
            if (idx >= 0 && openingContent.isNotEmpty) {
              _messages[idx] = {..._messages[idx], 'content': openingContent};
            }
          } else {
            final openingMsg = <String, dynamic>{
              'id': _openingMessageId ?? DateTime.now().millisecondsSinceEpoch,
              'role': 'assistant',
              'content': openingContent,
              'message_type': 'text',
              'is_opening': true,
              'created_at':
                  (opening['generated_at'] ?? DateTime.now().toIso8601String()).toString(),
            };
            // opening 插入到顶部，其它历史消息保持原顺序
            _messages = [
              openingMsg,
              ...historyMsgs.where((m) {
                final mid = m['id'] is int
                    ? m['id']
                    : int.tryParse(m['id']?.toString() ?? '');
                return mid != _openingMessageId;
              }),
            ];
          }
        });
      } else {
        setState(() => _messages = historyMsgs);
      }
    } catch (_) {
      // init 失败兜底：仅显示空会话
    }

    if (mounted) {
      setState(() => _isLoadingInit = false);
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
    if (!_scrollController.hasClients) return;
    Future.delayed(const Duration(milliseconds: 80), () {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 240),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _sendTextMessage() async {
    final text = _textController.text.trim();
    if (text.isEmpty || _isSending || _sessionId.isEmpty) return;
    _textController.clear();
    setState(() {
      _messages.add({
        'id': DateTime.now().millisecondsSinceEpoch.toString(),
        'role': 'user',
        'content': text,
        'message_type': 'text',
        'created_at': DateTime.now().toIso8601String(),
      });
      _isSending = true;
    });
    _scrollToBottom();

    try {
      final response = await _api.sendMessage(_sessionId, text);
      if (!mounted) return;
      if (response.statusCode == 200) {
        final aiData = response.data['data'] ?? response.data;
        setState(() => _messages.add(Map<String, dynamic>.from(aiData)));
      }
    } catch (_) {
      if (mounted) {
        setState(() => _messages.add({
              'id': DateTime.now().millisecondsSinceEpoch.toString(),
              'role': 'assistant',
              'content': '抱歉，网络异常，请稍后重试。',
              'message_type': 'text',
              'created_at': DateTime.now().toIso8601String(),
            }));
      }
    }
    if (mounted) setState(() => _isSending = false);
    _scrollToBottom();
  }

  Future<void> _regenerateOpening() async {
    if (_isRegenerating) return;
    final now = DateTime.now();
    if (_lastRegenTime != null &&
        now.difference(_lastRegenTime!).inSeconds < _kRegenDebounceSec) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请稍候…'), duration: Duration(seconds: 2)),
      );
      return;
    }
    final sid = int.tryParse(_sessionId);
    if (sid == null) return;

    setState(() => _isRegenerating = true);
    _lastRegenTime = now;

    try {
      final resp = await _api.drugChatRegenerateOpening(sid);
      if (!mounted) return;
      if (resp.statusCode == 200) {
        final d = resp.data is Map ? Map<String, dynamic>.from(resp.data) : {};
        final newContent = d['content_markdown']?.toString() ?? '';
        final newMsgId = d['message_id'];
        setState(() {
          _openingMessageId = newMsgId is int
              ? newMsgId
              : int.tryParse(newMsgId?.toString() ?? '') ?? _openingMessageId;
          final idx = _findOpeningIndex();
          if (idx >= 0 && newContent.isNotEmpty) {
            _messages[idx] = {
              ..._messages[idx],
              'id': _openingMessageId ?? _messages[idx]['id'],
              'content': newContent,
            };
          }
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              e.toString().contains('429') ? '请稍候…' : '重新生成失败，请稍后再试',
            ),
          ),
        );
      }
    }
    if (mounted) setState(() => _isRegenerating = false);
  }

  int _findOpeningIndex() {
    if (_openingMessageId != null) {
      final idx = _messages.indexWhere((m) {
        final mid = m['id'] is int ? m['id'] : int.tryParse(m['id']?.toString() ?? '');
        return mid == _openingMessageId;
      });
      if (idx >= 0) return idx;
    }
    return _messages.indexWhere((m) => m['role'] == 'assistant');
  }

  Future<void> _appendDrug() async {
    if (_drugs.length >= _kMaxDrugs) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('最多对比 2 个药品')),
      );
      return;
    }
    if (_isAppendingDrug) return;

    final XFile? pic = await _picker.pickImage(source: ImageSource.camera);
    if (pic == null || !mounted) return;

    setState(() => _isAppendingDrug = true);
    try {
      final resp = await _api.ocrAppendSingleDrug(
        pic.path,
        sessionId: _sessionId,
        familyMemberId: _familyMemberId,
      );
      if (!mounted) return;
      if (resp.statusCode == 200) {
        // 刷新 drug_list：重新调 init 即可拿到最新 drug_list + 可能更新的 opening
        await _loadInit();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('追加药品失败，请重试')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('网络异常，请稍后重试')),
        );
      }
    }
    if (mounted) setState(() => _isAppendingDrug = false);
  }

  Future<void> _shareDrug() async {
    if (_recordId == null) return;
    try {
      final response = await _api.shareDrugIdentify(_recordId!);
      if (!mounted) return;
      String link = '';
      if (response.statusCode == 200) {
        final d = response.data;
        link = d['data']?['share_url'] ?? d['share_url'] ?? '';
        if (link.isEmpty) {
          final token = d['data']?['share_token'] ?? d['share_token'] ?? '';
          if (token.isNotEmpty) {
            link = '${ApiConfig.baseUrl}/api/drug-identify/share/$token';
          }
        }
      }
      if (link.isNotEmpty) {
        await Clipboard.setData(ClipboardData(text: link));
      }
    } catch (_) {}
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('药物识别链接已复制到剪贴板')),
      );
    }
  }

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF7F7F9),
      appBar: CustomAppBar(
        title: _drugName,
        actions: [
          if (_recordId != null)
            IconButton(
              icon: const Icon(Icons.share_outlined, color: Colors.white),
              onPressed: _shareDrug,
            ),
        ],
      ),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            color: const Color(0xFFFFF7E6),
            child: Row(
              children: [
                const Icon(Icons.info_outline, size: 16, color: Color(0xFFFA8C16)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'AI建议仅供参考，用药请遵医嘱',
                    style: TextStyle(fontSize: 12, color: Colors.orange[700]),
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: _isLoadingInit
                ? const Center(child: CircularProgressIndicator(color: _kDrugPink))
                : _buildScrollingBody(),
          ),
          _buildInputBar(),
        ],
      ),
    );
  }

  Widget _buildScrollingBody() {
    return ListView(
      controller: _scrollController,
      padding: const EdgeInsets.only(bottom: 12),
      children: [
        if (_drugs.isNotEmpty)
          DrugMergeCardFlat(
            drugs: _drugs,
            memberName: _memberName,
            memberAge: _memberAge,
            memberRelation: _memberRelation,
          ),
        if (_drugs.isNotEmpty) _buildAddDrugButton(),
        if (_messages.isEmpty)
          _buildEmptyState()
        else
          ..._messages.map((m) => _buildMessageBubble(m)),
        if (_isSending) _buildLoadingBubble(),
        const SizedBox(height: 8),
      ],
    );
  }

  Widget _buildAddDrugButton() {
    final disabled = _drugs.length >= _kMaxDrugs || _isAppendingDrug;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
      child: SizedBox(
        width: double.infinity,
        height: 56,
        child: OutlinedButton.icon(
          onPressed: disabled
              ? () {
                  if (_drugs.length >= _kMaxDrugs) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('最多对比 2 个药品')),
                    );
                  }
                }
              : _appendDrug,
          icon: Icon(
            Icons.add_circle_outline,
            size: 20,
            color: disabled ? Colors.grey : _kDrugPink,
          ),
          label: Text(
            _isAppendingDrug ? '识别中…' : '➕ 再加一个药一起对比',
            style: TextStyle(
              fontSize: 16,
              color: disabled ? Colors.grey : _kDrugPink,
              fontWeight: FontWeight.w500,
            ),
          ),
          style: OutlinedButton.styleFrom(
            side: BorderSide(
              color: disabled ? Colors.grey.shade300 : _kDrugPink,
              width: 1,
            ),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            backgroundColor: Colors.white,
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 32),
      child: Column(
        children: [
          Icon(Icons.chat_bubble_outline, size: 48, color: Colors.grey[300]),
          const SizedBox(height: 10),
          Text('暂无消息', style: TextStyle(color: Colors.grey[500], fontSize: 16)),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(Map<String, dynamic> msg) {
    final isUser = msg['role'] == 'user';
    final content = msg['content']?.toString() ?? '';
    final msgId = msg['id'] is int
        ? msg['id']
        : int.tryParse(msg['id']?.toString() ?? '');
    final isOpening = !isUser &&
        (msg['is_opening'] == true ||
            (msgId != null && msgId == _openingMessageId));

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isUser) ...[
            _buildAvatar(false),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.78,
              ),
              padding: const EdgeInsets.fromLTRB(14, 12, 14, 8),
              decoration: BoxDecoration(
                color: isUser ? _kDrugPink : Colors.white,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(isUser ? 16 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 16),
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.04),
                    blurRadius: 6,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  isUser
                      ? Text(
                          content,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            height: 1.5,
                          ),
                        )
                      : _buildAiContent(content),
                  if (isOpening) _buildRegenerateButton(),
                ],
              ),
            ),
          ),
          if (isUser) ...[
            const SizedBox(width: 8),
            _buildAvatar(true),
          ],
        ],
      ),
    );
  }

  Widget _buildAiContent(String content) {
    // 过滤掉 prompt 要求追加的 "🔄 重新生成这条建议" 结尾占位（我们用独立按钮代替）
    var main = content;
    final splitIdx = main.indexOf('🔄 重新生成这条建议');
    if (splitIdx > 0) {
      main = main.substring(0, splitIdx);
      // 也去掉紧邻的 ---
      main = main.replaceAll(RegExp(r'\n?-{3,}\s*$'), '').trimRight();
    }
    return MarkdownBody(
      data: main,
      styleSheet: MarkdownStyleSheet(
        p: const TextStyle(fontSize: 16, height: 1.6, color: _kTextDark),
        h1: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: _kTextDark),
        h2: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: _kTextDark),
        h3: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: _kTextDark),
        listBullet: const TextStyle(fontSize: 16, color: _kTextDark),
        strong: const TextStyle(fontWeight: FontWeight.bold, color: _kTextDark),
      ),
    );
  }

  Widget _buildRegenerateButton() {
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Align(
        alignment: Alignment.centerLeft,
        child: TextButton(
          onPressed: _isRegenerating ? null : _regenerateOpening,
          style: TextButton.styleFrom(
            minimumSize: const Size(0, 40),
            padding: const EdgeInsets.symmetric(horizontal: 6),
            foregroundColor: _kDrugPink,
          ),
          child: Text(
            _isRegenerating ? '🔄 生成中…' : '🔄 重新生成这条建议',
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
          ),
        ),
      ),
    );
  }

  Widget _buildLoadingBubble() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAvatar(false),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.grey[400]),
                ),
                const SizedBox(width: 8),
                Text('正在思考中...', style: TextStyle(color: Colors.grey[500], fontSize: 14)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAvatar(bool isUser) {
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        gradient: isUser ? null : const LinearGradient(colors: [_kDrugPink, _kDrugPurple]),
        color: isUser ? const Color(0xFFFFE4F1) : null,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Icon(
        isUser ? Icons.person : Icons.medication,
        color: isUser ? _kDrugPink : Colors.white,
        size: 20,
      ),
    );
  }

  Widget _buildInputBar() {
    return Container(
      padding: EdgeInsets.only(
        left: 12,
        right: 12,
        top: 8,
        bottom: MediaQuery.of(context).padding.bottom + 8,
      ),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 8,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Row(
        children: [
          Expanded(
            child: Container(
              constraints: const BoxConstraints(minHeight: 44),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F7FA),
                borderRadius: BorderRadius.circular(22),
              ),
              child: TextField(
                controller: _textController,
                maxLines: 4,
                minLines: 1,
                style: const TextStyle(fontSize: 16, color: _kTextDark),
                decoration: const InputDecoration(
                  hintText: '输入用药问题...',
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  hintStyle: TextStyle(color: Color(0xFFBBBBBB)),
                ),
                onSubmitted: (_) => _sendTextMessage(),
              ),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: _isSending ? null : _sendTextMessage,
            child: Container(
              width: 56,
              height: 44,
              decoration: BoxDecoration(
                color: _isSending ? Colors.grey[300] : _kDrugPink,
                borderRadius: BorderRadius.circular(22),
              ),
              child: const Icon(Icons.send, color: Colors.white, size: 20),
            ),
          ),
        ],
      ),
    );
  }
}
