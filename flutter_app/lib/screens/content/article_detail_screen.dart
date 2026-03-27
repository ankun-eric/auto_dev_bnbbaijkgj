import 'package:flutter/material.dart';
import '../../widgets/custom_app_bar.dart';

class ArticleDetailScreen extends StatefulWidget {
  const ArticleDetailScreen({super.key});

  @override
  State<ArticleDetailScreen> createState() => _ArticleDetailScreenState();
}

class _ArticleDetailScreenState extends State<ArticleDetailScreen> {
  bool _isCollected = false;
  final TextEditingController _commentController = TextEditingController();

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: CustomAppBar(
        title: '文章详情',
        actions: [
          IconButton(
            icon: Icon(
              _isCollected ? Icons.bookmark : Icons.bookmark_border,
              color: _isCollected ? Colors.amber : Colors.white,
            ),
            onPressed: () => setState(() => _isCollected = !_isCollected),
          ),
          IconButton(
            icon: const Icon(Icons.share, color: Colors.white),
            onPressed: () {},
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '春季养生：如何预防过敏性鼻炎',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, height: 1.3),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Container(
                        width: 30,
                        height: 30,
                        decoration: BoxDecoration(
                          color: const Color(0xFF52C41A).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(15),
                        ),
                        child: const Icon(Icons.person, color: Color(0xFF52C41A), size: 18),
                      ),
                      const SizedBox(width: 8),
                      const Text('健康专家', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
                      const SizedBox(width: 12),
                      Text('2024-03-25', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                      const Spacer(),
                      Icon(Icons.visibility, size: 16, color: Colors.grey[400]),
                      const SizedBox(width: 4),
                      Text('2345', style: TextStyle(fontSize: 13, color: Colors.grey[400])),
                    ],
                  ),
                  const Divider(height: 32),
                  const Text(
                    '春季是过敏性鼻炎的高发季节。随着气温回升，花粉、柳絮等过敏原增多，很多人会出现打喷嚏、流鼻涕、鼻塞等症状。\n\n'
                    '## 什么是过敏性鼻炎？\n\n'
                    '过敏性鼻炎是免疫系统对特定过敏原产生的过度反应。常见症状包括：\n'
                    '- 频繁打喷嚏\n'
                    '- 鼻塞、流清涕\n'
                    '- 鼻痒、眼痒\n'
                    '- 嗅觉减退\n\n'
                    '## 预防措施\n\n'
                    '1. **减少外出**：花粉浓度高的时段（上午10点至下午4点）尽量避免外出。\n\n'
                    '2. **佩戴口罩**：外出时佩戴防护口罩，减少过敏原吸入。\n\n'
                    '3. **室内通风**：使用空气净化器，保持室内空气清新。\n\n'
                    '4. **鼻腔冲洗**：每天用生理盐水冲洗鼻腔，清除过敏原。\n\n'
                    '5. **增强免疫力**：规律作息，适当运动，均衡饮食。\n\n'
                    '## 中医调理建议\n\n'
                    '中医认为过敏性鼻炎多与肺气虚、脾气虚有关。可以通过以下方法调理：\n'
                    '- 黄芪、白术泡茶饮用\n'
                    '- 按摩迎香穴、印堂穴\n'
                    '- 艾灸大椎穴、肺俞穴\n\n'
                    '如果症状严重，建议及时就医，在医生指导下用药治疗。',
                    style: TextStyle(fontSize: 16, height: 1.8, color: Color(0xFF333333)),
                  ),
                  const SizedBox(height: 20),
                  Wrap(
                    spacing: 8,
                    children: ['养生', '鼻炎', '春季健康'].map((tag) {
                      return Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                        decoration: BoxDecoration(
                          color: const Color(0xFF52C41A).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(tag, style: const TextStyle(fontSize: 12, color: Color(0xFF52C41A))),
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 24),
                  const Text('评论', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 12),
                  _buildComment('小明', '非常实用的文章，学到了很多！', '2小时前'),
                  _buildComment('健康达人', '每年春天都会犯鼻炎，试试文章里的方法', '5小时前'),
                  _buildComment('中医爱好者', '中医调理的建议很好，已收藏', '1天前'),
                  const SizedBox(height: 20),
                ],
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
                    decoration: BoxDecoration(
                      color: const Color(0xFFF5F7FA),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: TextField(
                      controller: _commentController,
                      decoration: const InputDecoration(
                        hintText: '说点什么...',
                        border: InputBorder.none,
                        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                      ),
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.thumb_up_outlined, color: Color(0xFF999999)),
                  onPressed: () {},
                ),
                IconButton(
                  icon: Icon(
                    _isCollected ? Icons.bookmark : Icons.bookmark_border,
                    color: _isCollected ? Colors.amber : const Color(0xFF999999),
                  ),
                  onPressed: () => setState(() => _isCollected = !_isCollected),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildComment(String name, String content, String time) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: const Color(0xFFE8F5E9),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Center(
              child: Text(name[0], style: const TextStyle(color: Color(0xFF52C41A), fontWeight: FontWeight.bold)),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                    const Spacer(),
                    Text(time, style: TextStyle(fontSize: 12, color: Colors.grey[400])),
                  ],
                ),
                const SizedBox(height: 4),
                Text(content, style: TextStyle(fontSize: 14, color: Colors.grey[700], height: 1.4)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
