import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:dio/dio.dart';
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
import '../../widgets/ai_profile_card.dart';
import '../../widgets/health_self_check_drawer.dart';
import '../../widgets/health_self_check_card.dart';
// [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] AI 对话页问卷结果卡片 & 追问 chips
import '../../widgets/ai_chat/questionnaire_result_card.dart';
import '../../widgets/ai_chat/followup_chips_row.dart';
import '../health/constitution_result_screen.dart';
import '../../services/api_service.dart';
import '../../services/sse_service.dart';
import '../../services/tts_service.dart';
import '../../utils/datetime_utils.dart';

// [PRD-433 v1.0] 气泡卡片化视觉改版 - 设计 Token（与 H5/小程序严格一致）
class _ChatTokens {
  static const Color userBubbleBg = Color(0xFFE6F0FF);
  static const Color userBubbleText = Color(0xFF1F2937);
  static const Color aiCardBg = Colors.white;
  static const Color aiCardBorder = Color(0xFFEAEBED);
  static const Color senderName = Color(0xFF666666);
  static const Color disclaimerText = Color(0xFF9CA3AF);
  static const Color loadingText = Color(0xFF6B7280);
  static const Color inputBg = Color(0xFFF5F7FA);
  static const Color timeDividerText = Color(0xFF9CA3AF);
  static const double userBubbleRadius = 14;
  static const double aiCardRadius = 12;
  static const double inputRadius = 22;
  static const double aiCardWidthRatio = 0.88;
  static const double userBubbleMaxWidthRatio = 0.75;
  static const double userBubbleMaxWidth = 540;
  static const Duration timeDividerThreshold = Duration(minutes: 5);
  static const String disclaimer = 'AI 生成内容仅供参考，不作为诊断依据';
}

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

  // [PRD-AI-HOME-OPTIM-V4 2026-05-21] 切换咨询人三重提示
  bool _v4UndoBarVisible = false;
  String _v4UndoBarText = '';
  String? _v4SwitchSystemMsgText; // 永久留痕的系统消息（在消息列表上方常驻显示）
  String? _v4PrevTargetForUndo;
  Timer? _v4UndoTimer;
  
  // Route arguments for drug_identify / constitution flows
  String? _initialType;
  int? _initialFamilyMemberId;
  String? _summaryText;
  bool _argsProcessed = false;

  // Drug identify card state (与 H5/小程序对齐的顶部卡片)
  String _drugIdentifyMember = '';
  String _drugIdentifyDrugNames = '';

  // [2026-04-23 报告分支] 体检报告解读/对比 顶部卡片所需状态
  int? _reportIdForLoad;
  List<int> _reportIdsForLoad = const [];
  bool _autoStart = false;
  // 每个元素含 id/title/file_urls/thumbnail_urls
  List<Map<String, dynamic>> _reportCards = [];
  
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

  // [2026-04-25 PRD F5] 报告解读 OCR 详情默认隐藏 + 兜底入口
  bool _ocrDetailExpanded = false;
  bool _ocrDetailLoaded = false;
  bool _ocrDetailLoading = false;
  String _ocrDetailText = '';

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

      // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 注入"卡片消息协议"序列
      // 来源：tcm_screen 提交体质测评后跳过来时通过 arguments 传递
      if (_initialType == 'constitution_test' || _initialType == 'constitution') {
        setState(() => _isSymptomLocked = true);
        final pending = args['pending_qn_chat_messages'];
        final answerId = args['pending_qn_answer_id'];
        final qnCode = args['pending_qn_code']?.toString() ?? '';
        final cardPayloadArg = args['pending_qn_result_card_payload'];
        if (pending is List && pending.isNotEmpty) {
          final chatProvider = Provider.of<ChatProvider>(context, listen: false);
          // 确保有 session
          Future<void> ensureAndInject() async {
            if (chatProvider.currentSession == null) {
              await chatProvider.createSession('constitution');
            }
            if (!mounted) return;
            final sessionId = chatProvider.currentSession?.id?.toString() ?? '';
            final fallbackPayload = cardPayloadArg is Map
                ? Map<String, dynamic>.from(cardPayloadArg)
                : <String, dynamic>{};
            for (int i = 0; i < pending.length; i++) {
              final m = pending[i];
              if (m is! Map) continue;
              final t = (m['type'] ?? '').toString();
              if (t == 'questionnaire_result_card') {
                final card = m['card'] is Map
                    ? Map<String, dynamic>.from(m['card'] as Map)
                    : fallbackPayload;
                chatProvider.addMessageExternally(ChatMessage(
                  id: 'qn-card-$answerId-$i',
                  sessionId: sessionId,
                  role: 'assistant',
                  content: '',
                  type: 'questionnaire_result_card',
                  questionnaireResultPayload: card,
                  questionnaireAnswerId: answerId is int ? answerId : null,
                  questionnaireCode: qnCode,
                  createdAt: DateTime.now().toIso8601String(),
                ));
              } else if (t == 'text') {
                final text = (m['text'] ?? '').toString();
                chatProvider.addMessageExternally(ChatMessage(
                  id: 'qn-text-$answerId-$i',
                  sessionId: sessionId,
                  role: 'assistant',
                  content: text,
                  type: 'text',
                  createdAt: DateTime.now().toIso8601String(),
                ));
              } else if (t == 'followup_chips') {
                final chips = (m['chips'] as List?)
                        ?.whereType<Map>()
                        .map((e) => Map<String, dynamic>.from(e))
                        .toList() ??
                    <Map<String, dynamic>>[];
                chatProvider.addMessageExternally(ChatMessage(
                  id: 'qn-chips-$answerId-$i',
                  sessionId: sessionId,
                  role: 'assistant',
                  content: '',
                  type: 'followup_chips',
                  followupChips: chips,
                  questionnaireAnswerId: answerId is int ? answerId : null,
                  questionnaireCode: qnCode,
                  createdAt: DateTime.now().toIso8601String(),
                ));
              }
            }
          }
          ensureAndInject();
        }
      }

      // [2026-04-23 报告分支] 体检报告解读 / 体检报告对比
      if (_initialType == 'report_interpret' || _initialType == 'report_compare') {
        setState(() => _isSymptomLocked = true);

        final rid = args['report_id'];
        _reportIdForLoad = rid is int ? rid : int.tryParse(rid?.toString() ?? '');

        final rids = args['report_ids'];
        if (rids is String && rids.isNotEmpty) {
          _reportIdsForLoad = rids
              .split(',')
              .map((e) => int.tryParse(e.trim()) ?? 0)
              .where((v) => v > 0)
              .toList();
        } else if (rids is List) {
          _reportIdsForLoad = rids
              .map((e) => e is int ? e : int.tryParse(e.toString()) ?? 0)
              .where((v) => v > 0)
              .toList();
        } else {
          _reportIdsForLoad = const [];
        }

        _autoStart = (args['auto_start']?.toString() == '1');

        _loadReportBriefsAndMaybeAutoStart();
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
      } else if (sessionType == 'report_interpret' || sessionType == 'report_compare') {
        // [2026-04-25 Bug-04] 报告会话恢复：先本地锁定，再异步从 backend 拉取家庭成员
        setState(() {
          _initialType = sessionType;
          _isSymptomLocked = true;
        });
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
        // [2026-04-25 Bug-04] 历史会话恢复：报告解读/对比也需锁定咨询人按钮
        if (sessionType == 'report_interpret' || sessionType == 'report_compare') {
          final relation = (data['family_member_relation'] as String?) ?? '';
          setState(() {
            _initialType = sessionType;
            _isSymptomLocked = true;
            if (relation.isNotEmpty) {
              _currentConsultTarget = relation;
            }
          });
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

  // [2026-04-23 报告分支] 拉取体检报告 brief 列表；auto_start 暂不触发首条消息，保持与文档一致
  Future<void> _loadReportBriefsAndMaybeAutoStart() async {
    try {
      final List<Map<String, dynamic>> reports = [];

      if (_reportIdForLoad != null) {
        try {
          final resp = await _apiService.dio.get('/api/checkup/reports/${_reportIdForLoad}');
          if (resp.statusCode == 200 && resp.data is Map) {
            reports.add(Map<String, dynamic>.from(resp.data as Map));
          }
        } catch (e) {
          debugPrint('[report brief] single load failed: $e');
        }
      } else if (_reportIdsForLoad.isNotEmpty) {
        for (final rid in _reportIdsForLoad) {
          try {
            final resp = await _apiService.dio.get('/api/checkup/reports/$rid');
            if (resp.statusCode == 200 && resp.data is Map) {
              reports.add(Map<String, dynamic>.from(resp.data as Map));
            }
          } catch (e) {
            debugPrint('[report brief] item $rid load failed: $e');
          }
        }
      }

      final normalized = reports.map((r) {
        List<String> urls;
        if (r['file_urls'] is List && (r['file_urls'] as List).isNotEmpty) {
          urls = (r['file_urls'] as List)
              .map((e) => e?.toString() ?? '')
              .where((e) => e.isNotEmpty)
              .toList();
        } else if (r['file_url'] is String && (r['file_url'] as String).isNotEmpty) {
          urls = [r['file_url'].toString()];
        } else {
          urls = const [];
        }

        List<String> thumbs;
        if (r['thumbnail_urls'] is List && (r['thumbnail_urls'] as List).isNotEmpty) {
          thumbs = (r['thumbnail_urls'] as List)
              .map((e) => e?.toString() ?? '')
              .where((e) => e.isNotEmpty)
              .toList();
        } else {
          thumbs = List<String>.from(urls);
        }

        return <String, dynamic>{
          'id': r['id'],
          'title': r['title'] ?? r['report_date'] ?? '体检报告',
          'file_urls': urls,
          'thumbnail_urls': thumbs,
        };
      }).toList();

      if (mounted) setState(() => _reportCards = normalized);

      // [2026-04-25] 报告解读异步订阅：进入页面即订阅后端 worker 推流，不再本地插入用户气泡
      if (_autoStart) {
        final chatProvider = Provider.of<ChatProvider>(context, listen: false);
        final session = chatProvider.currentSession;
        if (session != null) {
          _subscribeReportInterpret(session.id);
        }
      }
    } catch (e) {
      debugPrint('[report brief] load failed: $e');
    }
  }

  // [2026-04-25] 报告解读异步 SSE 订阅
  StreamSubscription? _interpretSseSub;
  bool _interpretFailed = false;

  void _subscribeReportInterpret(String sessionId) {
    if (_interpretSseSub != null) return;
    setState(() { _isStreaming = true; _streamingContent = ''; _interpretFailed = false; });
    _startCursorBlink();

    _interpretSseSub = _sseService
        .subscribeReportInterpret(sessionId)
        .listen(
      (sseMsg) {
        if (!mounted) return;
        try {
          Map<String, dynamic> data = {};
          if (sseMsg.data.isNotEmpty) {
            try { data = jsonDecode(sseMsg.data) as Map<String, dynamic>; } catch (_) { data = {'raw': sseMsg.data}; }
          }
          final ev = sseMsg.event;

          if (ev == 'message.delta' || data['type'] == 'delta') {
            final delta = (data['delta'] ?? data['content'] ?? '').toString();
            if (delta.isNotEmpty) {
              setState(() => _streamingContent += delta);
              _scrollToBottom();
            }
          } else if (ev == 'message.done' || data['type'] == 'done') {
            final content = (data['content'] ?? _streamingContent).toString();
            _finishInterpretStream(sessionId, content);
          } else if (ev == 'status') {
            if (data['interpret_status'] == 'failed') {
              setState(() => _interpretFailed = true);
              _finishInterpretStream(sessionId, _streamingContent);
            }
          } else if (ev == 'error' || data['type'] == 'error') {
            setState(() => _interpretFailed = true);
            _finishInterpretStream(sessionId, _streamingContent);
          } else if (ev == 'done') {
            if (_isStreaming) {
              _finishInterpretStream(sessionId, _streamingContent);
            }
          }
        } catch (e) {
          debugPrint('[report SSE] parse error: $e');
        }
      },
      onDone: () {
        if (_isStreaming) _finishInterpretStream(sessionId, _streamingContent);
      },
      onError: (e) {
        debugPrint('[report SSE] error: $e');
        setState(() => _interpretFailed = true);
        if (_isStreaming) _finishInterpretStream(sessionId, _streamingContent);
      },
    );
  }

  void _finishInterpretStream(String sessionId, String content) {
    _interpretSseSub?.cancel();
    _interpretSseSub = null;
    _stopCursorBlink();
    if (content.isNotEmpty) {
      final chatProvider = Provider.of<ChatProvider>(context, listen: false);
      chatProvider.addMessageExternally(ChatMessage(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        sessionId: sessionId,
        role: 'assistant',
        content: content,
        createdAt: DateTime.now().toIso8601String(),
      ));
    }
    setState(() { _isStreaming = false; _streamingContent = ''; });
    _scrollToBottom();
  }

  Future<void> _retryReportInterpret() async {
    final chatProvider = Provider.of<ChatProvider>(context, listen: false);
    final session = chatProvider.currentSession;
    if (session == null) return;
    try {
      await _apiService.dio.post('/api/report/interpret/session/${session.id}/retry');
      setState(() { _interpretFailed = false; });
      _subscribeReportInterpret(session.id);
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('重试失败：$e')),
      );
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
          final parsed = items
              .map((e) => FunctionButton.fromJson(Map<String, dynamic>.from(e as Map)))
              .toList();
          // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 过滤：is_recommended OR is_capsule 任一为 true 即可见；
          // 兜底：若所有按钮新字段都不存在（老接口），退化为按 isEnabled 过滤
          final hasNewFields = parsed.any((b) => b.isRecommended || b.isCapsule);
          _functionButtons = parsed
              .where((b) => hasNewFields ? (b.isRecommended || b.isCapsule) : b.isEnabled)
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
      // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
      // 报告解读按钮：上传图片到服务器拿 URL → 在当前会话内 SSE 触发
      // intent='report_interpret'，由后端 ReportInterpretEngine 处理；
      // 不再走"image 路径作为消息"导致后端拿不到真实图片的旧逻辑。
      case 'report_interpret':
        _handleReportInterpretButton(btn);
        break;
      case 'ai_dialog_trigger':
        final triggerMsg = btn.params?['trigger_message']?.toString() ?? btn.name;
        _sendMessageWithSSE(triggerMsg);
        break;
      case 'drug_identify':
      // [PRD-AICHAT-CAPSULE-V2 2026-05-15] photo_recognize_drug 是新枚举值，复用识药交互
      case 'photo_recognize_drug':
        _handleDrugIdentifyButton(btn);
        break;
      case 'external_link':
        final url = btn.params?['url']?.toString();
        if (url != null && url.isNotEmpty) {
          launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
        }
        break;
      // [PRD-AICHAT-CAPSULE-V2 2026-05-15 需求 4.1] quick_ask 胶囊：以"用户身份"发出 preset_prompt
      case 'quick_ask':
      case 'prompt_template':
        final preset = (btn.presetPrompt ??
                btn.autoUserMessage ??
                btn.params?['preset_prompt']?.toString() ??
                btn.params?['trigger_message']?.toString() ??
                btn.name)
            .trim();
        if (preset.isNotEmpty) {
          _sendMessageWithSSE(preset);
        }
        break;
      // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查：唤起抽屉
      case 'health_self_check':
        _openHealthSelfCheckDrawer(btn);
        break;
    }
  }

  Future<void> _openHealthSelfCheckDrawer(FunctionButton btn,
      {HealthSelfCheckResult? prefill}) async {
    if (btn.healthCheckTemplateId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('该功能暂不可用，请联系管理员')),
      );
      return;
    }
    final result = await showModalBottomSheet<HealthSelfCheckResult>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => HealthSelfCheckDrawer(
        templateId: btn.healthCheckTemplateId!,
        buttonId: btn.id,
        archiveName: '本人',
        archiveIsDefault: true,
        prefill: prefill,
      ),
    );
    if (result == null) return;
    await _submitHealthSelfCheck(result);
  }

  Future<void> _submitHealthSelfCheck(HealthSelfCheckResult result) async {
    final provider = Provider.of<ChatProvider>(context, listen: false);
    var session = provider.currentSession;
    // 若无会话，先创建一个
    if (session == null) {
      await provider.createSession('symptom_check');
      session = provider.currentSession;
    }
    final sessionId = session?.id ?? '';
    // [PRD-HEALTH-SELF-CHECK-V2 2026-05-16] 卡片气泡 payload 增加 symptom_description
    final cardMsg = ChatMessage(
      id: 'hsc-${DateTime.now().millisecondsSinceEpoch}',
      sessionId: sessionId,
      role: 'user',
      content: '',
      type: 'health_self_check_card',
      createdAt: DateTime.now().toIso8601String(),
      healthSelfCheckPayload: {
        'archive_id': result.archiveId,
        'archive_name': result.archiveName,
        'archive_age': result.archiveAge,
        'archive_gender': result.archiveGender,
        'body_part': result.bodyPart,
        'symptoms': result.symptoms,
        'duration': result.duration,
        'symptom_description': result.symptomDescription ?? '',
        'template_id': result.templateId,
        'button_id': result.buttonId,
      },
    );
    provider.addMessageExternally(cardMsg);
    final aiPlaceholderId = 'a-hsc-${DateTime.now().millisecondsSinceEpoch}';
    final placeholder = ChatMessage(
      id: aiPlaceholderId,
      sessionId: sessionId,
      role: 'assistant',
      content: '正在分析中…',
      isLoading: true,
    );
    provider.addMessageExternally(placeholder);
    try {
      // [BUG-FIX 2026-05-16] 后端 schema 要求 body_part_id（整数），
      // 不接受 body_part 对象 / archive_name / archive_age / archive_gender。
      // 展示模型（卡片气泡 healthSelfCheckPayload）保留完整 body_part 对象，
      // 但发给后端的 payload 只传 body_part_id。
      final dynamic rawPartId = result.bodyPart['id'];
      final int bodyPartId = rawPartId is int
          ? rawPartId
          : int.tryParse(rawPartId?.toString() ?? '') ?? 0;
      final requestBody = <String, dynamic>{
        'template_id': result.templateId,
        'button_id': result.buttonId,
        'archive_id': result.archiveId,
        'body_part_id': bodyPartId,
        'symptoms': result.symptoms,
        'duration': result.duration,
        // [PRD-HEALTH-SELF-CHECK-V2 2026-05-16] 用户补充的症状描述（≤50 字，可为空）
        'symptom_description': result.symptomDescription ?? '',
      };

      // [PRD-HEALTH-SELF-CHECK-V2 2026-05-16] 改造为 SSE 流式接口 /start-stream
      // 协议（每个 event 块以 \n\n 结尾）：
      //   event: meta\ndata: {"session_id":..., "user_message_id":..., "card_payload":{...}}
      //   event: delta\ndata: {"content":"增量文本"}    （多条）
      //   event: done\ndata: {"message_id":..., "full_content":"完整文本"}
      final response = await _apiService.dio.post(
        '/api/health-self-check/start-stream',
        data: requestBody,
        options: Options(
          responseType: ResponseType.stream,
          headers: {'Accept': 'text/event-stream'},
        ),
      );
      final stream = response.data.stream as Stream<List<int>>;
      String buffer = '';
      String aiAccum = '';
      bool gotDone = false;

      await for (final chunk in stream) {
        buffer += utf8.decode(chunk, allowMalformed: true);
        // 按 \n\n 拆 event 块
        while (true) {
          final idx = buffer.indexOf('\n\n');
          if (idx < 0) break;
          final block = buffer.substring(0, idx);
          buffer = buffer.substring(idx + 2);
          String evt = 'message';
          String data = '';
          for (final raw in block.split('\n')) {
            final line = raw.trimRight();
            if (line.startsWith('event:')) {
              evt = line.substring(6).trim();
            } else if (line.startsWith('data:')) {
              final piece = line.substring(5).trim();
              data = data.isEmpty ? piece : '$data\n$piece';
            }
          }
          if (data.isEmpty) continue;
          Map<String, dynamic> payload;
          try {
            payload = json.decode(data) as Map<String, dynamic>;
          } catch (_) {
            continue;
          }
          if (evt == 'meta') {
            // 当前实现暂不需要更新 session/user_message_id 至 UI；保留扩展点
          } else if (evt == 'delta') {
            final piece = payload['content']?.toString() ?? '';
            if (piece.isEmpty) continue;
            aiAccum += piece;
            provider.replaceMessageById(
              aiPlaceholderId,
              ChatMessage(
                id: aiPlaceholderId,
                sessionId: sessionId,
                role: 'assistant',
                content: aiAccum,
                isLoading: true,
              ),
            );
          } else if (evt == 'done') {
            gotDone = true;
            final full = payload['full_content']?.toString();
            final finalText = (full != null && full.isNotEmpty) ? full : aiAccum;
            provider.replaceMessageById(
              aiPlaceholderId,
              ChatMessage(
                id: aiPlaceholderId,
                sessionId: sessionId,
                role: 'assistant',
                content: finalText.isEmpty ? '分析失败，请稍候重试' : finalText,
              ),
            );
          }
        }
      }

      if (!gotDone) {
        // 流意外结束：用已累积内容定型，若无累积则提示失败
        provider.replaceMessageById(
          aiPlaceholderId,
          ChatMessage(
            id: aiPlaceholderId,
            sessionId: sessionId,
            role: 'assistant',
            content: aiAccum.isEmpty ? '分析失败，请稍候重试' : aiAccum,
          ),
        );
      }
    } catch (_) {
      provider.replaceMessageById(
        aiPlaceholderId,
        ChatMessage(
          id: aiPlaceholderId,
          sessionId: sessionId,
          role: 'assistant',
          content: '分析失败，请稍候重试',
        ),
      );
    }
  }

  void _reopenHealthSelfCheck(Map<String, dynamic> payload) {
    final btnId = payload['button_id'];
    FunctionButton? btn;
    for (final b in _functionButtons) {
      if (b.id == btnId) {
        btn = b;
        break;
      }
    }
    if (btn == null) return;
    final bp = payload['body_part'] is Map
        ? Map<String, dynamic>.from(payload['body_part'] as Map)
        : <String, dynamic>{};
    final symptoms = (payload['symptoms'] as List?)?.map((e) => e.toString()).toList() ?? [];
    _openHealthSelfCheckDrawer(
      btn,
      prefill: HealthSelfCheckResult(
        templateId: payload['template_id'] as int? ?? 0,
        buttonId: btn.id,
        bodyPart: bp,
        symptoms: symptoms,
        duration: payload['duration']?.toString() ?? '',
        // [PRD-HEALTH-SELF-CHECK-V2 2026-05-16] 重新自查时回填症状描述
        symptomDescription: payload['symptom_description']?.toString(),
      ),
    );
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

  // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
  // 报告解读按钮入口：拍照/相册 → 上传到服务器拿 URL → 同会话 SSE intent
  Future<void> _handleReportInterpretButton(FunctionButton btn) async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
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
    if (image == null) return;

    if (mounted) {
      setState(() {
        _isStreaming = true;
        _streamingContent = '正在上传图片…';
      });
      _startCursorBlink();
    }

    String? imageUrl;
    try {
      final formData = FormData.fromMap({
        'file': await MultipartFile.fromFile(image.path),
      });
      final resp = await _apiService.dio.post('/api/upload/image', data: formData);
      if (resp.data is Map) {
        final m = resp.data as Map;
        imageUrl = (m['url'] ?? m['image_url'])?.toString();
      }
    } catch (_) {}

    if (imageUrl == null || imageUrl.isEmpty) {
      if (mounted) {
        setState(() {
          _isStreaming = false;
          _streamingContent = '';
        });
        _stopCursorBlink();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('图片上传失败，请重试')),
        );
      }
      return;
    }

    if (mounted) {
      setState(() {
        _isStreaming = false;
        _streamingContent = '';
      });
      _stopCursorBlink();
    }

    // 用户气泡：展示已上传图片 URL
    final chatProvider = Provider.of<ChatProvider>(context, listen: false);
    final sessionId = chatProvider.currentSession?.id;
    if (sessionId == null) return;
    chatProvider.addMessageExternally(ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      sessionId: sessionId,
      role: 'user',
      content: imageUrl,
      type: 'image',
      createdAt: DateTime.now().toIso8601String(),
    ));

    int? btnIdInt;
    try {
      btnIdInt = int.tryParse(btn.id?.toString() ?? '');
    } catch (_) {}

    _sendMessageWithSSE(
      '我上传了一份体检报告，请帮我解读',
      intent: 'report_interpret',
      imageUrls: [imageUrl],
      buttonType: 'report_interpret',
      buttonId: btnIdInt,
    );
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
  // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
  // 新增可选 extras：用于报告解读 / 显式识药等场景，把 intent + image_urls + button_type
  // 透传给后端通用 SSE 分发器（与 H5、小程序协议保持一致）。
  void _sendMessageWithSSE(
    String content, {
    String type = 'text',
    String? intent,
    List<String>? imageUrls,
    String? buttonType,
    int? buttonId,
    Map<String, dynamic>? reportMeta,
  }) {
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

    _sseSubscription = _sseService.streamChat(
      sessionId,
      content,
      type: type,
      intent: intent,
      imageUrls: imageUrls,
      buttonType: buttonType,
      buttonId: buttonId,
      reportMeta: reportMeta,
    ).listen(
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
  // [PRD-440] 移动端复制反馈：调用系统原生轻提示（使用浮层 SnackBar 模拟系统 Toast 风格）
  void _copyMessage(String content) {
    final cleanText = content.split('---disclaimer---').first.trim();
    Clipboard.setData(ClipboardData(text: cleanText));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('已复制', textAlign: TextAlign.center),
        duration: const Duration(milliseconds: 1500),
        backgroundColor: Colors.black.withOpacity(0.85),
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.fromLTRB(80, 0, 80, 200),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
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
    _interpretSseSub?.cancel();
    _cursorTimer?.cancel();
    _v4UndoTimer?.cancel();
    _ttsService.stop();
    super.dispose();
  }

  // [PRD-AI-HOME-OPTIM-V4 M2 · 2026-05-21] 切换咨询人三重提示
  // 1. 中央 Toast（SnackBar 居上 floating）2 秒
  // 2. 系统消息文案（_v4SwitchSystemMsgText）插入到消息流上方常驻
  // 3. 5 秒撤销横条（_v4UndoBarVisible）+ 「返回上一会话」按钮
  void _v4ShowSwitchTripleHints(String prevTarget, String newTarget) {
    // F-切人-01：中央 Toast（顶部 floating，2 秒）
    try {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('已切换为 $newTarget 咨询', textAlign: TextAlign.center),
          duration: const Duration(seconds: 2),
          behavior: SnackBarBehavior.floating,
          backgroundColor: const Color(0xCC2E2E2E),
          margin: const EdgeInsets.fromLTRB(40, 20, 40, 0),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        ),
      );
    } catch (_) {}
    // F-切人-02：系统消息（永久留痕——本会话期间常驻显示）
    setState(() {
      _v4SwitchSystemMsgText = '—— 现在开始为 $newTarget 提供健康咨询 ——';
      // F-切人-03：5 秒撤销横条
      _v4UndoBarVisible = true;
      _v4UndoBarText = '已切换为 $newTarget 咨询，已为您开启新对话';
      _v4PrevTargetForUndo = prevTarget;
    });
    _v4UndoTimer?.cancel();
    _v4UndoTimer = Timer(const Duration(seconds: 5), () {
      if (!mounted) return;
      setState(() {
        _v4UndoBarVisible = false;
        _v4PrevTargetForUndo = null;
      });
      _v4ReportTrack('switch_undo_expired', {});
    });
    _v4ReportTrack('switch_consultant', {
      'from_name': prevTarget,
      'to_name': newTarget,
    });
  }

  void _v4UndoSwitch() {
    if (_v4PrevTargetForUndo == null) return;
    final prev = _v4PrevTargetForUndo!;
    setState(() {
      _currentConsultTarget = prev;
      _v4UndoBarVisible = false;
      _v4SwitchSystemMsgText = null;
      _v4PrevTargetForUndo = null;
    });
    _v4UndoTimer?.cancel();
    _v4ReportTrack('switch_undo_clicked', {});
  }

  void _v4ReportTrack(String event, Map<String, dynamic> payload) {
    try {
      _apiService.dio.post('/api/ai-home/track', data: {
        'event': event,
        'platform': 'flutter',
        'payload': payload,
      }).catchError((_) => null);
    } catch (_) {}
  }

  // [PRD-AI-HOME-OPTIM-V4 M2] 5 秒撤销横条 widget（在 build 顶部叠加显示）
  Widget _v4BuildUndoBar() {
    if (!_v4UndoBarVisible) return const SizedBox.shrink();
    return Container(
      width: double.infinity,
      height: 36,
      color: const Color(0xFFEAF4FF),
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Row(
        children: [
          Expanded(
            child: Text(
              _v4UndoBarText,
              style: const TextStyle(fontSize: 13, color: Color(0xFF2E2E2E)),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: _v4UndoSwitch,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
              decoration: BoxDecoration(
                border: Border.all(color: const Color(0xFF1677FF)),
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Text('返回上一会话',
                  style: TextStyle(fontSize: 12, color: Color(0xFF1677FF))),
            ),
          ),
        ],
      ),
    );
  }

  // [PRD-AI-HOME-OPTIM-V4 M2 · F-切人-02] 系统消息常驻气泡（居中、灰色）
  Widget _v4BuildSystemMsgBanner() {
    if (_v4SwitchSystemMsgText == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
      child: Center(
        child: Text(
          _v4SwitchSystemMsgText!,
          style: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF)),
        ),
      ),
    );
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

    // [PRD-AIHOME-INPUT-HINT-OPTIM 2026-06-02 事件2-④] 按下瞬间轻微震动反馈
    try { HapticFeedback.lightImpact(); } catch (_) {}

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

  // [2026-04-23 报告分支] 顶部报告卡片入口：解读单报告 / 对比两份报告
  Widget _buildReportTopCard() {
    if (_reportCards.isEmpty) return const SizedBox.shrink();
    if (_initialType == 'report_compare' && _reportCards.length >= 2) {
      return _buildCompareCard(_reportCards[0], _reportCards[1]);
    }
    return _buildInterpretCard(_reportCards.first);
  }

  // [2026-04-23 报告分支] 单报告解读卡片：九宫格缩略图 + 点击全屏 PageView 预览
  Widget _buildInterpretCard(Map<String, dynamic> r) {
    final urls = List<String>.from((r['file_urls'] as List?) ?? const []);
    final thumbs = List<String>.from((r['thumbnail_urls'] as List?) ?? urls);
    final title = r['title']?.toString() ?? '体检报告';
    final previewThumbs = thumbs.take(4).toList();

    return Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [Color(0xFFE6F7FF), Colors.white]),
        border: Border.all(color: const Color(0xFF91D5FF)),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '🩺 报告解读：$title',
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
          ),
          if (urls.length > 1)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                '共 ${urls.length} 张',
                style: const TextStyle(fontSize: 12, color: Color(0xFF1890FF)),
              ),
            ),
          if (previewThumbs.isNotEmpty) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (int i = 0; i < previewThumbs.length; i++)
                  GestureDetector(
                    onTap: () => _openReportGallery(urls, i),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(6),
                      child: Image.network(
                        previewThumbs[i],
                        width: 60,
                        height: 60,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => Container(
                          width: 60,
                          height: 60,
                          color: Colors.grey[200],
                          child: const Icon(Icons.broken_image, color: Colors.grey, size: 24),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  // [2026-04-23 报告分支] 报告对比卡片：A / B 两行，点击按钮进入全屏画廊
  Widget _buildCompareCard(Map<String, dynamic> a, Map<String, dynamic> b) {
    return Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [Color(0xFFFFFBE6), Colors.white]),
        border: Border.all(color: const Color(0xFFFFE58F)),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('🔄 报告对比', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          _buildCompareRow('报告 A', a),
          _buildCompareRow('报告 B', b),
        ],
      ),
    );
  }

  Widget _buildCompareRow(String label, Map<String, dynamic> r) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          Text('$label：', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500)),
          Expanded(
            child: Text(
              r['title']?.toString() ?? '-',
              style: const TextStyle(fontSize: 12, color: Color(0xFF1890FF)),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  // [2026-04-23 报告分支] 复用 PageView + InteractiveViewer 的全屏预览
  void _openReportGallery(List<String> images, int initialIndex) {
    if (images.isEmpty) return;
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => _ChatReportGallery(images: images, initialIndex: initialIndex),
    ));
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
          // [2026-04-23 报告分支]
          _buildReportTopCard(),
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
          // [PRD-AI-HOME-OPTIM-V4 M2 · F-切人-03] 5 秒撤销横条
          _v4BuildUndoBar(),
          Expanded(
            child: Consumer<ChatProvider>(
              builder: (context, chatProvider, child) {
                final messages = chatProvider.messages;
                if (messages.isEmpty && !_isStreaming) {
                  return Column(
                    children: [
                      _v4BuildSystemMsgBanner(),
                      Expanded(child: _buildWelcome()),
                    ],
                  );
                }

                final extra = (_isStreaming ? 1 : 0) + (_interpretFailed ? 1 : 0);
                // [PRD-AI-HOME-OPTIM-V4 M2 · F-切人-02] 系统切换通知作为列表第一项常驻
                final hasSystemBanner = _v4SwitchSystemMsgText != null;
                final headerOffset = hasSystemBanner ? 1 : 0;
                final itemCount = messages.length + extra + headerOffset;
                return ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  itemCount: itemCount,
                  itemBuilder: (context, index) {
                    if (hasSystemBanner && index == 0) {
                      return _v4BuildSystemMsgBanner();
                    }
                    final realIndex = index - headerOffset;
                    if (realIndex == messages.length && _isStreaming) {
                      return _buildStreamingBubble();
                    }
                    if (realIndex == messages.length + (_isStreaming ? 1 : 0) && _interpretFailed) {
                      return _buildInterpretFailedBar();
                    }
                    final message = messages[realIndex];
                    final isLastAi = !message.isUser && _findLastAiIndex(messages) == realIndex;
                    final isReportSession = _initialType == 'report_interpret' || _initialType == 'report_compare';
                    final isFirstAi = isReportSession && !message.isUser && _findFirstAiIndex(messages) == realIndex;
                    // [PRD-433 F-09] 与上一条消息间隔 > 5 分钟时插入时间分隔条
                    final divider = _buildTimeDividerIfNeeded(messages, realIndex);
                    final bubble = _buildMessageBubble(
                      message,
                      showActions: isLastAi && !_isStreaming,
                      showOcrDetailEntry: isFirstAi && !_isStreaming && !_interpretFailed,
                    );
                    if (divider == null) return bubble;
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [divider, bubble],
                    );
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

  // [2026-04-25 PRD F5] 找到第一条 AI 消息的索引，用于在底部挂载 OCR 详情入口
  int _findFirstAiIndex(List<ChatMessage> messages) {
    for (int i = 0; i < messages.length; i++) {
      if (messages[i].isAssistant && !messages[i].isLoading) return i;
    }
    return -1;
  }

  // [2026-04-25 PRD F5-3] 切换 OCR 详情展开/收起；首次展开时按需拉取
  Future<void> _toggleOcrDetail() async {
    final session = Provider.of<ChatProvider>(context, listen: false).currentSession;
    final sid = session?.id;
    if (sid == null) return;
    final next = !_ocrDetailExpanded;
    setState(() { _ocrDetailExpanded = next; });
    // F5-7 埋点（不阻塞）
    try {
      _apiService.post('/api/report/interpret/ocr-detail/click', data: {
        'session_id': sid,
        'action': next ? 'view' : 'collapse',
      });
    } catch (_) { /* ignore */ }
    if (!next) return;
    if (_ocrDetailLoaded || _ocrDetailLoading) return;
    setState(() { _ocrDetailLoading = true; });
    try {
      final r = await _apiService.get('/api/report/interpret/session/$sid/ocr-detail');
      final data = r.data is Map ? r.data : {};
      setState(() {
        _ocrDetailText = (data['ocr_text'] ?? '').toString();
        _ocrDetailLoaded = true;
      });
    } catch (_) {
      setState(() { _ocrDetailText = ''; });
    } finally {
      if (mounted) setState(() { _ocrDetailLoading = false; });
    }
  }

  Widget _buildOcrDetailEntry() {
    final fontSize = _chatFontSize - 4 < 10 ? 10.0 : _chatFontSize - 4;
    return Padding(
      padding: const EdgeInsets.only(left: 46, right: 16, top: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Align(
            alignment: Alignment.centerRight,
            child: GestureDetector(
              onTap: _ocrDetailLoading ? null : _toggleOcrDetail,
              child: Text(
                _ocrDetailLoading
                    ? '加载中…'
                    : (_ocrDetailExpanded ? '收起 OCR 识别详情 ▴' : '查看 OCR 识别详情 ▾'),
                style: TextStyle(color: const Color(0xFF999999), fontSize: fontSize),
              ),
            ),
          ),
          if (_ocrDetailExpanded)
            Container(
              margin: const EdgeInsets.only(top: 6),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              constraints: const BoxConstraints(maxHeight: 320),
              decoration: BoxDecoration(
                color: const Color(0xFFFAFAFA),
                border: Border.all(color: const Color(0xFFF0F0F0)),
                borderRadius: BorderRadius.circular(8),
              ),
              child: SingleChildScrollView(
                child: Text(
                  _ocrDetailText.isNotEmpty
                      ? _ocrDetailText
                      : (_ocrDetailLoaded ? '（暂无 OCR 文本）' : '加载中…'),
                  style: TextStyle(
                    color: const Color(0xFF666666),
                    fontSize: fontSize + 1,
                    height: 1.7,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  // [2026-04-25] 报告解读失败时展示"重新解读"
  Widget _buildInterpretFailedBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFFFFF1F0),
          border: Border.all(color: const Color(0xFFFFCCC7)),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            const Text('抱歉，本次解读未能完成。', style: TextStyle(color: Color(0xFFCF1322), fontSize: 14)),
            const SizedBox(height: 10),
            ElevatedButton(
              onPressed: _retryReportInterpret,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFFF4D4F),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              ),
              child: const Text('重新解读'),
            ),
          ],
        ),
      ),
    );
  }

  // [PRD-433 F-02/F-10/F-11] 流式输出：使用 AI 卡片样式；空内容时显示 Loading 卡片；不显示光标
  Widget _buildStreamingBubble() {
    if (_streamingContent.isEmpty) {
      return _buildLoadingCard();
    }
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAiSenderRow(),
          const SizedBox(height: 8),
          _buildAiCardContainer(
            child: Text(
              _streamingContent,
              style: TextStyle(
                fontSize: _chatFontSize,
                height: 1.6,
                color: const Color(0xFF1A1A1A),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // [PRD-433 F-11] Loading 卡片：白底 + 描边 + 88% 占屏，含「小康正在思考中…」+ 三点跳动
  Widget _buildLoadingCard() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAiSenderRow(),
          const SizedBox(height: 8),
          _buildAiCardContainer(
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: const [
                Text(
                  '小康正在思考中',
                  style: TextStyle(fontSize: 16, color: _ChatTokens.loadingText),
                ),
                SizedBox(width: 4),
                _AnimatedDots(color: _ChatTokens.loadingText, fontSize: 16),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // [PRD-433 F-03] AI 头像 + 名称行（卡片外部上方）
  Widget _buildAiSenderRow() {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 28,
          height: 28,
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            gradient: LinearGradient(
              colors: [Color(0xFF52C41A), Color(0xFF13C2C2)],
            ),
          ),
          alignment: Alignment.center,
          child: const Text('🌿', style: TextStyle(fontSize: 14)),
        ),
        const SizedBox(width: 8),
        const Text(
          '小康',
          style: TextStyle(fontSize: 14, color: _ChatTokens.senderName),
        ),
      ],
    );
  }

  // [PRD-433 F-02] AI 白色卡片容器：白底 + 1px 描边 + 12 圆角 + 88% 屏宽
  Widget _buildAiCardContainer({required Widget child}) {
    final screenWidth = MediaQuery.of(context).size.width;
    return Container(
      width: screenWidth * _ChatTokens.aiCardWidthRatio,
      decoration: BoxDecoration(
        color: _ChatTokens.aiCardBg,
        border: Border.all(color: _ChatTokens.aiCardBorder, width: 1),
        borderRadius: BorderRadius.circular(_ChatTokens.aiCardRadius),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: child,
    );
  }

  // [PRD-433 F-09] 时间分隔条：与上一条消息间隔 > 5 分钟才插入
  Widget? _buildTimeDividerIfNeeded(List<ChatMessage> messages, int index) {
    final cur = _parseMessageTime(messages[index].createdAt);
    if (cur == null) return null;
    if (index == 0) return _timeDividerWidget(cur);
    final prev = _parseMessageTime(messages[index - 1].createdAt);
    if (prev == null) return _timeDividerWidget(cur);
    if (cur.difference(prev).abs() <= _ChatTokens.timeDividerThreshold) return null;
    return _timeDividerWidget(cur);
  }

  DateTime? _parseMessageTime(String? iso) {
    if (iso == null || iso.isEmpty) return null;
    return parseServerTime(iso);
  }

  Widget _timeDividerWidget(DateTime t) {
    final now = DateTime.now();
    final isSameDay = t.year == now.year && t.month == now.month && t.day == now.day;
    final hh = t.hour.toString().padLeft(2, '0');
    final mm = t.minute.toString().padLeft(2, '0');
    final label = isSameDay
        ? '$hh:$mm'
        : '${t.year}/${t.month.toString().padLeft(2, '0')}/${t.day.toString().padLeft(2, '0')} $hh:$mm';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Center(
        child: Text(
          label,
          style: const TextStyle(fontSize: 12, color: _ChatTokens.timeDividerText),
        ),
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

  // [PRD-433 v1.0] 气泡卡片化：用户右侧浅蓝气泡 + AI 白色卡片
  Widget _buildMessageBubble(ChatMessage message, {bool showActions = false, bool showOcrDetailEntry = false}) {
    if (message.isLoading) return _buildLoadingCard();
    // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] AI 侧问卷结果卡片（修复 Bug-3）
    if (!message.isUser &&
        message.type == 'questionnaire_result_card' &&
        message.questionnaireResultPayload != null) {
      return _buildAiSideQuestionnaireResultCard(message);
    }
    // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] AI 侧追问 chips 行（修复 Bug-1）
    if (!message.isUser &&
        message.type == 'followup_chips' &&
        message.followupChips != null) {
      return _buildAiSideFollowupChipsRow(message);
    }
    if (message.isUser) return _buildUserBubble(message);
    return _buildAiCard(message, showActions: showActions, showOcrDetailEntry: showOcrDetailEntry);
  }

  // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] AI 侧渲染：问卷结果卡片
  Widget _buildAiSideQuestionnaireResultCard(ChatMessage message) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 6, 16, 6),
      child: Align(
        alignment: Alignment.centerLeft,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 380),
          child: QuestionnaireResultCard(
            payload: message.questionnaireResultPayload!,
            onTapDetail: () {
              final payload = message.questionnaireResultPayload!;
              final code = (payload['questionnaire_code'] ?? '').toString();
              final resultId = payload['result_id'] ?? payload['answer_id'] ?? message.questionnaireAnswerId;
              if (code == 'tcm_constitution' && resultId is int) {
                Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => ConstitutionResultScreen(diagnosisId: resultId),
                ));
              } else if (resultId is int) {
                Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => ConstitutionResultScreen(diagnosisId: resultId),
                ));
              }
            },
          ),
        ),
      ),
    );
  }

  // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] AI 侧渲染：追问 chips 行
  Widget _buildAiSideFollowupChipsRow(ChatMessage message) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 6, 16, 6),
      child: Align(
        alignment: Alignment.centerLeft,
        child: FollowupChipsRow(
          chips: message.followupChips!,
          disabled: message.followupChipsDisabled,
          onTapChip: (chip) async {
            // 立即置灰
            final chatProvider = context.read<ChatProvider>();
            chatProvider.replaceMessageById(
              message.id,
              message.copyWith(followupChipsDisabled: true),
            );
            try {
              final api = ApiService();
              final r = await api.dio.post(
                '/api/questionnaire/followup-chip',
                data: {
                  'answer_id': message.questionnaireAnswerId,
                  'chip_code': chip['code'],
                  'chip_label': chip['label'],
                },
              );
              final data = r.data is Map ? r.data as Map : <String, dynamic>{};
              final aiText = (data['ai_text'] ?? '本次回答结合您的档案。${chip['label']} 暂无更详细资料。').toString();
              chatProvider.addMessageExternally(ChatMessage(
                id: 'chip-reply-${DateTime.now().millisecondsSinceEpoch}',
                sessionId: message.sessionId,
                role: 'assistant',
                content: aiText,
                type: 'text',
                createdAt: DateTime.now().toIso8601String(),
              ));
            } catch (e) {
              // ignore
            }
          },
        ),
      ),
    );
  }

  // [PRD-433 F-01/F-04] 用户消息：右侧浅蓝气泡，无头像
  Widget _buildUserBubble(ChatMessage message) {
    final screenWidth = MediaQuery.of(context).size.width;
    final maxW = (screenWidth * _ChatTokens.userBubbleMaxWidthRatio)
        .clamp(0.0, _ChatTokens.userBubbleMaxWidth);
    // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查卡片气泡
    if (message.type == 'health_self_check_card' &&
        message.healthSelfCheckPayload != null) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 6, 16, 6),
        child: Align(
          alignment: Alignment.centerRight,
          child: HealthSelfCheckCard(
            payload: message.healthSelfCheckPayload!,
            onReopen: () => _reopenHealthSelfCheck(message.healthSelfCheckPayload!),
          ),
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 6, 16, 6),
      child: Align(
        alignment: Alignment.centerRight,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxW),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: _ChatTokens.userBubbleBg,
              borderRadius: BorderRadius.circular(_ChatTokens.userBubbleRadius),
            ),
            child: Text(
              message.content,
              style: TextStyle(
                color: _ChatTokens.userBubbleText,
                fontSize: _chatFontSize,
                height: 1.6,
              ),
            ),
          ),
        ),
      ),
    );
  }

  // [PRD-433 F-02/F-03/F-06/F-08] AI 消息卡片
  Widget _buildAiCard(ChatMessage message, {required bool showActions, required bool showOcrDetailEntry}) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // [PRD-432] AI 回答顶部「咨询对象档案」折叠卡片（保留）
          AiProfileCard(
            consultantId: _initialFamilyMemberId ?? 0,
            onGoCompleteProfile: () {
              Navigator.pushNamed(context, '/health-profile');
            },
            onGoMedicationManage: (cid, autoCreate) {
              Navigator.of(context).pushNamed('/health-plan/medications', arguments: {
                'target': cid,
                if (autoCreate) 'action': 'create',
              });
            },
          ),
          const SizedBox(height: 8),
          // 头像 + 名称（卡片外部上方）
          _buildAiSenderRow(),
          const SizedBox(height: 8),
          // 白色卡片
          _buildAiCardContainer(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildAiMessageContent(message),
                // [PRD-433 F-14] 参考资料容错：仅当非空时渲染
                if (message.references != null && message.references!.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  _buildReferencesList(message.references!),
                ],
                // [2026-04-25 PRD F5] OCR 详情入口（仅报告解读会话第一条 AI 消息）
                if (showOcrDetailEntry) _buildOcrDetailEntry(),
                const SizedBox(height: 12),
                // [PRD-440] AI 回答操作栏：提示文字（靠右） + 全宽虚线 + 渐变三图标（左下一排）
                _buildAiActionBar440(message),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // [PRD-440] 卡片底部新版操作栏：提示文字（靠右） + 全宽 1px 虚线 + 渐变三图标（左下一排）
  // 顺序固定：复制 → 转发 → 语音播报
  Widget _buildAiActionBar440(ChatMessage message) {
    final isPlaying = _ttsService.isPlaying && _ttsService.currentPlayingId == message.id;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // 提示文字（靠右、11px、#999）
        const Align(
          alignment: Alignment.centerRight,
          child: Padding(
            padding: EdgeInsets.only(bottom: 6),
            child: Text(
              'AI 生成仅供参考',
              style: TextStyle(fontSize: 11, color: Color(0xFF999999), height: 1.4),
            ),
          ),
        ),
        // 全宽 1px 虚线
        const _DashedDivider(color: Color(0xFFE5E5E5)),
        const SizedBox(height: 8),
        Row(
          children: [
            _GradientActionButton(
              kind: _GradientIconKind.copy,
              tooltip: '复制',
              onTap: () => _copyMessage(message.content),
            ),
            const SizedBox(width: 16),
            _GradientActionButton(
              kind: _GradientIconKind.share,
              tooltip: '转发',
              onTap: () => _shareMessage(message),
            ),
            const SizedBox(width: 16),
            _GradientActionButton(
              kind: _GradientIconKind.speaker,
              tooltip: isPlaying ? '停止播报' : '语音播报',
              playing: isPlaying,
              onTap: () => _speakMessage(message),
            ),
          ],
        ),
      ],
    );
  }

  // [PRD-433 F-14] 参考资料列表渲染
  Widget _buildReferencesList(List<Map<String, dynamic>> references) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        border: Border.all(color: const Color(0xFFEAEBED)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('参考资料',
              style: TextStyle(fontSize: 12, color: Color(0xFF6B7280), fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          ...references.asMap().entries.map((e) {
            final idx = e.key + 1;
            final ref = e.value;
            final title = (ref['title'] ?? ref['name'] ?? '').toString();
            final source = (ref['source'] ?? ref['url'] ?? '').toString();
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Text(
                '[$idx] ${title.isNotEmpty ? title : source}',
                style: const TextStyle(fontSize: 12, color: Color(0xFF374151), height: 1.5),
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildAiMessageContent(ChatMessage message) {
    // [PRD-433 F-08] 免责声明改由卡片底部统一渲染，正文剥离 ---disclaimer--- 段
    final parts = message.content.split('---disclaimer---');
    final mainContent = parts[0].trim();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        // [PRD-433 F-13] 长内容：保留 markdown 表格等横滚（MarkdownBody 自身会处理）
        MarkdownBody(
          data: mainContent,
          selectable: true,
          styleSheet: MarkdownStyleSheet(
            p: TextStyle(fontSize: _chatFontSize, height: 1.6, color: const Color(0xFF333333)),
            h1: TextStyle(fontSize: _chatFontSize + 5, fontWeight: FontWeight.bold),
            h2: TextStyle(fontSize: _chatFontSize + 3, fontWeight: FontWeight.bold),
            h3: TextStyle(fontSize: _chatFontSize + 1, fontWeight: FontWeight.bold),
            listBullet: TextStyle(fontSize: _chatFontSize),
          ),
        ),
        if (message.knowledgeHits != null && message.knowledgeHits!.isNotEmpty)
          ...message.knowledgeHits!.map((h) => KnowledgeCard(
                hit: h,
                onFeedback: (hitLogId, feedback) =>
                    Provider.of<ChatProvider>(context, listen: false).submitKnowledgeFeedback(hitLogId, feedback),
              )),
      ],
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
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('切换咨询对象', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  GestureDetector(
                    onTap: () => Navigator.pop(ctx),
                    child: const Icon(Icons.close, color: Color(0xFF999999), size: 22),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: targets.map((t) {
                  final name = t['name']!;
                  final color = _relationColor(name);
                  final isSelected = _currentConsultTarget == name;
                  return GestureDetector(
                    onTap: () {
                      final prevTarget = _currentConsultTarget;
                      setState(() => _currentConsultTarget = name);
                      Navigator.pop(ctx);
                      if (prevTarget != name) {
                        _v4ShowSwitchTripleHints(prevTarget, name);
                      }
                    },
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
              // [PRD-420 F2] 新建家庭成员入口（与 H5/小程序对齐）：跳转到健康档案页面新增成员
              // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31] 点击时先查配额：
              //   满了直接弹"名额已满"框，不进入新增流程；quota_max 来自后端，绝不写死
              Container(
                width: double.infinity,
                margin: const EdgeInsets.only(top: 4),
                padding: const EdgeInsets.symmetric(vertical: 14),
                decoration: BoxDecoration(
                  color: const Color(0xFFF6FFED),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: const Color(0xFF52C41A), width: 1),
                ),
                child: GestureDetector(
                  onTap: () async {
                    Navigator.pop(ctx);
                    await _checkQuotaThenAddMember();
                  },
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.add, color: Color(0xFF52C41A), size: 18),
                      SizedBox(width: 6),
                      Text('新建家庭成员', style: TextStyle(color: Color(0xFF52C41A), fontSize: 13, fontWeight: FontWeight.w500)),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
            ],
          ),
        );
      },
    );
  }

  // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31]
  // 点"+ 新建家庭成员"前先查配额：
  //   - 满了：弹"名额已满"对话框（暂不升级 / 去升级）
  //   - 没满：跳到健康档案页面新增成员（沿用原行为）
  // quota_max 实时来自后端 /api/family/member/quota，绝不写死
  //
  // [PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31 修复版] 完善档案拦截前移：
  //   查名额之前，先查本人 needComplete。needComplete=true 时弹"去完善"对话框，
  //   引导用户跳到 /health-profile（App 端现成的 CompleteSelf 抽屉在该页承接）。
  Future<void> _checkQuotaThenAddMember() async {
    // 1) 先查本人 needComplete（与 H5 / 小程序口径一致）
    try {
      final sres = await _apiService.dio.get('/api/health-profile/self');
      if (sres.statusCode == 200 && sres.data is Map) {
        final body = Map<String, dynamic>.from(sres.data as Map);
        final data = body['data'] is Map
            ? Map<String, dynamic>.from(body['data'] as Map)
            : body;
        final need = data['needComplete'] == true;
        if (need) {
          if (!mounted) return;
          final go = await showDialog<bool>(
            context: context,
            barrierDismissible: true,
            builder: (dctx) => AlertDialog(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              title: const Text('请先完善本人资料',
                  style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
              content: const Text(
                '为了给您提供更精准的健康服务，添加家庭成员前请先完善您的基本资料（姓名、性别、出生日期）。',
                style: TextStyle(fontSize: 14, color: Color(0xFF475569), height: 1.6),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dctx, false),
                  child: const Text('稍后', style: TextStyle(color: Color(0xFF64748B))),
                ),
                ElevatedButton(
                  onPressed: () => Navigator.pop(dctx, true),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF0284C7),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                  ),
                  child: const Text('去完善'),
                ),
              ],
            ),
          );
          if (go == true && mounted) {
            await Navigator.pushNamed(context, '/health-profile');
            await _loadFamilyMembers();
          }
          return;
        }
      }
    } catch (_) {
      // 接口异常时不阻断：继续走原查名额流程
    }

    int quotaMax = 0;
    int quotaRemaining = 0;
    bool quotaOk = false;
    try {
      final resp = await _apiService.dio.get('/api/family/member/quota');
      if (resp.statusCode == 200 && resp.data is Map) {
        final m = resp.data as Map;
        quotaMax = (m['quota_max'] is int) ? (m['quota_max'] as int) : int.tryParse('${m['quota_max']}') ?? 0;
        quotaRemaining = (m['quota_remaining'] is int) ? (m['quota_remaining'] as int) : int.tryParse('${m['quota_remaining']}') ?? 0;
        quotaOk = true;
      }
    } catch (_) {
      // 接口异常时降级：放行让用户进入新增流程
      quotaOk = false;
    }
    if (quotaOk && quotaMax != -1 && quotaRemaining <= 0) {
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        barrierDismissible: true,
        builder: (dctx) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text('家庭成员名额已满', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
          content: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
            decoration: BoxDecoration(
              color: const Color(0xFFFFF7ED),
              borderRadius: BorderRadius.circular(12),
            ),
            child: RichText(
              text: TextSpan(
                style: const TextStyle(fontSize: 14, color: Color(0xFF0F172A), height: 1.6),
                children: [
                  const TextSpan(text: '当前最多可添加 '),
                  TextSpan(
                    text: '$quotaMax',
                    style: const TextStyle(color: Color(0xFFEA580C), fontWeight: FontWeight.w700),
                  ),
                  const TextSpan(text: ' 位家庭成员，升级会员可解锁更多名额。'),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dctx),
              child: const Text('暂不升级', style: TextStyle(color: Color(0xFF0EA5E9))),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.pop(dctx);
                Navigator.pushNamed(context, '/member-center');
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF0284C7),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              ),
              child: const Text('去升级'),
            ),
          ],
        ),
      );
      return;
    }
    // 没满 → 跳到健康档案页面（含成员列表与新增入口）
    if (!mounted) return;
    await Navigator.pushNamed(context, '/health-profile');
    await _loadFamilyMembers();
  }

  Widget _buildInputBar() {
    final targetColor = _relationColor(_currentConsultTarget);
    // [2026-04-25] 报告解读/对比会话：咨询人按钮只读，不可切换
    // [2026-04-25 Bug-04] 兜底：从历史会话恢复时 _initialType 可能为 null，
    // 此时回落到 chatProvider.currentSession?.type 判定。
    final chatProvider = Provider.of<ChatProvider>(context, listen: false);
    final String? sessionType = chatProvider.currentSession?.type;
    final bool isReportSession = _initialType == 'report_interpret'
        || _initialType == 'report_compare'
        || sessionType == 'report_interpret'
        || sessionType == 'report_compare';
    return Container(
      padding: EdgeInsets.only(left: 8, right: 8, top: 8, bottom: MediaQuery.of(context).padding.bottom + 8),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius: 8, offset: const Offset(0, -2))],
      ),
      child: Row(
        children: [
          isReportSession
              ? Tooltip(
                  message: '当前报告所属人：$_currentConsultTarget',
                  child: Container(
                    width: 36, height: 36,
                    decoration: BoxDecoration(shape: BoxShape.circle, color: targetColor),
                    alignment: Alignment.center,
                    child: Text(
                      _currentConsultTarget.length > 2 ? _currentConsultTarget.substring(0, 2) : _currentConsultTarget,
                      style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                  ),
                )
              : GestureDetector(
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

  // [PRD-433 F-12] 输入栏胶囊式：圆角 22 + 背景 F5F7FA
  Widget _buildTextField() {
    return Container(
      decoration: BoxDecoration(
        color: _ChatTokens.inputBg,
        borderRadius: BorderRadius.circular(_ChatTokens.inputRadius),
      ),
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
      // [PRD-AIHOME-INPUT-HINT-OPTIM 2026-06-02 事件2-①] 按住时轻微下沉缩小
      child: AnimatedScale(
        scale: _isRecording ? 0.97 : 1.0,
        duration: const Duration(milliseconds: 120),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          height: 44,
          decoration: BoxDecoration(
            color: _isRecording ? const Color(0xFF3DA512) : const Color(0xFF52C41A),
            borderRadius: BorderRadius.circular(_ChatTokens.inputRadius),
          ),
          alignment: Alignment.center,
          // [PRD-AIHOME-INPUT-HINT-OPTIM 2026-06-02 事件2-③] 文字「按住说话」↔「松开发送」
          child: Text(_isRecording ? '松开发送' : '按住说话', style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w500)),
        ),
      ),
    );
  }
}

// [PRD-433 F-11] Loading 卡片中的三点跳动动画 widget
class _AnimatedDots extends StatefulWidget {
  final Color color;
  final double fontSize;
  const _AnimatedDots({required this.color, this.fontSize = 16});  // const 构造便于在 const Row 子列表中使用

  @override
  State<_AnimatedDots> createState() => _AnimatedDotsState();
}

class _AnimatedDotsState extends State<_AnimatedDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (context, _) {
        final t = _ctrl.value;
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (i) {
            final phase = (t - i * 0.2) % 1.0;
            final opacity = phase < 0.5 ? (0.3 + phase * 1.4).clamp(0.3, 1.0) : (1.7 - phase * 1.4).clamp(0.3, 1.0);
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 1),
              child: Opacity(
                opacity: opacity,
                child: Text(
                  '.',
                  style: TextStyle(
                    color: widget.color,
                    fontSize: widget.fontSize + 4,
                    height: 1,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            );
          }),
        );
      },
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
    // [PRD-AIHOME-INPUT-HINT-OPTIM 2026-06-02 事件2-②] 录音浮层背景改为天蓝半透明，
    // 与产品主色统一；声波与文字用白色，在天蓝底上清晰可见。
    return Material(
      color: const Color(0xFF0EA5E9).withOpacity(0.78),
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
                      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(3)),
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

// [2026-04-23 报告分支] AI 聊天页报告顶部卡片的全屏画廊，复用 PageView + InteractiveViewer
class _ChatReportGallery extends StatefulWidget {
  final List<String> images;
  final int initialIndex;

  const _ChatReportGallery({required this.images, required this.initialIndex});

  @override
  State<_ChatReportGallery> createState() => _ChatReportGalleryState();
}

class _ChatReportGalleryState extends State<_ChatReportGallery> {
  late PageController _controller;
  late int _current;

  @override
  void initState() {
    super.initState();
    _current = widget.initialIndex;
    _controller = PageController(initialPage: widget.initialIndex);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        iconTheme: const IconThemeData(color: Colors.white),
        elevation: 0,
        title: Text(
          '${_current + 1} / ${widget.images.length}',
          style: const TextStyle(color: Colors.white, fontSize: 16),
        ),
      ),
      body: PageView.builder(
        controller: _controller,
        itemCount: widget.images.length,
        onPageChanged: (i) => setState(() => _current = i),
        itemBuilder: (_, i) => Center(
          child: InteractiveViewer(
            minScale: 1.0,
            maxScale: 4.0,
            child: Image.network(
              widget.images[i],
              fit: BoxFit.contain,
              errorBuilder: (_, __, ___) => const Icon(
                Icons.broken_image,
                color: Colors.white54,
                size: 64,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ============================================================================
// [PRD-440] AI 回答操作栏 — 通用辅助组件
// ============================================================================

enum _GradientIconKind { copy, share, speaker }

const LinearGradient _kAiActionGradient = LinearGradient(
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
  colors: [Color(0xFF6A8DFF), Color(0xFFB07CFF)],
);

const Color _kAiActionGray = Color(0xFF999999);

/// 全宽 1px dashed 虚线
class _DashedDivider extends StatelessWidget {
  final Color color;
  final double dashWidth;
  final double dashSpace;
  const _DashedDivider({this.color = const Color(0xFFE5E5E5), this.dashWidth = 4, this.dashSpace = 3});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final boxWidth = constraints.constrainWidth();
        final dashCount = (boxWidth / (dashWidth + dashSpace)).floor();
        return Flex(
          direction: Axis.horizontal,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: List.generate(dashCount, (_) {
            return SizedBox(
              width: dashWidth,
              height: 1,
              child: DecoratedBox(decoration: BoxDecoration(color: color)),
            );
          }),
        );
      },
    );
  }
}

/// 渐变描边操作按钮（含 Wi-Fi 弧线扩散动效）
class _GradientActionButton extends StatefulWidget {
  final _GradientIconKind kind;
  final String tooltip;
  final VoidCallback onTap;
  final bool playing;
  const _GradientActionButton({
    required this.kind,
    required this.tooltip,
    required this.onTap,
    this.playing = false,
  });

  @override
  State<_GradientActionButton> createState() => _GradientActionButtonState();
}

class _GradientActionButtonState extends State<_GradientActionButton> with TickerProviderStateMixin {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    // 默认未触发态：浅灰；播报中或长按：渐变高亮
    final useGradient = widget.playing || _hover;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: (_) => setState(() => _hover = true),
      onTapCancel: () => setState(() => _hover = false),
      onTapUp: (_) => setState(() => _hover = false),
      onTap: widget.onTap,
      child: Tooltip(
        message: widget.tooltip,
        child: SizedBox(
          width: 32,
          height: 32,
          child: Stack(
            alignment: Alignment.center,
            children: [
              if (widget.playing && widget.kind == _GradientIconKind.speaker)
                const _WifiPulseRings(),
              CustomPaint(
                size: const Size(20, 20),
                painter: _GradientIconPainter(kind: widget.kind, useGradient: useGradient),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _GradientIconPainter extends CustomPainter {
  final _GradientIconKind kind;
  final bool useGradient;
  _GradientIconPainter({required this.kind, required this.useGradient});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    if (useGradient) {
      paint.shader = _kAiActionGradient.createShader(Rect.fromLTWH(0, 0, size.width, size.height));
    } else {
      paint.color = _kAiActionGray;
    }

    // 所有图标按 24x24 viewBox 设计，缩放到目标 size
    final sx = size.width / 24.0;
    final sy = size.height / 24.0;
    canvas.save();
    canvas.scale(sx, sy);

    switch (kind) {
      case _GradientIconKind.copy:
        // 前景方块
        final r1 = RRect.fromRectAndRadius(const Rect.fromLTWH(9, 9, 11, 11), const Radius.circular(2));
        canvas.drawRRect(r1, paint);
        // 背景纸角（部分路径）
        final p = Path()
          ..moveTo(5, 15)
          ..lineTo(4.5, 15)
          ..arcToPoint(const Offset(3, 13.5), radius: const Radius.circular(1.5))
          ..lineTo(3, 4.5)
          ..arcToPoint(const Offset(4.5, 3), radius: const Radius.circular(1.5))
          ..lineTo(13.5, 3)
          ..arcToPoint(const Offset(15, 4.5), radius: const Radius.circular(1.5))
          ..lineTo(15, 5);
        canvas.drawPath(p, paint);
        break;
      case _GradientIconKind.share:
        // 三个圆 + 两条连线
        canvas.drawCircle(const Offset(18, 5), 2.5, paint);
        canvas.drawCircle(const Offset(6, 12), 2.5, paint);
        canvas.drawCircle(const Offset(18, 19), 2.5, paint);
        canvas.drawLine(const Offset(8.2, 13.3), const Offset(15.8, 17.7), paint);
        canvas.drawLine(const Offset(15.8, 6.3), const Offset(8.2, 10.7), paint);
        break;
      case _GradientIconKind.speaker:
        // 喇叭多边形
        final p = Path()
          ..moveTo(11, 5)
          ..lineTo(6, 9)
          ..lineTo(3, 9)
          ..lineTo(3, 15)
          ..lineTo(6, 15)
          ..lineTo(11, 19)
          ..close();
        canvas.drawPath(p, paint);
        break;
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _GradientIconPainter old) =>
      old.useGradient != useGradient || old.kind != kind;
}

/// Wi-Fi 弧线扩散动效（1 秒一圈，3 圈错位 333ms）
class _WifiPulseRings extends StatefulWidget {
  const _WifiPulseRings();
  @override
  State<_WifiPulseRings> createState() => _WifiPulseRingsState();
}

class _WifiPulseRingsState extends State<_WifiPulseRings> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1000))..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        return Stack(
          alignment: Alignment.center,
          children: List.generate(3, (i) {
            final phase = (_ctrl.value + (i / 3)) % 1.0;
            // scale 从 1 -> 2.5，opacity 从 1 -> 0
            final scale = 1.0 + (2.5 - 1.0) * phase;
            final opacity = (1.0 - phase).clamp(0.0, 1.0);
            return Opacity(
              opacity: opacity,
              child: Transform.scale(
                scale: scale,
                child: Container(
                  width: 20,
                  height: 20,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: const Color(0xFF6A8DFF), width: 1.0),
                  ),
                ),
              ),
            );
          }),
        );
      },
    );
  }
}
