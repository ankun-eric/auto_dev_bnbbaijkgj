import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:image_picker/image_picker.dart';
import '../../config/api_config.dart';
import '../../models/ai_analysis.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';

const kColorDrugHigh = Color(0xFFFF4D4F);
const kColorDrugLow = Color(0xFFFAAD14);
const kColorDrugNormal = Color(0xFF52C41A);

class DrugChatScreen extends StatefulWidget {
  const DrugChatScreen({super.key});

  @override
  State<DrugChatScreen> createState() => _DrugChatScreenState();
}

class _DrugChatScreenState extends State<DrugChatScreen> with SingleTickerProviderStateMixin {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final ImagePicker _picker = ImagePicker();
  final ApiService _api = ApiService();

  String _sessionId = '';
  String _drugName = '用药咨询';
  int? _recordId;
  List<Map<String, dynamic>> _messages = [];
  bool _isLoadingMessages = true;
  bool _isSending = false;

  DrugAnalysisResult? _drugAnalysis;
  bool _isLoadingPersonal = false;
  TabController? _drugTabController;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is Map<String, dynamic> && _sessionId.isEmpty) {
      _sessionId = args['sessionId']?.toString() ?? '';
      _drugName = args['drugName']?.toString() ?? '用药咨询';
      _recordId = args['recordId'] is int
          ? args['recordId']
          : int.tryParse(args['recordId']?.toString() ?? '');

      final aiResult = args['aiResult'];
      if (aiResult != null) {
        _parseDrugAnalysis(aiResult);
      }

      if (_sessionId.isNotEmpty) {
        _loadMessages();
      } else {
        setState(() => _isLoadingMessages = false);
      }
    }
  }

  void _parseDrugAnalysis(dynamic raw) {
    try {
      Map<String, dynamic>? json;
      if (raw is Map<String, dynamic>) {
        json = raw;
      } else if (raw is String && raw.isNotEmpty) {
        json = jsonDecode(raw) as Map<String, dynamic>?;
      }
      if (json != null) {
        final result = DrugAnalysisResult.fromJson(json);
        if (result.drugs.isNotEmpty) {
          _drugAnalysis = result;
          if (result.drugs.length == 1) {
            _drugTabController = TabController(length: 2, vsync: this);
          }
        }
      }
    } catch (_) {}
  }

  Future<void> _loadMessages() async {
    setState(() => _isLoadingMessages = true);
    try {
      final response = await _api.getChatMessages(_sessionId);
      if (response.statusCode == 200) {
        final data = response.data;
        final rawData = data is Map && data.containsKey('data') ? data['data'] : data;
        final list = rawData is List
            ? rawData
            : (rawData is Map ? (rawData['items'] as List? ?? []) : []);

        DrugAnalysisResult? parsed = _drugAnalysis;
        if (parsed == null) {
          for (final msg in list.reversed) {
            final aiResult = msg['ai_result'] ?? msg['structured_result'];
            if (aiResult != null) {
              try {
                Map<String, dynamic>? json;
                if (aiResult is Map<String, dynamic>) {
                  json = aiResult;
                } else if (aiResult is String) {
                  json = jsonDecode(aiResult) as Map<String, dynamic>?;
                }
                if (json != null) {
                  final r = DrugAnalysisResult.fromJson(json);
                  if (r.drugs.isNotEmpty) {
                    parsed = r;
                    break;
                  }
                }
              } catch (_) {}
            }
          }
        }

        setState(() {
          _messages = list.cast<Map<String, dynamic>>();
          if (parsed != null && _drugAnalysis == null) {
            _drugAnalysis = parsed;
            if (parsed.drugs.length == 1 && _drugTabController == null) {
              _drugTabController = TabController(length: 2, vsync: this);
            }
          }
        });
        _scrollToBottom();
      }
    } catch (_) {}
    setState(() => _isLoadingMessages = false);
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
        setState(() {
          _messages.add(Map<String, dynamic>.from(aiData));
        });
        _scrollToBottom();
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _messages.add({
          'id': DateTime.now().millisecondsSinceEpoch.toString(),
          'role': 'assistant',
          'content': '抱歉，网络异常，请稍后重试。',
          'message_type': 'text',
          'created_at': DateTime.now().toIso8601String(),
        });
      });
    }
    setState(() => _isSending = false);
    _scrollToBottom();
  }

  Future<void> _pickAndSendImage(ImageSource source) async {
    if (_isSending || _sessionId.isEmpty) return;
    final image = await _picker.pickImage(source: source);
    if (image == null || !mounted) return;

    setState(() {
      _messages.add({
        'id': DateTime.now().millisecondsSinceEpoch.toString(),
        'role': 'user',
        'content': '[图片识别中...]',
        'message_type': 'image',
        'image_path': image.path,
        'created_at': DateTime.now().toIso8601String(),
      });
      _isSending = true;
    });
    _scrollToBottom();

    try {
      final ocrResponse = await _api.ocrRecognizeDrug(image.path);
      if (!mounted) return;
      if (ocrResponse.statusCode == 200) {
        final ocrData = ocrResponse.data['data'] ?? ocrResponse.data;
        final ocrText = ocrData['ocr_text']?.toString() ?? ocrData['drug_name']?.toString() ?? '';
        if (ocrText.isNotEmpty) {
          final msgResponse = await _api.sendMessage(_sessionId, '识别药品: $ocrText');
          if (!mounted) return;
          if (msgResponse.statusCode == 200) {
            final aiData = msgResponse.data['data'] ?? msgResponse.data;
            setState(() {
              _messages.add(Map<String, dynamic>.from(aiData));
            });
          }
        }
      } else {
        setState(() {
          _messages.add({
            'id': DateTime.now().millisecondsSinceEpoch.toString(),
            'role': 'assistant',
            'content': '图片识别失败，请重试或手动输入药品信息。',
            'message_type': 'text',
            'created_at': DateTime.now().toIso8601String(),
          });
        });
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _messages.add({
          'id': DateTime.now().millisecondsSinceEpoch.toString(),
          'role': 'assistant',
          'content': '网络异常，请检查网络后重试。',
          'message_type': 'text',
          'created_at': DateTime.now().toIso8601String(),
        });
      });
    }
    setState(() => _isSending = false);
    _scrollToBottom();
  }

  Future<void> _loadPersonalSuggestion() async {
    if (_recordId == null || _isLoadingPersonal) return;
    setState(() => _isLoadingPersonal = true);
    try {
      final response = await _api.getDrugPersonalSuggestion(_recordId!);
      if (!mounted) return;
      if (response.statusCode == 200) {
        final data = response.data;
        final suggestion = data['data']?['suggestion'] ??
            data['suggestion']?.toString() ??
            data['data']?.toString() ??
            '';
        if (_drugAnalysis != null && _drugAnalysis!.drugs.isNotEmpty && suggestion.isNotEmpty) {
          setState(() {
            final drugs = List<DrugInfo>.from(_drugAnalysis!.drugs);
            drugs[0] = drugs[0].copyWith(aiSuggestionPersonal: suggestion.toString());
            _drugAnalysis = DrugAnalysisResult(
              drugs: drugs,
              interactions: _drugAnalysis!.interactions,
            );
          });
        }
      }
    } catch (_) {}
    if (mounted) setState(() => _isLoadingPersonal = false);
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
    _drugTabController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
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
          if (_drugAnalysis != null) _buildDrugAnalysisPanel(),
          Expanded(
            child: _isLoadingMessages
                ? const Center(child: CircularProgressIndicator(color: kColorDrugNormal))
                : _messages.isEmpty
                    ? _buildEmptyState()
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        itemCount: _messages.length + (_isSending ? 1 : 0),
                        itemBuilder: (context, index) {
                          if (index == _messages.length && _isSending) {
                            return _buildLoadingBubble();
                          }
                          return _buildMessageBubble(_messages[index]);
                        },
                      ),
          ),
          _buildInputBar(),
        ],
      ),
    );
  }

  Widget _buildDrugAnalysisPanel() {
    final analysis = _drugAnalysis!;
    if (analysis.drugs.length > 1) {
      return _buildMultiDrugPanel(analysis);
    }
    return _buildSingleDrugPanel(analysis.drugs.first);
  }

  Widget _buildMultiDrugPanel(DrugAnalysisResult analysis) {
    return Container(
      constraints: const BoxConstraints(maxHeight: 360),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (analysis.interactions.isNotEmpty)
              _buildInteractionWarning(analysis.interactions),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Text(
                '识别药物（${analysis.drugs.length}种）',
                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
              ),
            ),
            ...analysis.drugs.map((drug) => _buildDrugExpansionTile(drug)),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  Widget _buildInteractionWarning(List<DrugInteraction> interactions) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBE6),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: kColorDrugLow.withOpacity(0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.warning_amber_rounded, color: kColorDrugLow, size: 18),
              SizedBox(width: 6),
              Text(
                '药物相互作用提示',
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: kColorDrugLow),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...interactions.map((interaction) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('• ', style: TextStyle(color: kColorDrugLow)),
                    Expanded(
                      child: RichText(
                        text: TextSpan(
                          style: const TextStyle(fontSize: 13, color: Color(0xFF333333), height: 1.4),
                          children: [
                            TextSpan(
                              text: interaction.drugs.join(' + '),
                              style: const TextStyle(fontWeight: FontWeight.w600),
                            ),
                            const TextSpan(text: '：'),
                            TextSpan(text: interaction.risk),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildDrugExpansionTile(DrugInfo drug) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(color: Colors.grey[200]!),
      ),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        title: Text(drug.name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
        subtitle: drug.specification != null
            ? Text(drug.specification!, style: TextStyle(fontSize: 12, color: Colors.grey[500]))
            : null,
        children: [
          _buildDrugInfoRows(drug),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Widget _buildSingleDrugPanel(DrugInfo drug) {
    return Container(
      constraints: const BoxConstraints(maxHeight: 400),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildSingleDrugCard(drug),
            _buildDrugSuggestionTabs(drug),
          ],
        ),
      ),
    );
  }

  Widget _buildSingleDrugCard(DrugInfo drug) {
    return Card(
      margin: const EdgeInsets.all(16),
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.medication, color: Color(0xFFEB2F96), size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    drug.name,
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            if (drug.specification != null) ...[
              const SizedBox(height: 4),
              Text(drug.specification!, style: TextStyle(fontSize: 12, color: Colors.grey[500])),
            ],
            const Divider(height: 20),
            _buildDrugInfoRows(drug),
          ],
        ),
      ),
    );
  }

  Widget _buildDrugInfoRows(DrugInfo drug) {
    final rows = <_DrugInfoRow>[];
    if (drug.ingredients != null) rows.add(_DrugInfoRow('成分', drug.ingredients!));
    if (drug.indications != null) rows.add(_DrugInfoRow('适应症', drug.indications!));
    if (drug.dosage != null) rows.add(_DrugInfoRow('用法用量', drug.dosage!));
    if (drug.precautions != null) rows.add(_DrugInfoRow('注意事项', drug.precautions!));

    if (rows.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: rows.map((row) => _buildInfoRow(row.label, row.value)).toList(),
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 64,
            child: Text(
              label,
              style: TextStyle(fontSize: 13, color: Colors.grey[600], fontWeight: FontWeight.w500),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontSize: 13, color: Color(0xFF333333), height: 1.4),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDrugSuggestionTabs(DrugInfo drug) {
    if (_drugTabController == null) return const SizedBox.shrink();

    return Column(
      children: [
        TabBar(
          controller: _drugTabController,
          labelColor: const Color(0xFFEB2F96),
          unselectedLabelColor: Colors.grey[600],
          indicatorColor: const Color(0xFFEB2F96),
          labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
          tabs: const [
            Tab(text: '通用建议'),
            Tab(text: '个性化建议'),
          ],
          onTap: (index) {
            if (index == 1 && drug.aiSuggestionPersonal == null) {
              _loadPersonalSuggestion();
            }
          },
        ),
        SizedBox(
          height: 120,
          child: TabBarView(
            controller: _drugTabController,
            children: [
              _buildSuggestionContent(drug.aiSuggestionGeneral, '暂无通用建议'),
              _buildPersonalSuggestionContent(drug),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildSuggestionContent(String? text, String emptyHint) {
    if (text == null || text.isEmpty) {
      return Center(child: Text(emptyHint, style: TextStyle(color: Colors.grey[400], fontSize: 13)));
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Text(text, style: const TextStyle(fontSize: 13, color: Color(0xFF333333), height: 1.5)),
    );
  }

  Widget _buildPersonalSuggestionContent(DrugInfo drug) {
    if (_isLoadingPersonal) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFFEB2F96)));
    }
    if (drug.aiSuggestionPersonal != null && drug.aiSuggestionPersonal!.isNotEmpty) {
      return SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Text(
          drug.aiSuggestionPersonal!,
          style: const TextStyle(fontSize: 13, color: Color(0xFF333333), height: 1.5),
        ),
      );
    }
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text('暂无个性化建议', style: TextStyle(color: Colors.grey[400], fontSize: 13)),
          if (_recordId != null) ...[
            const SizedBox(height: 8),
            TextButton(
              onPressed: _loadPersonalSuggestion,
              child: const Text('点击获取', style: TextStyle(color: Color(0xFFEB2F96))),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.medication_outlined, size: 60, color: Colors.grey[300]),
          const SizedBox(height: 12),
          Text('暂无消息', style: TextStyle(color: Colors.grey[500])),
          const SizedBox(height: 6),
          Text('输入问题或拍照识药开始咨询', style: TextStyle(color: Colors.grey[400], fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(Map<String, dynamic> msg) {
    final isUser = msg['role'] == 'user';
    final content = msg['content']?.toString() ?? '';
    final messageType = msg['message_type']?.toString() ?? msg['type']?.toString() ?? 'text';
    final imageUrl = msg['image_url']?.toString();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isUser) ...[
            _buildAvatar(false),
            const SizedBox(width: 10),
          ],
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.7,
              ),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: isUser ? kColorDrugNormal : Colors.white,
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
                  if (messageType == 'image' && imageUrl != null && imageUrl.isNotEmpty)
                    GestureDetector(
                      onTap: () => _showImageDialog(imageUrl),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: Image.network(
                          imageUrl,
                          width: 180,
                          height: 180,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => Container(
                            width: 180,
                            height: 100,
                            color: Colors.grey[200],
                            child: const Icon(Icons.broken_image, color: Colors.grey),
                          ),
                        ),
                      ),
                    ),
                  if (content.isNotEmpty)
                    isUser
                        ? Text(
                            content,
                            style: const TextStyle(color: Colors.white, fontSize: 15, height: 1.5),
                          )
                        : _buildAiContent(content),
                ],
              ),
            ),
          ),
          if (isUser) ...[
            const SizedBox(width: 10),
            _buildAvatar(true),
          ],
        ],
      ),
    );
  }

  Widget _buildAiContent(String content) {
    final parts = content.split('---disclaimer---');
    final mainContent = parts[0].trim();
    final disclaimer = parts.length > 1 ? parts[1].trim() : null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        MarkdownBody(
          data: mainContent,
          styleSheet: MarkdownStyleSheet(
            p: const TextStyle(fontSize: 15, height: 1.6, color: Color(0xFF333333)),
            h1: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            h2: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            h3: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            listBullet: const TextStyle(fontSize: 15),
          ),
        ),
        if (disclaimer != null) ...[
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.only(top: 8),
            decoration: const BoxDecoration(
              border: Border(top: BorderSide(color: Color(0xFFE8E8E8), width: 0.5)),
            ),
            child: Text(
              disclaimer,
              style: const TextStyle(
                fontSize: 11,
                color: Color(0xFF999999),
                fontStyle: FontStyle.italic,
                height: 1.4,
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildLoadingBubble() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAvatar(false),
          const SizedBox(width: 10),
          Container(
            padding: const EdgeInsets.all(16),
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
        gradient: isUser
            ? null
            : const LinearGradient(colors: [Color(0xFFEB2F96), Color(0xFF722ED1)]),
        color: isUser ? const Color(0xFFE8F5E9) : null,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Icon(
        isUser ? Icons.person : Icons.medication,
        color: isUser ? kColorDrugNormal : Colors.white,
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
          IconButton(
            icon: const Icon(Icons.camera_alt, color: Color(0xFFEB2F96)),
            onPressed: _isSending ? null : () => _pickAndSendImage(ImageSource.camera),
          ),
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: const Color(0xFFF5F7FA),
                borderRadius: BorderRadius.circular(20),
              ),
              child: TextField(
                controller: _textController,
                maxLines: 3,
                minLines: 1,
                decoration: const InputDecoration(
                  hintText: '输入用药问题...',
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  hintStyle: TextStyle(color: Color(0xFFBBBBBB)),
                ),
                onSubmitted: (_) => _sendTextMessage(),
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.photo_outlined, color: Color(0xFFEB2F96)),
            onPressed: _isSending ? null : () => _pickAndSendImage(ImageSource.gallery),
          ),
          GestureDetector(
            onTap: _isSending ? null : _sendTextMessage,
            child: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: _isSending ? Colors.grey[300] : const Color(0xFFEB2F96),
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Icon(Icons.send, color: Colors.white, size: 18),
            ),
          ),
        ],
      ),
    );
  }

  void _showImageDialog(String imageUrl) {
    showDialog(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: Colors.transparent,
        child: GestureDetector(
          onTap: () => Navigator.pop(context),
          child: InteractiveViewer(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.network(imageUrl, fit: BoxFit.contain),
            ),
          ),
        ),
      ),
    );
  }
}

class _DrugInfoRow {
  final String label;
  final String value;
  const _DrugInfoRow(this.label, this.value);
}
