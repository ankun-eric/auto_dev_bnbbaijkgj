import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class HealthPlanScreen extends StatefulWidget {
  const HealthPlanScreen({super.key});

  @override
  State<HealthPlanScreen> createState() => _HealthPlanScreenState();
}

class _HealthPlanScreenState extends State<HealthPlanScreen> {
  final ApiService _apiService = ApiService();
  bool _loading = true;

  List<Map<String, dynamic>> _todayMedications = [];
  List<Map<String, dynamic>> _todayCheckins = [];
  List<Map<String, dynamic>> _todayPlanTasks = [];

  bool _aiGenerating = false;

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
          _todayMedications = _parseList(data['medications']);
          _todayCheckins = _parseList(data['checkin_items']);
          _todayPlanTasks = _parseList(data['plan_tasks']);
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

  Future<void> _handleCheckin(String type, Map<String, dynamic> item) async {
    try {
      final id = item['id'] as int;
      if (type == 'medication') {
        await _apiService.checkinMedication(id);
      } else if (type == 'checkin') {
        await _apiService.checkinCheckinItem(id, isCompleted: true);
      } else if (type == 'plan_task') {
        final planId = item['plan_id'] as int;
        await _apiService.checkinUserPlanTask(planId, id);
      }
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
              onRefresh: _loadTodayTodos,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildAiGenerateButton(),
                    const SizedBox(height: 20),
                    _buildCategoryCards(),
                    const SizedBox(height: 20),
                    _buildTodaySection(),
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
      {
        'icon': Icons.medication_rounded,
        'title': '用药提醒',
        'subtitle': '按时服药，健康管理',
        'color': const Color(0xFFFA8C16),
        'route': '/hp-medications',
      },
      {
        'icon': Icons.check_circle_outline_rounded,
        'title': '健康打卡',
        'subtitle': '每日打卡，养成习惯',
        'color': const Color(0xFF52C41A),
        'route': '/hp-checkins',
      },
      {
        'icon': Icons.flag_rounded,
        'title': '自定义计划',
        'subtitle': '个性定制，目标达成',
        'color': const Color(0xFF1890FF),
        'route': '/hp-template-categories',
      },
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('健康管理', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
        const SizedBox(height: 12),
        ...categories.map((cat) {
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
                        Text(cat['title'] as String, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF333333))),
                        const SizedBox(height: 2),
                        Text(cat['subtitle'] as String, style: TextStyle(fontSize: 13, color: Colors.grey[500])),
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
    final total = _todayMedications.length + _todayCheckins.length + _todayPlanTasks.length;
    final doneCount = _todayMedications.where((m) => m['is_checked'] == true).length +
        _todayCheckins.where((c) => c['is_checked'] == true).length +
        _todayPlanTasks.where((t) => t['is_checked'] == true).length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('今日待办', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
            if (total > 0)
              Text('$doneCount/$total 已完成', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
          ],
        ),
        const SizedBox(height: 12),
        if (total == 0)
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
        else ...[
          if (_todayMedications.isNotEmpty) ...[
            _buildGroupLabel('用药提醒', Icons.medication, const Color(0xFFFA8C16)),
            ..._todayMedications.map((m) => _buildTodoCard(
              title: m['medicine_name']?.toString() ?? '',
              subtitle: '${m['dosage'] ?? ''} · ${m['time_period'] ?? ''} ${m['remind_time'] ?? ''}',
              done: m['is_checked'] == true,
              color: const Color(0xFFFA8C16),
              onCheck: () => _handleCheckin('medication', m),
            )),
          ],
          if (_todayCheckins.isNotEmpty) ...[
            _buildGroupLabel('健康打卡', Icons.check_circle_outline, const Color(0xFF52C41A)),
            ..._todayCheckins.map((c) => _buildTodoCard(
              title: c['name']?.toString() ?? '',
              subtitle: c['target_value'] != null ? '目标: ${c['target_value']} ${c['target_unit'] ?? ''}' : '',
              done: c['is_checked'] == true,
              color: const Color(0xFF52C41A),
              onCheck: () => _handleCheckin('checkin', c),
            )),
          ],
          if (_todayPlanTasks.isNotEmpty) ...[
            _buildGroupLabel('计划任务', Icons.flag_outlined, const Color(0xFF1890FF)),
            ..._todayPlanTasks.map((t) => _buildTodoCard(
              title: t['task_name']?.toString() ?? t['name']?.toString() ?? '',
              subtitle: t['plan_name']?.toString() ?? '',
              done: t['is_checked'] == true,
              color: const Color(0xFF1890FF),
              onCheck: () => _handleCheckin('plan_task', t),
            )),
          ],
        ],
      ],
    );
  }

  Widget _buildGroupLabel(String label, IconData icon, Color color) {
    return Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 6),
      child: Row(
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 6),
          Text(label, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: color)),
        ],
      ),
    );
  }

  Widget _buildTodoCard({
    required String title,
    required String subtitle,
    required bool done,
    required Color color,
    required VoidCallback onCheck,
  }) {
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
            onTap: done ? null : onCheck,
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
                  title,
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
}
