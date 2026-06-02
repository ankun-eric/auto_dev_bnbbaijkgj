// [PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02] 健康计划落地页（重做版）
// 直接是打卡首页：顶部蓝紫色横幅 + 总览卡 + 我的计划列表 + 右下角浮动「+」
import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class HealthPlanScreen extends StatefulWidget {
  const HealthPlanScreen({super.key});

  @override
  State<HealthPlanScreen> createState() => _HealthPlanScreenState();
}

class _HealthPlanScreenState extends State<HealthPlanScreen> {
  final ApiService _api = ApiService();
  bool _loading = true;
  List<Map<String, dynamic>> _items = [];
  Map<String, dynamic> _overview = {
    'active_count': 0,
    'today_done_count': 0,
    'week_completion_rate': 0,
  };

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final futures = await Future.wait([
        _api.getCheckinItems(),
        _api.getCheckinOverview(),
      ]);
      final list = futures[0].data is Map ? (futures[0].data['items'] as List?) ?? [] : [];
      final ov = futures[1].data is Map ? Map<String, dynamic>.from(futures[1].data as Map) : {};
      if (!mounted) return;
      setState(() {
        _items = list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
        _overview = {
          'active_count': ov['active_count'] ?? 0,
          'today_done_count': ov['today_done_count'] ?? 0,
          'week_completion_rate': ov['week_completion_rate'] ?? 0,
        };
      });
    } catch (_) {
      // ignore
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _freqLabel(Map<String, dynamic> it) {
    final f = it['repeat_frequency'];
    final w = it['weekly_target_count'];
    if (f == 'weekly' && w != null) return '每周 $w 次';
    return '每天';
  }

  String _periodLabel(Map<String, dynamic> it) {
    final s = it['start_date'];
    final e = it['end_date'];
    if (s == null && e == null) return '长期';
    return '${s ?? '今起'} ~ ${e ?? '不限期'}';
  }

  Future<void> _doCheckin(Map<String, dynamic> it) async {
    if (it['today_completed'] == true) return;
    try {
      await _api.checkinCheckinItem(it['id'] as int);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('打卡成功'), backgroundColor: Color(0xFF6366F1)),
        );
      }
      _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('打卡失败'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _doDelete(Map<String, dynamic> it) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除计划'),
        content: const Text('确定删除该计划吗？该计划的打卡记录也会一并清除。'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('删除', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await _api.deleteCheckinItem(it['id'] as int);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('已删除')));
      }
      _load();
    } catch (_) {}
  }

  void _showMoreMenu(Map<String, dynamic> it) {
    showModalBottomSheet(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.edit, color: Color(0xFF6366F1)),
              title: const Text('编辑'),
              onTap: () {
                Navigator.pop(ctx);
                Navigator.pushNamed(context, '/hp-checkin-edit', arguments: it['id'])
                    .then((_) => _load());
              },
            ),
            ListTile(
              leading: const Icon(Icons.delete_outline, color: Colors.red),
              title: const Text('删除', style: TextStyle(color: Colors.red)),
              onTap: () {
                Navigator.pop(ctx);
                _doDelete(it);
              },
            ),
            ListTile(
              title: const Center(child: Text('取消')),
              onTap: () => Navigator.pop(ctx),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F5F7),
      appBar: AppBar(
        title: const Text('健康计划'),
        backgroundColor: const Color(0xFF52C41A),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: EdgeInsets.zero,
                children: [
                  // 顶部蓝紫色横幅
                  Container(
                    padding: const EdgeInsets.fromLTRB(16, 24, 16, 36),
                    decoration: const BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
                      ),
                    ),
                    child: const Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('健康计划',
                            style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
                        SizedBox(height: 4),
                        Text('每天一勾，养成更健康的自己',
                            style: TextStyle(color: Colors.white70, fontSize: 12)),
                      ],
                    ),
                  ),
                  // 总览卡
                  Transform.translate(
                    offset: const Offset(0, -18),
                    child: Container(
                      margin: const EdgeInsets.symmetric(horizontal: 16),
                      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(14),
                        boxShadow: [
                          BoxShadow(
                              color: const Color(0xFF6366F1).withOpacity(0.1),
                              blurRadius: 12,
                              offset: const Offset(0, 4))
                        ],
                      ),
                      child: Row(
                        children: [
                          _statCol('${_overview['active_count']}', '进行中计划', const Color(0xFF6366F1)),
                          _divider(),
                          _statCol('${_overview['today_done_count']}', '今天已打卡', const Color(0xFF8B5CF6)),
                          _divider(),
                          _statCol('${_overview['week_completion_rate']}%', '本周完成率', const Color(0xFFA855F7)),
                        ],
                      ),
                    ),
                  ),
                  // 标题 + 查看成果
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('我的计划',
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                        GestureDetector(
                          onTap: () => Navigator.pushNamed(context, '/hp-checkin-result')
                              .then((_) => _load()),
                          child: const Text('查看成果 ›',
                              style: TextStyle(fontSize: 12, color: Color(0xFF6366F1))),
                        ),
                      ],
                    ),
                  ),
                  // 列表
                  if (_items.isEmpty)
                    _emptyState()
                  else
                    ..._items.map(_planCard).toList(),
                  const SizedBox(height: 80),
                ],
              ),
            ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFF6366F1),
        onPressed: () {
          Navigator.pushNamed(context, '/hp-checkin-edit').then((_) => _load());
        },
        child: const Icon(Icons.add),
      ),
    );
  }

  Widget _statCol(String num, String label, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text(num, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: color)),
          const SizedBox(height: 4),
          Text(label, style: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))),
        ],
      ),
    );
  }

  Widget _divider() => Container(width: 1, height: 32, color: const Color(0xFFF0F0F0));

  Widget _emptyState() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 16),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
      child: Column(
        children: [
          const Text('✅', style: TextStyle(fontSize: 36)),
          const SizedBox(height: 12),
          const Text('还没有计划，创建一个开始打卡吧',
              style: TextStyle(color: Color(0xFF9CA3AF), fontSize: 14)),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () => Navigator.pushNamed(context, '/hp-checkin-edit').then((_) => _load()),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF6366F1),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            child: const Text('新建计划'),
          ),
        ],
      ),
    );
  }

  Widget _planCard(Map<String, dynamic> it) {
    final done = it['today_completed'] == true;
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(it['name'] ?? '未命名',
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Text('${_freqLabel(it)} · ${_periodLabel(it)}',
                    style: const TextStyle(fontSize: 11, color: Color(0xFF9CA3AF))),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.more_horiz, color: Color(0xFF9CA3AF)),
            onPressed: () => _showMoreMenu(it),
          ),
          SizedBox(
            height: 32,
            child: ElevatedButton(
              onPressed: done ? null : () => _doCheckin(it),
              style: ElevatedButton.styleFrom(
                backgroundColor: done ? const Color(0xFFE5E7EB) : const Color(0xFF6366F1),
                disabledBackgroundColor: const Color(0xFFE5E7EB),
                foregroundColor: done ? const Color(0xFF9CA3AF) : Colors.white,
                disabledForegroundColor: const Color(0xFF9CA3AF),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
                padding: const EdgeInsets.symmetric(horizontal: 16),
                elevation: 0,
              ),
              child: Text(done ? '已打卡' : '打卡', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
            ),
          ),
        ],
      ),
    );
  }
}
