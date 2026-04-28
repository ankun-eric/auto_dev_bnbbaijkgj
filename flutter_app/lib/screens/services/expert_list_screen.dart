import 'package:flutter/material.dart';
import '../../models/expert.dart';
import '../../utils/price_formatter.dart';
import '../../widgets/custom_app_bar.dart';

class ExpertListScreen extends StatefulWidget {
  const ExpertListScreen({super.key});

  @override
  State<ExpertListScreen> createState() => _ExpertListScreenState();
}

class _ExpertListScreenState extends State<ExpertListScreen> {
  final List<Expert> _experts = [
    Expert(id: '1', name: '张明华', title: '主任医师', hospital: '北京协和医院', department: '内科', specialty: '心血管疾病', rating: 4.9, consultCount: 2580, price: 299, tags: ['心血管', '高血压']),
    Expert(id: '2', name: '李芳', title: '副主任医师', hospital: '上海瑞金医院', department: '中医科', specialty: '中医养生', rating: 4.8, consultCount: 1860, price: 199, tags: ['中医', '养生']),
    Expert(id: '3', name: '王建国', title: '主任医师', hospital: '广州中山医院', department: '骨科', specialty: '骨关节疾病', rating: 4.9, consultCount: 3200, price: 259, tags: ['骨科', '康复']),
    Expert(id: '4', name: '刘婷', title: '主治医师', hospital: '深圳人民医院', department: '皮肤科', specialty: '皮肤病', rating: 4.7, consultCount: 1420, price: 149, tags: ['皮肤', '过敏']),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '专家列表'),
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _experts.length,
        itemBuilder: (context, index) {
          final expert = _experts[index];
          return GestureDetector(
            onTap: () => Navigator.pushNamed(context, '/expert-detail', arguments: expert.id),
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
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 60,
                    height: 60,
                    decoration: BoxDecoration(
                      color: const Color(0xFF52C41A).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Icon(Icons.person, color: Color(0xFF52C41A), size: 32),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(expert.name, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: const Color(0xFF1890FF).withOpacity(0.1),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(expert.title ?? '', style: const TextStyle(fontSize: 11, color: Color(0xFF1890FF))),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${expert.hospital} · ${expert.department}',
                          style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                        ),
                        const SizedBox(height: 6),
                        Row(
                          children: [
                            ...expert.tags.map((tag) => Container(
                                  margin: const EdgeInsets.only(right: 6),
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF52C41A).withOpacity(0.08),
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: Text(tag, style: const TextStyle(fontSize: 11, color: Color(0xFF52C41A))),
                                )),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            Icon(Icons.star, size: 16, color: Colors.amber[700]),
                            const SizedBox(width: 2),
                            Text('${expert.rating}', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                            const SizedBox(width: 12),
                            Text('接诊${expert.consultCount}次', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                            const Spacer(),
                            Text(
                              '¥${formatPrice(expert.price)}',
                              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFFFF6B35)),
                            ),
                            Text('/次', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
