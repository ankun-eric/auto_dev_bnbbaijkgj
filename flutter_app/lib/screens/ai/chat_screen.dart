import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:image_picker/image_picker.dart';
import '../../providers/chat_provider.dart';
import '../../models/chat_message.dart';
import '../../widgets/custom_app_bar.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final ImagePicker _picker = ImagePicker();

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      Future.delayed(const Duration(milliseconds: 100), () {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      });
    }
  }

  void _sendMessage() {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    final chatProvider = Provider.of<ChatProvider>(context, listen: false);
    chatProvider.sendMessage(text);
    _textController.clear();
    _scrollToBottom();
  }

  Future<void> _pickImage() async {
    final image = await _picker.pickImage(source: ImageSource.gallery);
    if (image != null) {
      final chatProvider = Provider.of<ChatProvider>(context, listen: false);
      chatProvider.sendMessage(image.path, type: 'image');
      _scrollToBottom();
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
      appBar: CustomAppBar(
        title: Provider.of<ChatProvider>(context).currentSession?.typeLabel ?? 'AI问诊',
        actions: [
          IconButton(
            icon: const Icon(Icons.more_horiz, color: Colors.white),
            onPressed: () {},
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
                    'AI建议仅供参考，如有不适请及时就医',
                    style: TextStyle(fontSize: 12, color: Colors.orange[700]),
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: Consumer<ChatProvider>(
              builder: (context, chatProvider, child) {
                if (chatProvider.messages.isEmpty) {
                  return _buildWelcome();
                }
                return ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  itemCount: chatProvider.messages.length,
                  itemBuilder: (context, index) {
                    return _buildMessageBubble(chatProvider.messages[index]);
                  },
                );
              },
            ),
          ),
          _buildInputBar(),
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
            width: 70,
            height: 70,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF52C41A), Color(0xFF13C2C2)],
              ),
              borderRadius: BorderRadius.circular(18),
            ),
            child: const Icon(Icons.smart_toy, color: Colors.white, size: 36),
          ),
          const SizedBox(height: 16),
          const Text(
            '您好，我是小康AI医生',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text(
            '请描述您的症状或健康问题，我会为您提供专业的健康建议。',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 14, color: Colors.grey[600], height: 1.5),
          ),
          const SizedBox(height: 32),
          const Text(
            '常见问题',
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
          ),
          const SizedBox(height: 12),
          ...[
            '最近总是头痛怎么回事？',
            '感冒了应该吃什么药？',
            '血压偏高如何调理？',
            '失眠有什么好的解决方法？',
          ].map((q) => GestureDetector(
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

  Widget _buildMessageBubble(ChatMessage message) {
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
              child: isUser
                  ? Text(
                      message.content,
                      style: const TextStyle(color: Colors.white, fontSize: 15, height: 1.5),
                    )
                  : MarkdownBody(
                      data: message.content,
                      styleSheet: MarkdownStyleSheet(
                        p: const TextStyle(fontSize: 15, height: 1.6, color: Color(0xFF333333)),
                        h1: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                        h2: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        h3: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        listBullet: const TextStyle(fontSize: 15),
                      ),
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

  Widget _buildAvatar(bool isUser) {
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        gradient: isUser
            ? null
            : const LinearGradient(colors: [Color(0xFF52C41A), Color(0xFF13C2C2)]),
        color: isUser ? const Color(0xFFE8F5E9) : null,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Icon(
        isUser ? Icons.person : Icons.smart_toy,
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
            icon: const Icon(Icons.mic, color: Color(0xFF52C41A)),
            onPressed: () {},
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
                  hintText: '描述您的症状...',
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  hintStyle: TextStyle(color: Color(0xFFBBBBBB)),
                ),
                onSubmitted: (_) => _sendMessage(),
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.photo_outlined, color: Color(0xFF52C41A)),
            onPressed: _pickImage,
          ),
          GestureDetector(
            onTap: _sendMessage,
            child: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: const Color(0xFF52C41A),
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Icon(Icons.send, color: Colors.white, size: 18),
            ),
          ),
        ],
      ),
    );
  }
}
