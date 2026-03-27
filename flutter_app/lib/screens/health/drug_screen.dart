import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../../widgets/custom_app_bar.dart';

class DrugScreen extends StatefulWidget {
  const DrugScreen({super.key});

  @override
  State<DrugScreen> createState() => _DrugScreenState();
}

class _DrugScreenState extends State<DrugScreen> {
  final TextEditingController _searchController = TextEditingController();
  final ImagePicker _picker = ImagePicker();
  List<Map<String, String>> _searchResults = [];
  bool _isSearching = false;

  final List<Map<String, String>> _hotDrugs = [
    {'name': '阿莫西林', 'category': '抗生素'},
    {'name': '布洛芬', 'category': '解热镇痛'},
    {'name': '感冒灵', 'category': '感冒用药'},
    {'name': '板蓝根', 'category': '清热解毒'},
    {'name': '维生素C', 'category': '营养补充'},
    {'name': '六味地黄丸', 'category': '中成药'},
  ];

  void _search() {
    final keyword = _searchController.text.trim();
    if (keyword.isEmpty) return;
    setState(() {
      _isSearching = true;
      _searchResults = _hotDrugs
          .where((d) => d['name']!.contains(keyword))
          .toList();
      _isSearching = false;
    });
  }

  Future<void> _identifyDrug() async {
    final image = await _picker.pickImage(source: ImageSource.camera);
    if (image != null && mounted) {
      showDialog(
        context: context,
        builder: (context) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Row(
            children: [
              Icon(Icons.medication, color: Color(0xFFEB2F96)),
              SizedBox(width: 8),
              Text('药物识别'),
            ],
          ),
          content: const Text('正在识别药物，请稍候...\n\nAI将分析药物图片，为您提供药品名称、功效、用法用量等信息。'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('关闭', style: TextStyle(color: Color(0xFF52C41A))),
            ),
          ],
        ),
      );
    }
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '药物查询'),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              color: Colors.white,
              child: Row(
                children: [
                  Expanded(
                    child: Container(
                      decoration: BoxDecoration(
                        color: const Color(0xFFF5F7FA),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: TextField(
                        controller: _searchController,
                        decoration: const InputDecoration(
                          hintText: '输入药品名称搜索',
                          prefixIcon: Icon(Icons.search, color: Color(0xFF999999)),
                          border: InputBorder.none,
                          contentPadding: EdgeInsets.symmetric(vertical: 14),
                        ),
                        onSubmitted: (_) => _search(),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  GestureDetector(
                    onTap: _search,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF52C41A),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Text('搜索', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                    ),
                  ),
                ],
              ),
            ),
            GestureDetector(
              onTap: _identifyDrug,
              child: Container(
                margin: const EdgeInsets.all(16),
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [const Color(0xFFEB2F96).withOpacity(0.1), const Color(0xFF722ED1).withOpacity(0.1)],
                  ),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFEB2F96).withOpacity(0.3)),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.camera_alt, color: Color(0xFFEB2F96), size: 32),
                    SizedBox(width: 16),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('拍照识药', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                        SizedBox(height: 2),
                        Text('拍摄药品照片，AI自动识别', style: TextStyle(fontSize: 13, color: Color(0xFF999999))),
                      ],
                    ),
                    Spacer(),
                    Icon(Icons.chevron_right, color: Color(0xFF999999)),
                  ],
                ),
              ),
            ),
            if (_searchResults.isNotEmpty) ...[
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text('搜索结果', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.grey[800])),
              ),
              const SizedBox(height: 8),
              ...List.generate(_searchResults.length, (index) => _buildDrugCard(_searchResults[index])),
              const SizedBox(height: 16),
            ],
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text('热门药品', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.grey[800])),
            ),
            const SizedBox(height: 8),
            ...List.generate(_hotDrugs.length, (index) => _buildDrugCard(_hotDrugs[index])),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildDrugCard(Map<String, String> drug) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: const Color(0xFFEB2F96).withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.medication, color: Color(0xFFEB2F96)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(drug['name']!, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                const SizedBox(height: 2),
                Text(drug['category']!, style: TextStyle(fontSize: 13, color: Colors.grey[500])),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: const Color(0xFF52C41A).withOpacity(0.1),
              borderRadius: BorderRadius.circular(16),
            ),
            child: const Text('查看详情', style: TextStyle(fontSize: 12, color: Color(0xFF52C41A))),
          ),
        ],
      ),
    );
  }
}
