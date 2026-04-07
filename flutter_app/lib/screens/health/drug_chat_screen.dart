import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:image_picker/image_picker.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';

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
  String _drugName = '用药咨询';
  List<Map<String, dynamic>> _messages = [];
  bool _isLoadingMessages = true;
  bool _isSending = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is Map<String, dynamic> && _sessionId.isEmpty) {
      _sessionId = args['sessionId']?.toString() ?? '';
      _drugName = args['drugName']?.toString() ?? '用药咨询';
      if (_sessionId.isNotEmpty) {
        _loadMessages();
      }
    }
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
        setState(() {
          _messages = list.cast<Map<String, dynamic>>();
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

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: CustomAppBar(title: _drugName),
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
            child: _isLoadingMessages
                ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
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
                color: isUser ? const Color(0xFF52C41A) : Colors.white,
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
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.grey[400],
                  ),
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
        color: isUser ? const Color(0xFF52C41A) : Colors.white,
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
