import 'package:flutter/material.dart';
import '../../widgets/custom_app_bar.dart';

class HealthPlanScreen extends StatefulWidget {
  const HealthPlanScreen({super.key});

  @override
  State<HealthPlanScreen> createState() => _HealthPlanScreenState();
}

class _HealthPlanScreenState extends State<HealthPlanScreen> {
  final List<Map<String, dynamic>> _plans = [
    {
      'title': '30天健康饮食计划',
      'progress': 0.6,
      'days': 18,
      'totalDays': 30,
      'color': const Color(0xFF52C41A),
    },
    {
      'title': '每日运动打卡',
      'progress': 0.4,
      'days': 12,
      'totalDays': 30,
      'color': const Color(0xFF1890FF),
    },
    {
      'title': '睡眠改善计划',
      'progress': 0.8,
      'days': 24,
      'totalDays': 30,
      'color': const Color(0xFF722ED1),
    },
  ];

  final List<Map<String, dynamic>> _todayTasks = [
    {'title': '早餐：全麦面包+鸡蛋+牛奶', 'time': '07:00', 'done': true, 'icon': Icons.restaurant},
    {'title': '晨跑30分钟', 'time': '07:30', 'done': true, 'icon': Icons.directions_run},
    {'title': '午餐：低脂高蛋白餐', 'time': '12:00', 'done': false, 'icon': Icons.restaurant},
    {'title': '午休20分钟', 'time': '13:00', 'done': false, 'icon': Icons.hotel},
    {'title': '下午茶：水果+坚果', 'time': '15:30', 'done': false, 'icon': Icons.local_cafe},
    {'title': '晚间散步20分钟', 'time': '19:00', 'done': false, 'icon': Icons.directions_walk},
    {'title': '睡前冥想10分钟', 'time': '22:00', 'done': false, 'icon': Icons.self_improvement},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '健康计划'),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('我的计划', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            ...List.generate(_plans.length, (index) {
              final plan = _plans[index];
              return Container(
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
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(plan['title'], style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                        Text(
                          '${plan['days']}/${plan['totalDays']}天',
                          style: TextStyle(fontSize: 13, color: Colors.grey[500]),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: plan['progress'] as double,
                        backgroundColor: (plan['color'] as Color).withOpacity(0.15),
                        valueColor: AlwaysStoppedAnimation(plan['color'] as Color),
                        minHeight: 8,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '完成 ${((plan['progress'] as double) * 100).toInt()}%',
                      style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                    ),
                  ],
                ),
              );
            }),
            const SizedBox(height: 20),
            const Text('今日任务', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            ...List.generate(_todayTasks.length, (index) {
              final task = _todayTasks[index];
              return Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(10),
                  border: (task['done'] as bool)
                      ? Border.all(color: const Color(0xFF52C41A).withOpacity(0.3))
                      : null,
                ),
                child: Row(
                  children: [
                    GestureDetector(
                      onTap: () {
                        setState(() {
                          _todayTasks[index]['done'] = !(task['done'] as bool);
                        });
                      },
                      child: Container(
                        width: 24,
                        height: 24,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: (task['done'] as bool) ? const Color(0xFF52C41A) : Colors.transparent,
                          border: Border.all(
                            color: (task['done'] as bool) ? const Color(0xFF52C41A) : Colors.grey[300]!,
                            width: 2,
                          ),
                        ),
                        child: (task['done'] as bool)
                            ? const Icon(Icons.check, size: 14, color: Colors.white)
                            : null,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Icon(task['icon'] as IconData, color: const Color(0xFF52C41A), size: 20),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        task['title'],
                        style: TextStyle(
                          fontSize: 14,
                          decoration: (task['done'] as bool) ? TextDecoration.lineThrough : null,
                          color: (task['done'] as bool) ? Colors.grey[400] : const Color(0xFF333333),
                        ),
                      ),
                    ),
                    Text(task['time'], style: TextStyle(fontSize: 12, color: Colors.grey[400])),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {},
        backgroundColor: const Color(0xFF52C41A),
        child: const Icon(Icons.add),
      ),
    );
  }
}
