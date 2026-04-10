import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class CategoryDetailScreen extends StatefulWidget {
  const CategoryDetailScreen({super.key});

  @override
  State<CategoryDetailScreen> createState() => _CategoryDetailScreenState();
}

class _CategoryDetailScreenState extends State<CategoryDetailScreen> {
  final ApiService _apiService = ApiService();
  bool _loading = true;
  bool _aiGenerating = false;

  Map<String, dynamic> _category = {};
  List<Map<String, dynamic>> _recommendedPlans = [];
  List<Map<String, dynamic>> _myPlans = [];

  int? _categoryId;
  String _categoryName = '';

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_categoryId == null) {
      final args = ModalRoute.of(context)?.settings.arguments;
      if (args is Map<String, dynamic>) {
        _categoryId = args['id'] as int?;
        _categoryName = args['name']?.toString() ?? '分类详情';
        if (_categoryId != null) _loadDetail();
      }
    }
  }

  Future<void> _loadDetail() async {
    try {
      final response = await _apiService.getTemplateCategoryDetail(_categoryId!);
      if (response.statusCode == 200 && mounted) {
        final data = response.data is Map ? response.data as Map<String, dynamic> : <String, dynamic>{};
        setState(() {
          _category = data;
          _recommendedPlans = _parseList(data['recommended_plans']);
          _myPlans = _parseList(data['my_plans'] ?? data['user_plans']);
          _loading = false;
        });
        return;
      }
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  List<Map<String, dynamic>> _parseList(dynamic list) {
    if (list is List) return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    return [];
  }

  Future<void> _aiGenerate() async {
    setState(() => _aiGenerating = true);
    try {
      final response = await _apiService.aiGenerateCategoryPlan(_categoryId!);
      if (response.statusCode == 200 && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('AI 计划已生成'), backgroundColor: Color(0xFF52C41A)),
        );
        _loadDetail();
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('生成失败，请稍后重试'), backgroundColor: Colors.red),
        );
      }
    }
    if (mounted) setState(() => _aiGenerating = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_categoryName),
        backgroundColor: const Color(0xFF1890FF),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF1890FF)))
          : RefreshIndicator(
              color: const Color(0xFF1890FF),
              onRefresh: _loadDetail,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildAiCard(),
                    const SizedBox(height: 20),
                    if (_recommendedPlans.isNotEmpty) ...[
                      const Text('推荐计划', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
                      const SizedBox(height: 12),
                      ..._recommendedPlans.map(_buildRecommendedCard),
                      const SizedBox(height: 20),
                    ],
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('我的计划', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
                        GestureDetector(
                          onTap: () => Navigator.pushNamed(context, '/hp-create-plan', arguments: {'category_id': _categoryId}).then((r) {
                            if (r == true) _loadDetail();
                          }),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                            decoration: BoxDecoration(
                              color: const Color(0xFF1890FF).withOpacity(0.1),
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: const Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.add, size: 16, color: Color(0xFF1890FF)),
                                SizedBox(width: 4),
                                Text('创建计划', style: TextStyle(fontSize: 13, color: Color(0xFF1890FF), fontWeight: FontWeight.w500)),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    if (_myPlans.isEmpty)
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.symmetric(vertical: 32),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          children: [
                            Icon(Icons.note_add_outlined, size: 48, color: Colors.grey[300]),
                            const SizedBox(height: 12),
                            Text('还没有自己的计划', style: TextStyle(fontSize: 14, color: Colors.grey[400])),
                          ],
                        ),
                      )
                    else
                      ..._myPlans.map(_buildMyPlanCard),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildAiCard() {
    return GestureDetector(
      onTap: _aiGenerating ? null : _aiGenerate,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          gradient: const LinearGradient(colors: [Color(0xFF1890FF), Color(0xFF13C2C2)]),
        ),
        child: Row(
          children: [
            _aiGenerating
                ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.auto_awesome, color: Colors.white, size: 24),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                _aiGenerating ? 'AI 正在为您定制计划...' : 'AI 智能定制「$_categoryName」计划',
                style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w500),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRecommendedCard(Map<String, dynamic> plan) {
    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, '/hp-recommended-plan', arguments: plan),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8, offset: const Offset(0, 2))],
        ),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: const Color(0xFF1890FF).withOpacity(0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.recommend, color: Color(0xFF1890FF), size: 24),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(plan['plan_name']?.toString() ?? plan['name']?.toString() ?? '', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                  if (plan['description'] != null)
                    Text(plan['description'].toString(), style: TextStyle(fontSize: 12, color: Colors.grey[400]), maxLines: 1, overflow: TextOverflow.ellipsis),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: Colors.grey[400], size: 22),
          ],
        ),
      ),
    );
  }

  Widget _buildMyPlanCard(Map<String, dynamic> plan) {
    final progress = (plan['progress'] ?? 0).toDouble();

    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, '/hp-user-plan', arguments: plan).then((_) => _loadDetail()),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8, offset: const Offset(0, 2))],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(plan['plan_name']?.toString() ?? plan['name']?.toString() ?? '', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                ),
                if (plan['duration_days'] != null)
                  Text('${plan['duration_days']}天', style: TextStyle(fontSize: 12, color: Colors.grey[400])),
              ],
            ),
            if (progress > 0) ...[
              const SizedBox(height: 10),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: progress / 100,
                  backgroundColor: const Color(0xFF1890FF).withOpacity(0.12),
                  valueColor: const AlwaysStoppedAnimation(Color(0xFF1890FF)),
                  minHeight: 6,
                ),
              ),
              const SizedBox(height: 4),
              Text('进度 ${progress.toInt()}%', style: TextStyle(fontSize: 11, color: Colors.grey[400])),
            ],
          ],
        ),
      ),
    );
  }
}
