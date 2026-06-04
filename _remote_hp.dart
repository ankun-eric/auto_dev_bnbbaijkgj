import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../widgets/checkin_points_progress.dart';

class HealthPlanScreen extends StatefulWidget {
  const HealthPlanScreen({super.key});

  @override
  State<HealthPlanScreen> createState() => _HealthPlanScreenState();
}

class _HealthPlanScreenState extends State<HealthPlanScreen> {
  final ApiService _apiService = ApiService();
  final _progressKey = GlobalKey<CheckinPointsProgressState>();
  bool _loading = true;
  bool _aiGenerating = false;

  List<Map<String, dynamic>> _todoGroups = [];
  int _totalCompleted = 0;
  int _totalCount = 0;

  static const _groupTypeConfig = <String, Map<String, dynamic>>{
    'medication': {'icon': Icons.medication_rounded, 'color': Color(0xFFFA8C16), 'label': '用药提醒', 'route': '/hp-medications'},
    'checkin': {'icon': Icons.check_circle_outline_rounded, 'color': Color(0xFF52C41A), 'label': '健康打卡', 'route': '/hp-checkins'},
    'custom': {'icon': Icons.flag_rounded, 'color': Color(0xFF1890FF), 'label': '自定义计划', 'route': '/hp-template-categories'},
  };

  @override
  void initState() {
    super.initState();
    _loadTodayTodos();
  }

  Future<void> _loadTodayTodos() async {
    try {
      final response = await _apiService.getTodayTodos();
      if (response.statusCode == 200 && mounted) {
        final data = response.data is Map ? response.data as Map<String, dynamic> : <String, dynamic>{};
        setState(() {
          _todoGroups = _parseList(data['groups']);
          _totalCompleted = data['total_completed'] ?? 0;
          _totalCount = data['total_count'] ?? 0;
          _loading = false;
        });
        return;
      }
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  List<Map<String, dynamic>> _parseList(dynamic list) {
    if (list is List) {
      return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    return [];
  }

  Future<void> _aiGeneratePlan() async {
    setState(() => _aiGenerating = true);
    try {
      final response = await _apiService.aiGeneratePlan({});
      if (response.statusCode == 200 && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('AI 计划已生成'), backgroundColor: Color(0xFF52C41A)),
        );
        _loadTodayTodos();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('生成失败，请稍后重试'), backgroundColor: Colors.red),
        );
      }
    }
    if (mounted) setState(() => _aiGenerating = false);
  }

  void _showPointsSnackBar(Map<String, dynamic>? responseData) {
    if (!mounted || responseData == null) return;
    final pointsEarned = responseData['points_earned'] as int? ?? 0;
    final limitReached = responseData['points_limit_reached'] == true;
    if (pointsEarned > 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('打卡成功，获得 $pointsEarned 积分！'), backgroundColor: const Color(0xFF52C41A)),
      );
    } else if (limitReached) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('打卡成功！今日打卡积分已达上限'), backgroundColor: Color(0xFFFA8C16)),
      );
    }
    _progressKey.currentState?.loadProgress();
  }

  Future<void> _handleQuickCheckin(Map<String, dynamic> item) async {
    final type = item['type']?.toString() ?? '';
    if (type == 'checkin' && item['target_value'] != null) {
      final controller = TextEditingController();
      final result = await showDialog<double>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('${item['name']} 打卡'),
          content: TextField(
            controller: controller,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(
              hintText: '请输入实际值',
              suffixText: item['target_unit']?.toString() ?? '',
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
            TextButton(
              onPressed: () => Navigator.pop(ctx, double.tryParse(controller.text)),
              child: const Text('确认打卡'),
            ),
          ],
        ),
      );
      if (result != null) {
        try {
          final response = await _apiService.quickCheckin(item['id'] as int, type, value: result);
          _showPointsSnackBar(response.data is Map ? response.data as Map<String, dynamic> : null);
          _loadTodayTodos();
        } catch (_) {}
      }
      return;
    }

    try {
      final response = await _apiService.quickCheckin(item['id'] as int, type);
      _showPointsSnackBar(response.data is Map ? response.data as Map<String, dynamic> : null);
      _loadTodayTodos();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('健康计划'),
        backgroundColor: const Color(0xFF52C41A),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.bar_chart_rounded),
            onPressed: () => Navigator.pushNamed(context, '/hp-statistics'),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
          : RefreshIndicator(
              color: const Color(0xFF52C41A),
              onRefresh: () async {
                await _loadTodayTodos();
                _progressKey.currentState?.loadProgress();
              },
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    CheckinPointsProgress(key: _progressKey),
                    const SizedBox(height: 16),
                    _buildAiGenerateButton(),
                    const SizedBox(height: 20),
                    _buildCategoryCards(),
                    const SizedBox(height: 20),
                    _buildTodaySection(),
                    const SizedBox(height: 20),
                    _buildStatisticsEntry(),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildAiGenerateButton() {
    return GestureDetector(
      onTap: _aiGenerating ? null : _aiGeneratePlan,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF52C41A), Color(0xFF13C2C2)],
          ),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF52C41A).withOpacity(0.3),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.2),
                borderRadius: BorderRadius.circular(12),
              ),
              child: _aiGenerating
                  ? const Padding(
                      padding: EdgeInsets.all(12),
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.auto_awesome, color: Colors.white, size: 26),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _aiGenerating ? 'AI 正在生成计划...' : 'AI 智能生成健康计划',
                    style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '基于您的健康档案，为您量身定制',
                    style: TextStyle(color: Colors.white.withOpacity(0.85), fontSize: 13),
                  ),
                ],
              ),
            ),
            Icon(Icons.arrow_forward_ios, color: Colors.white.withOpacity(0.7), size: 16),
          ],
        ),
      ),
    );
  }

  Widget _buildCategoryCards() {
    final categories = [
      _groupTypeConfig['medication']!,
      _groupTypeConfig['checkin']!,
      _groupTypeConfig['custom']!,
    ];
    final subtitles = ['按时服药，健康管理', '每日打卡，养成习惯', '个性定制，目标达成'];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('健康管理', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
        const SizedBox(height: 12),
        ...categories.asMap().entries.map((entry) {
          final idx = entry.key;
          final cat = entry.value;
          final color = cat['color'] as Color;
          return GestureDetector(
            onTap: () => Navigator.pushNamed(context, cat['route'] as String).then((_) => _loadTodayTodos()),
            child: Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8, offset: const Offset(0, 2)),
                ],
              ),
              child: Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(cat['icon'] as IconData, color: color, size: 26),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(cat['label'] as String, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF333333))),
                        const SizedBox(height: 2),
                        Text(subtitles[idx], style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                      ],
                    ),
                  ),
                  Icon(Icons.chevron_right, color: Colors.grey[400], size: 22),
                ],
              ),
            ),
          );
        }),
      ],
    );
  }

  Widget _buildTodaySection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('今日待办', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
            if (_totalCount > 0)
              Text('$_totalCompleted/$_totalCount 已完成', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
          ],
        ),
        const SizedBox(height: 12),
        if (_totalCount == 0)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 40),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              children: [
                Icon(Icons.event_available, size: 48, color: Colors.grey[300]),
                const SizedBox(height: 12),
                Text('暂无待办事项', style: TextStyle(fontSize: 14, color: Colors.grey[400])),
                const SizedBox(height: 4),
                Text('添加用药提醒或健康打卡来开始吧', style: TextStyle(fontSize: 12, color: Colors.grey[300])),
              ],
            ),
          )
        else
          for (final group in _todoGroups) _buildGroupSection(group),
      ],
    );
  }

  Widget _buildGroupSection(Map<String, dynamic> group) {
    final groupType = group['group_type']?.toString() ?? '';
    final config = _groupTypeConfig[groupType] ?? _groupTypeConfig['custom']!;
    final icon = config['icon'] as IconData;
    final color = config['color'] as Color;
    final groupName = group['group_name']?.toString() ?? '';
    final isEmpty = group['is_empty'] == true;
    final items = _parseList(group['items']);
    final completedCount = group['completed_count'] ?? 0;
    final totalCount = group['total_count'] ?? 0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 8, bottom: 6),
          child: Row(
            children: [
              Icon(icon, size: 16, color: color),
              const SizedBox(width: 6),
              Text(groupName, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: color)),
              const Spacer(),
              if (totalCount > 0)
                Text('$completedCount/$totalCount', style: TextStyle(fontSize: 11, color: Colors.grey[400])),
            ],
          ),
        ),
        if (isEmpty)
          _buildEmptyGroupHint(groupName)
        else
          ...items.map((item) => _buildTodoCard(item, groupType, color)),
      ],
    );
  }

  Widget _buildEmptyGroupHint(String groupName) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.grey[50],
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Icon(Icons.info_outline, size: 16, color: Colors.grey[300]),
          const SizedBox(width: 8),
          Text('$groupName 今日无待办', style: TextStyle(fontSize: 13, color: Colors.grey[400])),
        ],
      ),
    );
  }

  Widget _buildTodoCard(Map<String, dynamic> item, String groupType, Color color) {
    final done = item['is_completed'] == true;
    final name = item['name']?.toString() ?? '';
    String subtitle = '';
    if (groupType == 'medication') {
      final extra = item['extra'] is Map ? item['extra'] as Map : {};
      subtitle = [extra['dosage'] ?? '', extra['time_period'] ?? '', item['remind_time'] ?? '']
          .where((s) => s.toString().isNotEmpty)
          .join(' · ');
    } else if (item['target_value'] != null) {
      subtitle = '目标: ${item['target_value']} ${item['target_unit'] ?? ''}';
    } else if (item['extra'] is Map && (item['extra'] as Map)['plan_name'] != null) {
      subtitle = (item['extra'] as Map)['plan_name'].toString();
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: done ? Border.all(color: color.withOpacity(0.3)) : null,
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: done ? null : () => _handleQuickCheckin(item),
            child: Container(
              width: 24,
              height: 24,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: done ? color : Colors.transparent,
                border: Border.all(color: done ? color : Colors.grey[300]!, width: 2),
              ),
              child: done ? const Icon(Icons.check, size: 14, color: Colors.white) : null,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  style: TextStyle(
                    fontSize: 15,
                    decoration: done ? TextDecoration.lineThrough : null,
                    color: done ? Colors.grey[400] : const Color(0xFF333333),
                  ),
                ),
                if (subtitle.isNotEmpty)
                  Text(subtitle, style: TextStyle(fontSize: 12, color: Colors.grey[400])),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatisticsEntry() {
    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, '/hp-statistics'),
      child: Container(
        width: double.infinity,
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
                color: const Color(0xFF722ED1).withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.insights, color: Color(0xFF722ED1), size: 24),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('打卡统计', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF333333))),
                  const SizedBox(height: 2),
                  Text('查看打卡趋势和成就', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: Colors.grey[400], size: 22),
          ],
        ),
      ),
    );
  }
}
