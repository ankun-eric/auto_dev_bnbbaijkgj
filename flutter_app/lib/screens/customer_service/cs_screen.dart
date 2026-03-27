import 'package:flutter/material.dart';
import '../../widgets/custom_app_bar.dart';

class CsScreen extends StatefulWidget {
  const CsScreen({super.key});

  @override
  State<CsScreen> createState() => _CsScreenState();
}

class _CsScreenState extends State<CsScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  final List<Map<String, dynamic>> _messages = [
    {'role': 'system', 'content': '您好！我是宾尼小康客服，有什么可以帮您的？', 'time': '10:00'},
  ];

  final List<String> _quickQuestions = [
    '如何预约服务？',
    '如何查看订单？',
    '如何申请退款？',
    '如何联系专家？',
    '积分如何使用？',
  ];

  void _sendMessage(String text) {
    if (text.trim().isEmpty) return;
    setState(() {
      _messages.add({'role': 'user', 'content': text, 'time': TimeOfDay.now().format(context)});
    });
    _textController.clear();

    Future.delayed(const Duration(seconds: 1), () {
      if (mounted) {
        setState(() {
          _messages.add({
            'role': 'system',
            'content': '感谢您的咨询，客服人员正在为您处理，请稍候...',
            'time': TimeOfDay.now().format(context),
          });
        });
        _scrollToBottom();
      }
    });

    _scrollToBottom();
  }

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

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '在线客服'),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(16),
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final msg = _messages[index];
                final isUser = msg['role'] == 'user';

                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Row(
                    mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (!isUser)
                        Container(
                          width: 36,
                          height: 36,
                          margin: const EdgeInsets.only(right: 8),
                          decoration: BoxDecoration(
                            color: const Color(0xFF52C41A).withOpacity(0.1),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: const Icon(Icons.headset_mic, color: Color(0xFF52C41A), size: 20),
                        ),
                      Flexible(
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                          decoration: BoxDecoration(
                            color: isUser ? const Color(0xFF52C41A) : Colors.white,
                            borderRadius: BorderRadius.only(
                              topLeft: const Radius.circular(14),
                              topRight: const Radius.circular(14),
                              bottomLeft: Radius.circular(isUser ? 14 : 4),
                              bottomRight: Radius.circular(isUser ? 4 : 14),
                            ),
                          ),
                          child: Text(
                            msg['content'],
                            style: TextStyle(
                              color: isUser ? Colors.white : const Color(0xFF333333),
                              fontSize: 15,
                              height: 1.4,
                            ),
                          ),
                        ),
                      ),
                      if (isUser)
                        Container(
                          width: 36,
                          height: 36,
                          margin: const EdgeInsets.only(left: 8),
                          decoration: BoxDecoration(
                            color: const Color(0xFFE8F5E9),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: const Icon(Icons.person, color: Color(0xFF52C41A), size: 20),
                        ),
                    ],
                  ),
                );
              },
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            color: const Color(0xFFF5F7FA),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: _quickQuestions.map((q) {
                  return GestureDetector(
                    onTap: () => _sendMessage(q),
                    child: Container(
                      margin: const EdgeInsets.only(right: 8),
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: const Color(0xFF52C41A).withOpacity(0.3)),
                      ),
                      child: Text(q, style: const TextStyle(fontSize: 13, color: Color(0xFF52C41A))),
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
          Container(
            padding: EdgeInsets.only(
              left: 12,
              right: 12,
              top: 8,
              bottom: MediaQuery.of(context).padding.bottom + 8,
            ),
            color: Colors.white,
            child: Row(
              children: [
                Expanded(
                  child: Container(
                    decoration: BoxDecoration(
                      color: const Color(0xFFF5F7FA),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: TextField(
                      controller: _textController,
                      decoration: const InputDecoration(
                        hintText: '输入您的问题...',
                        border: InputBorder.none,
                        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                      ),
                      onSubmitted: _sendMessage,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                GestureDetector(
                  onTap: () => _sendMessage(_textController.text),
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
          ),
        ],
      ),
    );
  }
}
