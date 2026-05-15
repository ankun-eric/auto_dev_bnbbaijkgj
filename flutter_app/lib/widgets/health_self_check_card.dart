// [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 自查卡片气泡
import 'package:flutter/material.dart';

class HealthSelfCheckCard extends StatelessWidget {
  final Map<String, dynamic> payload;
  final VoidCallback? onReopen;

  const HealthSelfCheckCard({super.key, required this.payload, this.onReopen});

  @override
  Widget build(BuildContext context) {
    final archiveName = payload['archive_name']?.toString();
    final age = payload['archive_age'];
    final gender = payload['archive_gender']?.toString();
    final bodyPart = (payload['body_part'] is Map)
        ? Map<String, dynamic>.from(payload['body_part'] as Map)
        : <String, dynamic>{};
    final symptoms =
        (payload['symptoms'] as List?)?.map((e) => e.toString()).toList() ?? [];
    final duration = payload['duration']?.toString() ?? '';

    return Container(
      constraints: const BoxConstraints(maxWidth: 320),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFE6F4FF),
        border: Border.all(color: const Color(0xFF91CAFF)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('🩺 健康自查',
                  style: TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF1677FF))),
              if (onReopen != null)
                GestureDetector(
                  onTap: onReopen,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      border: Border.all(color: const Color(0xFF91CAFF)),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text('重新自查',
                        style: TextStyle(fontSize: 11, color: Color(0xFF1677FF))),
                  ),
                ),
            ],
          ),
          if (archiveName != null && archiveName.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                '咨询人：$archiveName${age != null ? "（${age}岁" : ""}${gender != null && gender.isNotEmpty ? "·$gender" : ""}${age != null ? "）" : ""}',
                style: const TextStyle(fontSize: 12, color: Color(0xFF666666)),
              ),
            ),
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 6),
            child: Divider(height: 1, color: Color(0xFF91CAFF)),
          ),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('部位：', style: TextStyle(color: Color(0xFF888888), fontSize: 13)),
              Text((bodyPart['icon'] as String?)?.isNotEmpty == true ? bodyPart['icon'] : '🧩',
                  style: const TextStyle(fontSize: 14)),
              const SizedBox(width: 4),
              Text(bodyPart['name']?.toString() ?? '-',
                  style: const TextStyle(fontSize: 13)),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('症状：', style: TextStyle(color: Color(0xFF888888), fontSize: 13)),
              Expanded(
                child: Wrap(
                  spacing: 4,
                  runSpacing: 4,
                  children: symptoms
                      .map((s) => Container(
                            padding:
                                const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              border: Border.all(color: const Color(0xFF91CAFF)),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Text(s,
                                style: const TextStyle(
                                    fontSize: 12, color: Color(0xFF1677FF))),
                          ))
                      .toList(),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              const Text('持续：', style: TextStyle(color: Color(0xFF888888), fontSize: 13)),
              Text(duration, style: const TextStyle(fontSize: 13)),
            ],
          ),
        ],
      ),
    );
  }
}
