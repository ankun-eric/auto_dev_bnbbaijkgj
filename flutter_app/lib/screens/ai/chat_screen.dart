import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
import 'package:share_plus/share_plus.dart';
import '../../providers/chat_provider.dart';
import '../../models/chat_message.dart';
import '../../models/function_button.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/chat_history_drawer.dart';
import '../../widgets/knowledge_card.dart';
import '../../widgets/function_buttons_bar.dart';
import '../../services/api_service.dart';
import '../../services/sse_service.dart';
import '../../services/tts_service.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final ImagePicker _picker = ImagePicker();
  final ApiService _apiService = ApiService();
  final SseService _sseService = SseService();
  final TtsService _ttsService = TtsService();
  final AudioRecorder _audioRecorder = AudioRecorder();

  bool _isVoiceMode = false;
  bool _isRecording = false;
  bool _isCancelZone = false;

  List<FunctionButton> _functionButtons = [];
  DateTime? _functionButtonsCachedAt;
  static const _buttonsCacheDuration = Duration(minutes: 5);

  String _currentConsultTarget = '本人';
  bool _isSymptomLocked = false;
  List<Map<String, dynamic>> _familyMembers = [];
  
  // Route arguments for drug_identify / constitution flows
  String? _initialType;
  int? _initialFamilyMemberId;
  String? _summaryText;
  bool _argsProcessed = false;

  // Drug identify card state (与 H5/小程序对齐的顶部卡片)
  String _drugIdentifyMember = '';
  String _drugIdentifyDrugNames = '';
  
  DateTime? _recordStartTime;
  Timer? _recordTimer;
  Timer? _amplitudeTimer;
  int _recordElapsed = 0;
  List<double> _amplitudes = List.filled(7, 0.15);
  final Random _random = Random();
  OverlayEntry? _recordOverlay;

  // SSE streaming state
  bool _isStreaming = false;
  String _streamingContent = '';
  StreamSubscription? _sseSubscription;

  // Cursor blink for streaming
  bool _cursorVisible = true;
  Timer? _cursorTimer;

  static const Map<String, double> _fontSizeMap = {
    'standard': 14.0,
    'large': 18.0,
    'extra_large': 22.0,
  };

  static const Map<String, String> _fontLabelMap = {
    'standard': '标准',
    'large': '大',
    'extra_large': '超大',
  };

  String _fontSizeLevel = 'standard';
  double _chatFontSize = 14.0;

  static Color _relationColor(String relation) {
    if (relation == '本人') return const Color(0xFF52C41A);
    if (relation == '爸爸' || relation == '妈妈' || relation == '父亲' || relation == '母亲') {
      return const Color(0xFF1890FF);
    }
    if (relation == '儿子' || relation == '女儿' || relation == '子女') {
      return const Color(0xFFEB2F96);
    }
    if (relation == '爷爷' || relation == '奶奶') return const Color(0xFFFA8C16);
    return const Color(0xFF8C8C8C);
  }

  @override
  void initState() {
    super.initState();
    _loadFontSetting();
    _loadFamilyMembers();
    _loadFunctionButtons();
    _ttsService.onStateChanged = () {
      if (mounted) setState(() {});
    };
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _processRouteArguments();
      _initConsultTarget();
    });
  }

  void _processRouteArguments() {
    if (_argsProcessed) return;
    _argsProcessed = true;

    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is Map<String, dynamic>) {
      _initialType = args['type']?.toString();
      _initialFamilyMemberId = args['family_member_id'] is int
          ? args['family_member_id'] as int
          : int.tryParse(args['family_member_id']?.toString() ?? '');
      _summaryText = args['summary']?.toString();

      // 用药识别卡片参数（URL 参数优先）
      if (_initialType == 'drug_identify') {
        setState(() {
          _drugIdentifyMember = (args['member'] ?? '').toString();
          _drugIdentifyDrugNames = (args['drug_name'] ?? '').toString();
        });
      }

      if (_initialType == 'drug_identify' || _initialType == 'constitution') {
        setState(() => _isSymptomLocked = true);

        if (_initialFamilyMemberId != null) {
          final member = _familyMembers.firstWhere(
            (m) => m['id'] == _initialFamilyMemberId,
            orElse: () => <String, dynamic>{},
          );
          if (member.isNotEmpty) {
            setState(() {
              _currentConsultTarget = (member['relation_type_name'] ?? member['nickname'] ?? '家人').toString();
            });
          }
        }

        final chatProvider = Provider.of<ChatProvider>(context, listen: false);
        if (chatProvider.currentSession == null) {
          chatProvider.createSession(_initialType!).then((session) {
            if (session != null && mounted) {
              final initialMsg = args['initial_message']?.toString();
              if (initialMsg != null && initialMsg.isNotEmpty) {
                _sendMessageWithSSE(initialMsg);
              }
            }
          });
        }
      }
    }
  }

  Future<void> _loadFamilyMembers() async {
    try {
      final response = await _apiService.getFamilyMembers();
      if (response.statusCode == 200 && mounted) {
        final items = response.data['items'] as List? ?? [];
        setState(() {
          _familyMembers = items.map((e) => Map<String, dynamic>.from(e as Map)).toList();
        });
      }
    } catch (_) {}
  }

  void _initConsultTarget() {
    final chatProvider = Provider.of<ChatProvider>(context, listen: false);
    final session = chatProvider.currentSession;
    if (session != null) {
      final sessionType = session.type;
      if (sessionType == 'symptom_check' || sessionType == 'symptom') {
        setState(() => _isSymptomLocked = true);
        _restoreSessionMember(session.id);
      } else if (sessionType == 'drug_identify' || sessionType == 'drug_query') {
        // 用药识别也需要尝试 backend 兜底卡片信息
        _restoreSessionMember(session.id);
      }
    }
  }

  Future<void> _restoreSessionMember(String sessionId) async {
    try {
      final response = await _apiService.getChatSessionDetail(sessionId);
      if (response.statusCode == 200 && mounted) {
        final data = response.data is Map<String, dynamic> ? response.data as Map<String, dynamic> : <String, dynamic>{};
        final sessionType = data['session_type']?.toString() ?? '';
        if (sessionType == 'symptom_check' || sessionType == 'symptom') {
          final relation = data['family_member_relation'] as String?;
          if (relation != null && relation.isNotEmpty) {
            setState(() {
              _currentConsultTarget = relation;
              _isSymptomLocked = true;
            });
          }
        }
        // drug_identify 卡片 backend 兜底（仅当 URL 参数为空时填充）
        if (sessionType == 'drug_identify' || sessionType == 'drug_query') {
          final updates = <String, String>{};
          if (_drugIdentifyMember.isEmpty) {
            final fm = data['family_member'];
            final memberInfo = (data['family_member_relation'] ?? (fm is Map ? fm['nickname'] : null) ?? '').toString();
            if (memberInfo.isNotEmpty) updates['member'] = memberInfo;
          }
          if (_drugIdentifyDrugNames.isEmpty) {
            final apiDrugs = (data['drug_names'] ?? data['title'] ?? '').toString();
            if (apiDrugs.isNotEmpty) updates['drug'] = apiDrugs;
          }
          if (updates.isNotEmpty) {
            setState(() {
              if (updates.containsKey('member')) _drugIdentifyMember = updates['member']!;
              if (updates.containsKey('drug')) _drugIdentifyDrugNames = updates['drug']!;
            });
          }
        }
      }
    } catch (e) {
      debugPrint('restoreSessionMember error: $e');
    }
  }

  Future<void> _loadFunctionButtons() async {
    if (_functionButtonsCachedAt != null &&
        DateTime.now().difference(_functionButtonsCachedAt!) < _buttonsCacheDuration) {
      return;
    }
    try {
      final response = await _apiService.getFunctionButtons();
      if (response.statusCode == 200 && mounted) {
        final items = response.data['items'] as List? ?? response.data['data'] as List? ?? [];
        setState(() {
          _functionButtons = items
              .map((e) => FunctionButton.fromJson(Map<String, dynamic>.from(e as Map)))
              .where((b) => b.isEnabled)
              .toList()
            ..sort((a, b) => b.sortWeight.compareTo(a.sortWeight));
          _functionButtonsCachedAt = DateTime.now();
        });
      }
    } catch (_) {}
  }

  void _handleFunctionButton(FunctionButton btn) {
    switch (btn.buttonType) {
      case 'digital_human_call':
        Navigator.pushNamed(context, '/digital-human-call', arguments: {
          'sessionId': Provider.of<ChatProvider>(context, listen: false).currentSession?.id,
        });
        break;
      case 'photo_upload':
        _handlePhotoUpload();
        break;
      case 'file_upload':
        _handleFileUpload();
        break;
      case 'ai_dialog_trigger':
        final triggerMsg = btn.params?['trigger_message']?.toString() ?? btn.name;
        _sendMessageWithSSE(triggerMsg);
        break;
      case 'drug_identify':
        _handleDrugIdentifyButton(btn);
        break;
      case 'external_link':
        final url = btn.params?['url']?.toString();
        if (url != null && url.isNotEmpty) {
          launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
        }
        break;
    }
  }

  bool _isDrugIdentifying = false;

  void _handleDrugIdentifyButton(FunctionButton btn) {
    if (_isDrugIdentifying) return;
    final tipText = btn.params?['photo_tip_text']?.toString() ?? '请拍摄药品包装正面，确保文字清晰可见';
    final maxCount = btn.params?['max_photo_count'] ?? 5;

    showCupertinoModalPopup(
      context: context,
      builder: (ctx) => CupertinoActionSheet(
        title: Text(tipText),
        actions: [
          CupertinoActionSheetAction(
            onPressed: () {
              Navigator.pop(ctx);
              _drugIdentifyFromCamera();
            },
            child: const Text('拍照识药'),
          ),
          CupertinoActionSheetAction(
            onPressed: () {
              Navigator.pop(ctx);
              _drugIdentifyFromGallery(maxCount is int ? maxCount : 5);
            },
            child: const Text('从相册选择'),
          ),
        ],
        cancelButton: CupertinoActionSheetAction(
          isDestructiveAction: true,
          onPressed: () => Navigator.pop(ctx),
          child: const Text('取消'),
        ),
      ),
    );
  }

  Future<void> _drugIdentifyFromCamera() async {
    final image = await _picker.pickImage(source: ImageSource.camera);
    if (image == null || !mounted) return;
    await _processDrugIdentifyImages([image.path]);
  }

  Future<void> _drugIdentifyFromGallery(int maxCount) async {
    final images = await _picker.pickMultiImage();
    if (images.isEmpty || !mounted) return;
    final paths = images.take(maxCount).map((e) => e.path).toList();
    await _processDrugIdentifyImages(paths);
  }

  Future<void> _processDrugIdentifyImages(List<String> imagePaths) async {
    if (_isDrugIdentifying || !mounted) return;

    setState(() {
      _isDrugIdentifying = true;
      _isStreaming = true;
      _streamingContent = '正在识别药品...';
    });
    _startCursorBlink();

    try {
      final response = await _apiService.ocrBatchRecognize(imagePaths, sceneName: '拍照识药');
      if (!mounted) return;

      if (response.statusCode == 200) {
        final data = response.data is Map ? response.data as Map<String, dynamic> : <String, dynamic>{};
        final ocrTexts = <String>[];
        final items = data['items'] as List? ?? data['results'] as List? ?? [];
        for (final item in items) {
          final text = (item is Map ? (item['ocr_text'] ?? item['text'] ?? item['drug_name'] ?? '') : '').toString();
          if (text.isNotEmpty) ocrTexts.add(text);
        }
        final mergedText = data['merged_text']?.toString() ?? data['ocr_text']?.toString() ?? ocrTexts.join('\n');

        setState(() {
          _isStreaming = false;
          _streamingContent = '';
        });
        _stopCursorBlink();

        if (mergedText.isNotEmpty) {
          _sendMessageWithSSE('识别药品: $mergedText');
          Future.delayed(const Duration(seconds: 1), () {
            if (mounted && !_isStreaming) {
              _sendMessageWithSSE('请根据以上药品信息，提供详细的用药指导和注意事项');
            }
          });
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('未能识别药品，请重试')),
          );
        }
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _isStreaming = false;
          _streamingContent = '';
        });
        _stopCursorBlink();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('识别失败，请重试')),
        );
      }
    } finally {
      if (mounted) setState(() => _isDrugIdentifying = false);
    }
  }

  Future<void> _handlePhotoUpload() async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: const Icon(Icons.camera_alt, color: Color(0xFF52C41A)),
                title: const Text('拍照'),
                onTap: () => Navigator.pop(ctx, ImageSource.camera),
              ),
              ListTile(
                leading: const Icon(Icons.photo_library, color: Color(0xFF52C41A)),
                title: const Text('从相册选择'),
                onTap: () => Navigator.pop(ctx, ImageSource.gallery),
              ),
            ],
          ),
        ),
      ),
    );
    if (source == null) return;
    final image = await _picker.pickImage(source: source);
    if (image != null) {
      _sendMessageWithSSE(image.path, type: 'image');
    }
  }

  Future<void> _handleFileUpload() async {
    final result = await FilePicker.platform.pickFiles();
    if (result != null && result.files.single.path != null) {
      _sendMessageWithSSE(result.files.single.path!, type: 'file');
    }
  }

  // Module 5: Drug photo shortcut
  void _showDrugPhotoSheet() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('拍照识药', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 6),
              Text('拍摄药品包装，AI帮您解读用药信息', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: _buildDrugSheetOption(
                      icon: Icons.camera_alt,
                      label: '拍照识药',
                      color: const Color(0xFFEB2F96),
                      onTap: () {
                        Navigator.pop(ctx);
                        _pickDrugImage(ImageSource.camera);
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildDrugSheetOption(
                      icon: Icons.photo_library,
                      label: '相册选择',
                      color: const Color(0xFF722ED1),
                      onTap: () {
                        Navigator.pop(ctx);
                        _pickDrugImage(ImageSource.gallery);
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildDrugSheetOption(
                      icon: Icons.medication,
                      label: '识药记录',
                      color: const Color(0xFF1890FF),
                      onTap: () {
                        Navigator.pop(ctx);
                        Navigator.pushNamed(context, '/drug');
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDrugSheetOption({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 18),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          children: [
            Icon(icon, color: color, size: 28),
            const SizedBox(height: 8),
            Text(label, style: TextStyle(fontSize: 13, color: color, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }

  Future<void> _pickDrugImage(ImageSource source) async {
    final image = await _picker.pickImage(source: source);
    if (image == null || !mounted) return;

    final chatProvider = Provider.of<ChatProvider>(context, listen: false);
    final session = chatProvider.currentSession;
    if (session == null) return;

    // Show drug card placeholder
    setState(() {
      _isStreaming = true;
      _streamingContent = '正在识别药品...';
    });
    _startCursorBlink();

    try {
      final ocrResponse = await _apiService.ocrRecognizeDrug(image.path);
      if (!mounted) return;

      if (ocrResponse.statusCode == 200) {
        final ocrData = ocrResponse.data['data'] ?? ocrResponse.data;
        final drugName = ocrData['drug_name']?.toString() ?? ocrData['ocr_text']?.toString() ?? '';

        setState(() {
          _isStreaming = false;
          _streamingContent = '';
        });
        _stopCursorBlink();

        if (drugName.isNotEmpty) {
          _sendMessageWithSSE('识别药品: $drugName');
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('未能识别药品，请重试')),
          );
        }
      }
    } catch (_) {
      if (mounted) {
        setState(() { _isStreaming = false; _streamingContent = ''; });
        _stopCursorBlink();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('识别失败，请重试')),
        );
      }
    }
  }

  Future<void> _loadFontSetting() async {
    try {
      final result = await _apiService.getUserFontSetting();
      final level = result['font_size_level']?.toString() ?? 'standard';
      if (_fontSizeMap.containsKey(level) && mounted) {
        setState(() {
          _fontSizeLevel = level;
          _chatFontSize = _fontSizeMap[level]!;
        });
      }
    } catch (_) {}
  }

  Future<void> _switchFontSize(String level) async {
    if (level == _fontSizeLevel) return;
    setState(() {
      _fontSizeLevel = level;
      _chatFontSize = _fontSizeMap[level]!;
    });
    final label = _fontLabelMap[level] ?? '标准';
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('已切换为${label}字体'), duration: const Duration(milliseconds: 1500), backgroundColor: const Color(0xFF52C41A)),
      );
    }
    final success = await _apiService.updateUserFontSetting(level);
    if (!success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('保存失败，请稍后重试'), duration: Duration(milliseconds: 1500), backgroundColor: Colors.red),
      );
    }
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      Future.delayed(const Duration(milliseconds: 100), () {
        if (_scrollController.hasClients) {
          _scrollController.animateTo(
            _scrollController.position.maxScrollExtent,
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeOut,
          );
        }
      });
    }
  }

  // Module 6: SSE streaming with typewriter effect
  void _sendMessageWithSSE(String content, {String type = 'text'}) {
    if (_isStreaming) return;

    final chatProvider = Provider.of<ChatProvider>(context, listen: false);
    if (chatProvider.currentSession == null) return;

    final sessionId = chatProvider.currentSession!.id;

    chatProvider.addMessageExternally(ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: sessionId,
      role: 'user',
      content: content,
      type: type,
      createdAt: DateTime.now().toIso8601String(),
    ));

    setState(() {
      _isStreaming = true;
      _streamingContent = '';
    });
    _startCursorBlink();
    _scrollToBottom();

    _sseSubscription = _sseService.streamChat(sessionId, content, type: type).listen(
      (sseMsg) {
        if (!mounted) return;
        if (sseMsg.event == 'error') {
          _finishStreaming(sessionId, fallbackContent: '网络异常，请重试');
          return;
        }

        try {
          final data = jsonDecode(sseMsg.data);
          if (data is Map) {
            final chunk = data['content']?.toString() ?? data['delta']?.toString() ?? sseMsg.data;
            setState(() => _streamingContent += chunk);
            _scrollToBottom();

            if (data['done'] == true || data['finished'] == true) {
              _finishStreaming(sessionId);
            }
          } else {
            setState(() => _streamingContent += sseMsg.data);
            _scrollToBottom();
          }
        } catch (_) {
          setState(() => _streamingContent += sseMsg.data);
          _scrollToBottom();
        }
      },
      onDone: () {
        if (mounted && _isStreaming) {
          _finishStreaming(sessionId);
        }
      },
      onError: (_) {
        if (mounted) _finishStreaming(sessionId, fallbackContent: '网络异常，请重试');
      },
    );
  }

  void _finishStreaming(String sessionId, {String? fallbackContent}) {
    _sseSubscription?.cancel();
    _stopCursorBlink();

    final finalContent = _streamingContent.isNotEmpty ? _streamingContent : (fallbackContent ?? '抱歉，暂时无法回复。');

    final chatProvider = Provider.of<ChatProvider>(context, listen: false);
    chatProvider.addMessageExternally(ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: sessionId,
      role: 'assistant',
      content: finalContent,
      createdAt: DateTime.now().toIso8601String(),
    ));

    setState(() {
      _isStreaming = false;
      _streamingContent = '';
    });
    _scrollToBottom();
  }

  void _startCursorBlink() {
    _cursorTimer?.cancel();
    _cursorTimer = Timer.periodic(const Duration(milliseconds: 500), (_) {
      if (mounted) setState(() => _cursorVisible = !_cursorVisible);
    });
  }

  void _stopCursorBlink() {
    _cursorTimer?.cancel();
    _cursorVisible = true;
  }

  void _sendMessage() {
    final text = _textController.text.trim();
    if (text.isEmpty) return;
    _textController.clear();
    _sendMessageWithSSE(text);
  }

  Future<void> _pickImage() async {
    final image = await _picker.pickImage(source: ImageSource.gallery);
    if (image != null) {
      _sendMessageWithSSE(image.path, type: 'image');
    }
  }

  // Module 7 & 8: Copy, TTS, Share actions
  void _copyMessage(String content) {
    final cleanText = content.split('---disclaimer---').first.trim();
    Clipboard.setData(ClipboardData(text: cleanText));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('已复制到剪贴板'), duration: Duration(seconds: 1), backgroundColor: Color(0xFF52C41A)),
    );
  }

  void _speakMessage(ChatMessage message) {
    _ttsService.speak(message.content, messageId: message.id);
  }

  Future<void> _shareMessage(ChatMessage message) async {
    final cleanText = message.content.split('---disclaimer---').first.trim();

    try {
      final chatProvider = Provider.of<ChatProvider>(context, listen: false);
      final sessionId = chatProvider.currentSession?.id ?? '';
      final response = await _apiService.generateSharePoster(sessionId, message.id);
      if (response.statusCode == 200) {
        final shareUrl = response.data['share_url']?.toString() ?? response.data['data']?['share_url']?.toString() ?? '';
        if (shareUrl.isNotEmpty) {
          await Share.share('$cleanText\n\n$shareUrl', subject: 'AI健康咨询');
          return;
        }
      }
    } catch (_) {}

    await Share.share(cleanText, subject: 'AI健康咨询');
  }

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    _recordTimer?.cancel();
    _amplitudeTimer?.cancel();
    _audioRecorder.dispose();
    _recordOverlay?.remove();
    _sseSubscription?.cancel();
    _cursorTimer?.cancel();
    _ttsService.stop();
    super.dispose();
  }

  // ── Voice Input ──

  void _toggleVoiceMode() {
    setState(() => _isVoiceMode = !_isVoiceMode);
  }

  Future<bool> _requestMicPermission() async {
    var status = await Permission.microphone.status;
    if (status.isGranted) return true;

    if (status.isPermanentlyDenied) {
      if (!mounted) return false;
      final goSettings = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('允许访问麦克风'),
          content: const Text('麦克风权限已被永久拒绝，请前往系统设置手动开启'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
            TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('去设置', style: TextStyle(color: Color(0xFF52C41A)))),
          ],
        ),
      );
      if (goSettings == true) openAppSettings();
      return false;
    }

    status = await Permission.microphone.request();
    if (status.isGranted) return true;

    if (!mounted) return false;
    final goSettings = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('允许访问麦克风'),
        content: const Text('请授权麦克风，以便AI发送语音消息'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('去授权', style: TextStyle(color: Color(0xFF52C41A)))),
        ],
      ),
    );
    if (goSettings == true) {
      openAppSettings();
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('请在设置中开启麦克风权限')));
    }
    return false;
  }

  Future<void> _onHoldStart() async {
    final granted = await _requestMicPermission();
    if (!granted || !mounted) return;

    final tempDir = Directory.systemTemp;
    final filePath = '${tempDir.path}/${DateTime.now().millisecondsSinceEpoch}.m4a';

    try {
      await _audioRecorder.start(
        const RecordConfig(encoder: AudioEncoder.aacLc, sampleRate: 16000, numChannels: 1),
        path: filePath,
      );
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('录音启动失败')));
      return;
    }

    _recordStartTime = DateTime.now();
    _recordElapsed = 0;
    _isCancelZone = false;
    _amplitudes = List.filled(7, 0.15);

    setState(() => _isRecording = true);
    _showRecordOverlay();

    _recordTimer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return;
      _recordElapsed++;
      _recordOverlay?.markNeedsBuild();
      if (_recordElapsed >= 30) _onHoldEnd(cancelled: false);
    });

    _amplitudeTimer = Timer.periodic(const Duration(milliseconds: 150), (_) async {
      try {
        final amp = await _audioRecorder.getAmplitude();
        if (!mounted || !_isRecording) return;
        final normalized = ((amp.current + 50) / 50).clamp(0.1, 1.0);
        _amplitudes = List.generate(7, (i) => (normalized * (0.5 + _random.nextDouble() * 0.5)).clamp(0.15, 1.0));
        _recordOverlay?.markNeedsBuild();
      } catch (_) {}
    });
  }

  Future<void> _onHoldEnd({required bool cancelled}) async {
    _recordTimer?.cancel();
    _amplitudeTimer?.cancel();

    final wasTooShort = _recordStartTime != null && DateTime.now().difference(_recordStartTime!).inMilliseconds < 500;
    String? filePath;
    try { filePath = await _audioRecorder.stop(); } catch (_) {}

    _removeRecordOverlay();
    setState(() => _isRecording = false);

    if (wasTooShort) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('录音时间太短')));
      _cleanupRecordFile(filePath);
      return;
    }
    if (cancelled || _isCancelZone) { _cleanupRecordFile(filePath); return; }
    if (filePath == null || filePath.isEmpty) return;
    await _recognizeAndSend(filePath);
  }

  void _cleanupRecordFile(String? path) {
    if (path == null) return;
    try { final f = File(path); if (f.existsSync()) f.deleteSync(); } catch (_) {}
  }

  Future<void> _recognizeAndSend(String filePath) async {
    if (!mounted) return;
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(
        child: Card(
          child: Padding(
            padding: EdgeInsets.all(24),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              CircularProgressIndicator(color: Color(0xFF52C41A)),
              SizedBox(height: 16),
              Text('正在识别...'),
            ]),
          ),
        ),
      ),
    );

    try {
      final result = await _apiService.asrRecognize(filePath, 'm4a');
      if (!mounted) return;
      Navigator.of(context).pop();

      if (result['success'] == false) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('未识别到语音内容，请重试')));
        return;
      }

      final asrData = result['data'];
      final rawText = (asrData is Map ? asrData['text']?.toString() : null) ?? result['text']?.toString() ?? '';
      final text = rawText.trim();

      if (text.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('未识别到语音内容，请重试')));
        return;
      }

      _sendMessageWithSSE(text);
    } catch (_) {
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('语音服务暂不可用，已切换为键盘输入')));
      setState(() => _isVoiceMode = false);
    } finally {
      _cleanupRecordFile(filePath);
    }
  }

  void _showRecordOverlay() {
    _recordOverlay = OverlayEntry(builder: (context) {
      return _VoiceRecordOverlay(amplitudes: _amplitudes, elapsed: _recordElapsed, isCancelZone: _isCancelZone);
    });
    Overlay.of(context).insert(_recordOverlay!);
  }

  void _removeRecordOverlay() {
    _recordOverlay?.remove();
    _recordOverlay = null;
  }

  void _onHoldUpdate(Offset localPosition) {
    if (!_isRecording) return;
    final wasCancelZone = _isCancelZone;
    _isCancelZone = localPosition.dy < -80;
    if (wasCancelZone != _isCancelZone) _recordOverlay?.markNeedsBuild();
  }

  void _showFontSizeMenu() {
    final overlay = Overlay.of(context).context.findRenderObject() as RenderBox;
    showMenu<String>(
      context: context,
      position: RelativeRect.fromRect(
        Rect.fromLTWH(overlay.size.width - 160, kToolbarHeight + MediaQuery.of(context).padding.top, 140, 0),
        Offset.zero & overlay.size,
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      items: _fontSizeMap.keys.map((level) {
        final label = _fontLabelMap[level]!;
        final size = _fontSizeMap[level]!;
        final isSelected = level == _fontSizeLevel;
        return PopupMenuItem<String>(
          value: level,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('$label（${size.toInt()}px）', style: TextStyle(
                fontSize: 14, color: isSelected ? const Color(0xFF52C41A) : const Color(0xFF333333),
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
              )),
              if (isSelected) const Icon(Icons.check, color: Color(0xFF52C41A), size: 18),
            ],
          ),
        );
      }).toList(),
    ).then((value) { if (value != null) _switchFontSize(value); });
  }

  Widget _buildDrugIdentifyBanner() {
    if (_initialType != 'drug_identify') return const SizedBox.shrink();
    if (_drugIdentifyMember.isEmpty && _drugIdentifyDrugNames.isEmpty) return const SizedBox.shrink();
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF7E6),
        borderRadius: BorderRadius.circular(8),
        border: const Border(left: BorderSide(color: Color(0xFFFA8C16), width: 4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('💊', style: TextStyle(fontSize: 14)),
              const SizedBox(width: 6),
              const Text(
                '用药识别',
                style: TextStyle(color: Color(0xFFFA8C16), fontWeight: FontWeight.w600, fontSize: 13),
              ),
              if (_drugIdentifyMember.isNotEmpty) ...[
                const Spacer(),
                Text(
                  '咨询对象：$_drugIdentifyMember',
                  style: const TextStyle(color: Color(0xFFFA8C16), fontSize: 12),
                ),
              ],
            ],
          ),
          if (_drugIdentifyDrugNames.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                _drugIdentifyDrugNames,
                style: const TextStyle(color: Color(0xFF595959), fontSize: 12, height: 1.4),
              ),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: _scaffoldKey,
      drawer: ChatHistoryDrawer(onSessionTap: (session) {}),
      appBar: CustomAppBar(
        title: Provider.of<ChatProvider>(context).currentSession?.typeLabel ?? 'AI健康咨询',
        actions: [
          IconButton(
            icon: const Text('Aa', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
            onPressed: _showFontSizeMenu,
          ),
          IconButton(icon: const Icon(Icons.history, color: Colors.white), onPressed: () => _scaffoldKey.currentState?.openDrawer()),
          IconButton(icon: const Icon(Icons.more_horiz, color: Colors.white), onPressed: () {}),
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
                Expanded(child: Text('AI建议仅供参考，如有不适请及时就医', style: TextStyle(fontSize: 12, color: Colors.orange[700]))),
              ],
            ),
          ),
          _buildDrugIdentifyBanner(),
          if (_summaryText != null && _summaryText!.isNotEmpty)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                color: _initialType == 'constitution'
                    ? const Color(0xFFF9F0FF)
                    : const Color(0xFFFFF0F6),
                border: Border(
                  bottom: BorderSide(
                    color: _initialType == 'constitution'
                        ? const Color(0xFF722ED1).withOpacity(0.2)
                        : const Color(0xFFEB2F96).withOpacity(0.2),
                  ),
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    _initialType == 'constitution' ? Icons.spa : Icons.medication,
                    size: 16,
                    color: _initialType == 'constitution'
                        ? const Color(0xFF722ED1)
                        : const Color(0xFFEB2F96),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _summaryText!,
                      style: TextStyle(
                        fontSize: 13,
                        color: _initialType == 'constitution'
                            ? const Color(0xFF722ED1)
                            : const Color(0xFFEB2F96),
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
          Expanded(
            child: Consumer<ChatProvider>(
              builder: (context, chatProvider, child) {
                final messages = chatProvider.messages;
                if (messages.isEmpty && !_isStreaming) return _buildWelcome();

                final itemCount = messages.length + (_isStreaming ? 1 : 0);
                return ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  itemCount: itemCount,
                  itemBuilder: (context, index) {
                    if (index == messages.length && _isStreaming) {
                      return _buildStreamingBubble();
                    }
                    final message = messages[index];
                    final isLastAi = !message.isUser && _findLastAiIndex(messages) == index;
                    return _buildMessageBubble(message, showActions: isLastAi && !_isStreaming);
                  },
                );
              },
            ),
          ),
          FunctionButtonsBar(buttons: _functionButtons, onButtonTap: _handleFunctionButton),
          _buildInputBar(),
        ],
      ),
    );
  }

  int _findLastAiIndex(List<ChatMessage> messages) {
    for (int i = messages.length - 1; i >= 0; i--) {
      if (messages[i].isAssistant && !messages[i].isLoading) return i;
    }
    return -1;
  }

  Widget _buildStreamingBubble() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAvatar(false),
          const SizedBox(width: 10),
          Flexible(
            child: Container(
              constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.7),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(16), topRight: Radius.circular(16),
                  bottomLeft: Radius.circular(4), bottomRight: Radius.circular(16),
                ),
                boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 6, offset: const Offset(0, 2))],
              ),
              child: _streamingContent.isEmpty
                  ? Row(mainAxisSize: MainAxisSize.min, children: [
                      SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.grey[400])),
                      const SizedBox(width: 8),
                      Text('正在思考中...', style: TextStyle(color: Colors.grey[500], fontSize: 14)),
                    ])
                  : RichText(
                      text: TextSpan(
                        style: TextStyle(fontSize: _chatFontSize, height: 1.6, color: const Color(0xFF333333)),
                        children: [
                          TextSpan(text: _streamingContent),
                          if (_cursorVisible)
                            const TextSpan(text: '▌', style: TextStyle(color: Color(0xFF52C41A), fontWeight: FontWeight.bold)),
                        ],
                      ),
                    ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWelcome() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          const SizedBox(height: 40),
          Container(
            width: 70, height: 70,
            decoration: BoxDecoration(
              gradient: const LinearGradient(colors: [Color(0xFF52C41A), Color(0xFF13C2C2)]),
              borderRadius: BorderRadius.circular(18),
            ),
            child: const Icon(Icons.smart_toy, color: Colors.white, size: 36),
          ),
          const SizedBox(height: 16),
          const Text('您好，我是小康AI健康顾问', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text('请描述您的症状或健康问题，我会为您提供专业的健康建议。',
            textAlign: TextAlign.center, style: TextStyle(fontSize: 14, color: Colors.grey[600], height: 1.5)),
          const SizedBox(height: 32),
          const Text('常见问题', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF333333))),
          const SizedBox(height: 12),
          ...['最近总是头痛怎么回事？', '感冒了应该吃什么药？', '血压偏高如何调理？', '失眠有什么好的解决方法？'].map((q) => GestureDetector(
            onTap: () {
              _textController.text = q;
              _sendMessage();
            },
            child: Container(
              width: double.infinity,
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: const Color(0xFFF0F9EB),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFF52C41A).withOpacity(0.2)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.chat_bubble_outline, size: 16, color: Color(0xFF52C41A)),
                  const SizedBox(width: 10),
                  Text(q, style: const TextStyle(fontSize: 14, color: Color(0xFF333333))),
                ],
              ),
            ),
          )),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(ChatMessage message, {bool showActions = false}) {
    final isUser = message.isUser;

    if (message.isLoading) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildAvatar(false),
            const SizedBox(width: 10),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.grey[400])),
                const SizedBox(width: 8),
                Text('正在思考中...', style: TextStyle(color: Colors.grey[500], fontSize: 14)),
              ]),
            ),
          ],
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Column(
        crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
            children: [
              if (!isUser) ...[_buildAvatar(false), const SizedBox(width: 10)],
              Flexible(
                child: Container(
                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.7),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: isUser ? const Color(0xFF52C41A) : Colors.white,
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(16), topRight: const Radius.circular(16),
                      bottomLeft: Radius.circular(isUser ? 16 : 4), bottomRight: Radius.circular(isUser ? 4 : 16),
                    ),
                    boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 6, offset: const Offset(0, 2))],
                  ),
                  child: isUser
                      ? Text(message.content, style: TextStyle(color: Colors.white, fontSize: _chatFontSize, height: 1.5))
                      : _buildAiMessageContent(message),
                ),
              ),
              if (isUser) ...[const SizedBox(width: 10), _buildAvatar(true)],
            ],
          ),
          // Module 7: Bottom action buttons for last AI message
          if (showActions && !isUser)
            Padding(
              padding: const EdgeInsets.only(left: 46, top: 8),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _buildActionButton(
                    icon: Icons.copy,
                    label: '复制',
                    onTap: () => _copyMessage(message.content),
                  ),
                  const SizedBox(width: 16),
                  _buildActionButton(
                    icon: _ttsService.isPlaying && _ttsService.currentPlayingId == message.id
                        ? Icons.stop_circle_outlined
                        : Icons.volume_up,
                    label: _ttsService.isPlaying && _ttsService.currentPlayingId == message.id ? '停止' : '播报',
                    onTap: () => _speakMessage(message),
                    isActive: _ttsService.isPlaying && _ttsService.currentPlayingId == message.id,
                  ),
                  const SizedBox(width: 16),
                  _buildActionButton(
                    icon: Icons.share,
                    label: '分享',
                    onTap: () => _shareMessage(message),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildActionButton({required IconData icon, required String label, required VoidCallback onTap, bool isActive = false}) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isActive ? const Color(0xFF52C41A).withOpacity(0.1) : const Color(0xFFF5F5F5),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: isActive ? const Color(0xFF52C41A).withOpacity(0.3) : Colors.grey[300]!),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: isActive ? const Color(0xFF52C41A) : Colors.grey[600]),
            const SizedBox(width: 4),
            Text(label, style: TextStyle(fontSize: 12, color: isActive ? const Color(0xFF52C41A) : Colors.grey[600])),
          ],
        ),
      ),
    );
  }

  Widget _buildAiMessageContent(ChatMessage message) {
    final parts = message.content.split('---disclaimer---');
    final mainContent = parts[0].trim();
    final disclaimer = parts.length > 1 ? parts[1].trim() : null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        MarkdownBody(
          data: mainContent,
          styleSheet: MarkdownStyleSheet(
            p: TextStyle(fontSize: _chatFontSize, height: 1.6, color: const Color(0xFF333333)),
            h1: TextStyle(fontSize: _chatFontSize + 5, fontWeight: FontWeight.bold),
            h2: TextStyle(fontSize: _chatFontSize + 3, fontWeight: FontWeight.bold),
            h3: TextStyle(fontSize: _chatFontSize + 1, fontWeight: FontWeight.bold),
            listBullet: TextStyle(fontSize: _chatFontSize),
          ),
        ),
        if (disclaimer != null) ...[
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.only(top: 8),
            decoration: const BoxDecoration(border: Border(top: BorderSide(color: Color(0xFFE8E8E8), width: 0.5))),
            child: Text(disclaimer, style: const TextStyle(fontSize: 11, color: Color(0xFF999999), fontStyle: FontStyle.italic, height: 1.4)),
          ),
        ],
        if (message.knowledgeHits != null && message.knowledgeHits!.isNotEmpty)
          ...message.knowledgeHits!.map((h) => KnowledgeCard(
            hit: h,
            onFeedback: (hitLogId, feedback) => Provider.of<ChatProvider>(context, listen: false).submitKnowledgeFeedback(hitLogId, feedback),
          )),
      ],
    );
  }

  Widget _buildAvatar(bool isUser) {
    return Container(
      width: 36, height: 36,
      decoration: BoxDecoration(
        gradient: isUser ? null : const LinearGradient(colors: [Color(0xFF52C41A), Color(0xFF13C2C2)]),
        color: isUser ? const Color(0xFFE8F5E9) : null,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Icon(isUser ? Icons.person : Icons.smart_toy, color: isUser ? const Color(0xFF52C41A) : Colors.white, size: 20),
    );
  }

  void _showConsultTargetPicker() {
    if (_isSymptomLocked) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('当前为健康自查专属咨询，咨询对象已锁定，如需为其他人咨询请返回重新发起'), duration: Duration(milliseconds: 2500)),
      );
      return;
    }
    final targets = <Map<String, String>>[
      {'name': '本人'},
      ..._familyMembers.where((m) => m['is_self'] != true).map((m) => {'name': (m['relation_type_name'] ?? m['nickname'] ?? '').toString()}),
    ];
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('选择咨询对象', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: targets.map((t) {
                  final name = t['name']!;
                  final color = _relationColor(name);
                  final isSelected = _currentConsultTarget == name;
                  return GestureDetector(
                    onTap: () { setState(() => _currentConsultTarget = name); Navigator.pop(ctx); },
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 44, height: 44,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: isSelected ? color : const Color(0xFFF0F0F0),
                            border: isSelected ? Border.all(color: color, width: 2) : null,
                          ),
                          alignment: Alignment.center,
                          child: Text(name.length > 2 ? name.substring(0, 2) : name, style: TextStyle(
                            fontSize: 13, fontWeight: FontWeight.w600,
                            color: isSelected ? Colors.white : const Color(0xFF333333),
                          )),
                        ),
                        const SizedBox(height: 4),
                        Text(name, style: const TextStyle(fontSize: 11, color: Color(0xFF666666))),
                      ],
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 16),
            ],
          ),
        );
      },
    );
  }

  Widget _buildInputBar() {
    final targetColor = _relationColor(_currentConsultTarget);
    return Container(
      padding: EdgeInsets.only(left: 8, right: 8, top: 8, bottom: MediaQuery.of(context).padding.bottom + 8),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius: 8, offset: const Offset(0, -2))],
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: _showConsultTargetPicker,
            child: Container(
              width: 36, height: 36,
              decoration: BoxDecoration(shape: BoxShape.circle, color: targetColor),
              alignment: Alignment.center,
              child: Text(
                _currentConsultTarget.length > 2 ? _currentConsultTarget.substring(0, 2) : _currentConsultTarget,
                style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
              ),
            ),
          ),
          const SizedBox(width: 4),
          IconButton(
            icon: Icon(_isVoiceMode ? Icons.keyboard : Icons.mic, color: const Color(0xFF52C41A), size: 22),
            constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
            padding: EdgeInsets.zero,
            onPressed: _toggleVoiceMode,
          ),
          Expanded(child: _isVoiceMode ? _buildHoldToTalkButton() : _buildTextField()),
          // Module 5: Drug photo shortcut button
          IconButton(
            icon: const Icon(Icons.medication_outlined, color: Color(0xFFEB2F96), size: 22),
            constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
            padding: EdgeInsets.zero,
            onPressed: _showDrugPhotoSheet,
            tooltip: '拍照识药',
          ),
          IconButton(
            icon: const Icon(Icons.photo_outlined, color: Color(0xFF52C41A), size: 22),
            constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
            padding: EdgeInsets.zero,
            onPressed: _pickImage,
          ),
          const SizedBox(width: 4),
          GestureDetector(
            onTap: _sendMessage,
            child: Container(
              width: 36, height: 36,
              decoration: BoxDecoration(color: const Color(0xFF52C41A), borderRadius: BorderRadius.circular(18)),
              child: const Icon(Icons.send, color: Colors.white, size: 16),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTextField() {
    return Container(
      decoration: BoxDecoration(color: const Color(0xFFF5F7FA), borderRadius: BorderRadius.circular(20)),
      child: TextField(
        controller: _textController,
        maxLines: 3,
        minLines: 1,
        decoration: const InputDecoration(
          hintText: '发信息...',
          border: InputBorder.none,
          contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          hintStyle: TextStyle(color: Color(0xFFBBBBBB)),
        ),
        onSubmitted: (_) => _sendMessage(),
      ),
    );
  }

  Widget _buildHoldToTalkButton() {
    return GestureDetector(
      onLongPressStart: (_) => _onHoldStart(),
      onLongPressMoveUpdate: (details) => _onHoldUpdate(details.localPosition),
      onLongPressEnd: (_) => _onHoldEnd(cancelled: false),
      onLongPressCancel: () { if (_isRecording) _onHoldEnd(cancelled: true); },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        height: 44,
        decoration: BoxDecoration(
          color: _isRecording ? const Color(0xFF3DA512) : const Color(0xFF52C41A),
          borderRadius: BorderRadius.circular(20),
        ),
        alignment: Alignment.center,
        child: Text(_isRecording ? '松开结束' : '按住说话', style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w500)),
      ),
    );
  }
}

class _VoiceRecordOverlay extends StatelessWidget {
  final List<double> amplitudes;
  final int elapsed;
  final bool isCancelZone;

  const _VoiceRecordOverlay({required this.amplitudes, required this.elapsed, required this.isCancelZone});

  @override
  Widget build(BuildContext context) {
    final remaining = 30 - elapsed;
    return Material(
      color: Colors.black.withOpacity(0.5),
      child: SizedBox.expand(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Spacer(),
            if (isCancelZone)
              Container(
                width: 80, height: 80,
                decoration: const BoxDecoration(color: Colors.redAccent, shape: BoxShape.circle),
                child: const Icon(Icons.delete_outline, color: Colors.white, size: 36),
              )
            else
              SizedBox(
                height: 80,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: List.generate(7, (i) {
                    return AnimatedContainer(
                      duration: const Duration(milliseconds: 150),
                      width: 6, height: 80 * amplitudes[i],
                      margin: const EdgeInsets.symmetric(horizontal: 3),
                      decoration: BoxDecoration(color: const Color(0xFF52C41A), borderRadius: BorderRadius.circular(3)),
                    );
                  }),
                ),
              ),
            const SizedBox(height: 16),
            Text('$elapsed″ / 30″', style: TextStyle(
              color: remaining <= 5 ? Colors.redAccent : Colors.white, fontSize: 16, fontWeight: FontWeight.w600,
            )),
            const SizedBox(height: 24),
            Text(isCancelZone ? '松开取消' : '松开发送，上滑取消', style: TextStyle(
              color: isCancelZone ? Colors.redAccent : Colors.white70, fontSize: 14,
            )),
            const Spacer(),
          ],
        ),
      ),
    );
  }
}
