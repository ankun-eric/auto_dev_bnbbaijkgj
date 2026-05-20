// [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] AI 追问 chips 行（AI 侧）
import 'package:flutter/material.dart';

class FollowupChipsRow extends StatelessWidget {
  final List<Map<String, dynamic>> chips;
  final bool disabled;
  final void Function(Map<String, dynamic> chip)? onTapChip;

  const FollowupChipsRow({
    super.key,
    required this.chips,
    this.disabled = false,
    this.onTapChip,
  });

  @override
  Widget build(BuildContext context) {
    if (chips.isEmpty) return const SizedBox.shrink();
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: chips.map((chip) {
        final label = (chip['label'] ?? '').toString();
        return GestureDetector(
          onTap: disabled ? null : () => onTapChip?.call(chip),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            decoration: BoxDecoration(
              color: disabled ? const Color(0xFFF1F5F9) : const Color(0xFFEFF6FF),
              border: Border.all(
                color: disabled ? const Color(0xFFE2E8F0) : const Color(0xFFBAE6FD),
              ),
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              label,
              style: TextStyle(
                fontSize: 13,
                color: disabled ? const Color(0xFF94A3B8) : const Color(0xFF0EA5E9),
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        );
      }).toList(),
    );
  }
}
