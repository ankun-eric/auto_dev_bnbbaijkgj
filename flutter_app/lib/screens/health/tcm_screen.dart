import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../../widgets/custom_app_bar.dart';

class TcmScreen extends StatefulWidget {
  const TcmScreen({super.key});

  @override
  State<TcmScreen> createState() => _TcmScreenState();
}

class _TcmScreenState extends State<TcmScreen> {
  final ImagePicker _picker = ImagePicker();

  final List<Map<String, dynamic>> _functions = [
    {
      'title': '舌诊',
      'desc': '拍摄舌头照片，AI智能分析',
      'icon': Icons.camera_alt,
      'color': const Color(0xFFEB2F96),
      'type': 'tongue',
    },
    {
      'title': '面诊',
      'desc': '拍摄面部照片，辨别面色',
      'icon': Icons.face,
      'color': const Color(0xFFFA8C16),
      'type': 'face',
    },
    {
      'title': '体质测评',
      'desc': '回答问卷，了解您的中医体质',
      'icon': Icons.quiz,
      'color': const Color(0xFF722ED1),
      'type': 'constitution',
    },
  ];

  final List<Map<String, String>> _constitutions = [
    {'name': '平和质', 'desc': '体态适中，面色红润'},
    {'name': '气虚质', 'desc': '容易疲乏、气短'},
    {'name': '阳虚质', 'desc': '手脚发凉、畏寒怕冷'},
    {'name': '阴虚质', 'desc': '手足心热、口燥咽干'},
    {'name': '痰湿质', 'desc': '体形肥胖、腹部肥满'},
    {'name': '湿热质', 'desc': '面垢油光、口苦口干'},
    {'name': '血瘀质', 'desc': '肤色晦暗、色素沉着'},
    {'name': '气郁质', 'desc': '情志抑郁、忧虑脆弱'},
    {'name': '特禀质', 'desc': '过敏体质、易生荨麻疹'},
  ];

  Future<void> _takeDiagnosePhoto(String type) async {
    final image = await _picker.pickImage(source: ImageSource.camera);
    if (image != null && mounted) {
      _showDiagnoseResult(type);
    }
  }

  void _showDiagnoseResult(String type) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            const Icon(Icons.spa, color: Color(0xFF722ED1)),
            const SizedBox(width: 8),
            Text(type == 'tongue' ? '舌诊分析' : '面诊分析'),
          ],
        ),
        content: const Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('正在上传图片进行AI分析...', style: TextStyle(fontSize: 14)),
            SizedBox(height: 16),
            Text(
              '分析完成后将为您提供：\n• 体质类型判断\n• 健康状态评估\n• 养生调理建议',
              style: TextStyle(fontSize: 14, height: 1.6, color: Color(0xFF666666)),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('知道了', style: TextStyle(color: Color(0xFF52C41A))),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '中医辨证'),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF722ED1), Color(0xFFEB2F96)],
                ),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                children: [
                  Container(
                    width: 56,
                    height: 56,
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Icon(Icons.spa, color: Colors.white, size: 30),
                  ),
                  const SizedBox(width: 16),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('中医智能辨证', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                        SizedBox(height: 4),
                        Text('结合望闻问切，AI辅助辨证施治', style: TextStyle(color: Colors.white70, fontSize: 13)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            const Text('诊断工具', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            ...List.generate(_functions.length, (index) {
              final func = _functions[index];
              return GestureDetector(
                onTap: () {
                  if (func['type'] == 'constitution') {
                    _showConstitutionTest();
                  } else {
                    _takeDiagnosePhoto(func['type']);
                  }
                },
                child: Container(
                  margin: const EdgeInsets.only(bottom: 12),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.04),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          color: (func['color'] as Color).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(func['icon'], color: func['color'], size: 26),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(func['title'], style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                            const SizedBox(height: 2),
                            Text(func['desc'], style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                          ],
                        ),
                      ),
                      Icon(Icons.chevron_right, color: Colors.grey[400]),
                    ],
                  ),
                ),
              );
            }),
            const SizedBox(height: 24),
            const Text('九种体质', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 3,
                childAspectRatio: 0.9,
                crossAxisSpacing: 10,
                mainAxisSpacing: 10,
              ),
              itemCount: _constitutions.length,
              itemBuilder: (context, index) {
                final item = _constitutions[index];
                return Container(
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.spa, color: Color(0xFF722ED1).withOpacity(0.6 + index * 0.04), size: 28),
                      const SizedBox(height: 6),
                      Text(item['name']!, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 2),
                      Text(
                        item['desc']!,
                        style: TextStyle(fontSize: 10, color: Colors.grey[500]),
                        textAlign: TextAlign.center,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  void _showConstitutionTest() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.8,
        maxChildSize: 0.95,
        minChildSize: 0.5,
        expand: false,
        builder: (context, controller) => Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(color: Colors.grey[300], borderRadius: BorderRadius.circular(2)),
              ),
              const SizedBox(height: 20),
              const Text('中医体质测评', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Text('回答以下问题，了解您的中医体质类型', style: TextStyle(color: Colors.grey[600])),
              const SizedBox(height: 24),
              Expanded(
                child: ListView(
                  controller: controller,
                  children: [
                    _buildQuestion('1. 您是否经常感到疲劳、气短？'),
                    _buildQuestion('2. 您是否手脚发凉、怕冷？'),
                    _buildQuestion('3. 您是否口干舌燥、手足心热？'),
                    _buildQuestion('4. 您是否体形偏胖、腹部肥满？'),
                    _buildQuestion('5. 您是否面部容易出油？'),
                  ],
                ),
              ),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('提交测评'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildQuestion(String question) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFF5F7FA),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(question, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500)),
          const SizedBox(height: 12),
          Row(
            children: ['没有', '很少', '有时', '经常', '总是'].map((option) {
              return Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 2),
                  child: OutlinedButton(
                    onPressed: () {},
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      side: BorderSide(color: Colors.grey[300]!),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                    child: Text(option, style: const TextStyle(fontSize: 12, color: Color(0xFF666666))),
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}
