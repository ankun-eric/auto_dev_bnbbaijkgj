import 'package:flutter/material.dart';
import '../../widgets/custom_app_bar.dart';

class ExpertDetailScreen extends StatefulWidget {
  const ExpertDetailScreen({super.key});

  @override
  State<ExpertDetailScreen> createState() => _ExpertDetailScreenState();
}

class _ExpertDetailScreenState extends State<ExpertDetailScreen> {
  int _selectedDateIndex = 0;
  int _selectedTimeIndex = -1;

  final List<Map<String, String>> _dates = [
    {'date': '03/27', 'weekday': '今天'},
    {'date': '03/28', 'weekday': '周六'},
    {'date': '03/29', 'weekday': '周日'},
    {'date': '03/30', 'weekday': '周一'},
    {'date': '03/31', 'weekday': '周二'},
  ];

  final List<String> _timeSlots = ['09:00', '09:30', '10:00', '10:30', '14:00', '14:30', '15:00', '15:30'];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '专家详情'),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              color: Colors.white,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 72,
                    height: 72,
                    decoration: BoxDecoration(
                      color: const Color(0xFF52C41A).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: const Icon(Icons.person, color: Color(0xFF52C41A), size: 40),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(
                          children: [
                            Text('张明华', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                            SizedBox(width: 8),
                            Text('主任医师', style: TextStyle(fontSize: 13, color: Color(0xFF1890FF))),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text('北京协和医院 · 内科', style: TextStyle(color: Colors.grey[600])),
                        const SizedBox(height: 6),
                        Row(
                          children: [
                            Icon(Icons.star, size: 16, color: Colors.amber[700]),
                            const Text(' 4.9', style: TextStyle(fontWeight: FontWeight.w600)),
                            const SizedBox(width: 16),
                            Text('接诊2580次', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(16),
              color: Colors.white,
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('个人简介', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  SizedBox(height: 8),
                  Text(
                    '从事心血管内科临床工作20余年，擅长高血压、冠心病、心力衰竭等心血管疾病的诊治。'
                    '在心血管介入诊疗方面有丰富经验。曾在国内外核心期刊发表论文50余篇。',
                    style: TextStyle(fontSize: 14, height: 1.6, color: Color(0xFF666666)),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(16),
              color: Colors.white,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('预约排班', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 12),
                  SizedBox(
                    height: 60,
                    child: ListView.builder(
                      scrollDirection: Axis.horizontal,
                      itemCount: _dates.length,
                      itemBuilder: (context, index) {
                        final isSelected = _selectedDateIndex == index;
                        return GestureDetector(
                          onTap: () => setState(() {
                            _selectedDateIndex = index;
                            _selectedTimeIndex = -1;
                          }),
                          child: Container(
                            width: 60,
                            margin: const EdgeInsets.only(right: 10),
                            decoration: BoxDecoration(
                              color: isSelected ? const Color(0xFF52C41A) : const Color(0xFFF5F7FA),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Text(
                                  _dates[index]['weekday']!,
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: isSelected ? Colors.white : Colors.grey[600],
                                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  _dates[index]['date']!,
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: isSelected ? Colors.white70 : Colors.grey[500],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: List.generate(_timeSlots.length, (index) {
                      final isSelected = _selectedTimeIndex == index;
                      return GestureDetector(
                        onTap: () => setState(() => _selectedTimeIndex = index),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                          decoration: BoxDecoration(
                            color: isSelected ? const Color(0xFF52C41A) : Colors.white,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: isSelected ? const Color(0xFF52C41A) : Colors.grey[300]!,
                            ),
                          ),
                          child: Text(
                            _timeSlots[index],
                            style: TextStyle(
                              color: isSelected ? Colors.white : Colors.grey[700],
                              fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                            ),
                          ),
                        ),
                      );
                    }),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 80),
          ],
        ),
      ),
      bottomNavigationBar: Container(
        padding: EdgeInsets.only(
          left: 16,
          right: 16,
          top: 10,
          bottom: MediaQuery.of(context).padding.bottom + 10,
        ),
        decoration: const BoxDecoration(
          color: Colors.white,
          boxShadow: [BoxShadow(color: Colors.black12, blurRadius: 6, offset: Offset(0, -2))],
        ),
        child: Row(
          children: [
            const Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('咨询费用', style: TextStyle(fontSize: 12, color: Color(0xFF999999))),
                SizedBox(height: 2),
                Text('¥299/次', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFFFF6B35))),
              ],
            ),
            const SizedBox(width: 24),
            Expanded(
              child: SizedBox(
                height: 48,
                child: ElevatedButton(
                  onPressed: _selectedTimeIndex >= 0 ? () {} : null,
                  child: const Text('立即预约'),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
