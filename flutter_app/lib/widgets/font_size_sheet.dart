import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/font_provider.dart';

class FontSizeSheet extends StatelessWidget {
  const FontSizeSheet({super.key});

  static void show(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => const FontSizeSheet(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final fontProvider = Provider.of<FontProvider>(context);
    final labels = ['标准', '大字号 👨‍🦳', '超大字号 👴'];

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 16, 24, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.grey[300],
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              '字体大小',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 24),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F7FA),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                '预览文字：宾尼小康AI健康管家',
                style: TextStyle(
                  fontSize: fontProvider.baseFontSize,
                  color: const Color(0xFF333333),
                ),
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: List.generate(3, (i) {
                return Text(
                  labels[i],
                  style: TextStyle(
                    fontSize: 13,
                    color: fontProvider.fontLevel == i
                        ? const Color(0xFF52C41A)
                        : Colors.grey[500],
                    fontWeight: fontProvider.fontLevel == i
                        ? FontWeight.w600
                        : FontWeight.normal,
                  ),
                );
              }),
            ),
            SliderTheme(
              data: SliderTheme.of(context).copyWith(
                activeTrackColor: const Color(0xFF52C41A),
                inactiveTrackColor: Colors.grey[200],
                thumbColor: const Color(0xFF52C41A),
                overlayColor: const Color(0xFF52C41A).withOpacity(0.12),
                trackHeight: 4,
              ),
              child: Slider(
                value: fontProvider.fontLevel.toDouble(),
                min: 0,
                max: 2,
                divisions: 2,
                onChanged: (v) => fontProvider.setFontLevel(v.round()),
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}
