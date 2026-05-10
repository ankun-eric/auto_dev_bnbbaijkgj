// BhIcon Widget — PRD-442 三端图标统一组件（Flutter 端）
// 不依赖 flutter_svg：使用 Material 兜底图标 + 名称查询；如需真实 SVG，可扩展为 SvgPicture.string(BhIcons.svgMap[name]!)
import 'package:flutter/material.dart';
import 'tokens.g.dart';
import 'icons.g.dart';

class BhIcon extends StatelessWidget {
  final String name;
  final double size;
  final Color? color;
  const BhIcon({
    super.key,
    required this.name,
    this.size = 24,
    this.color,
  });

  IconData _fallback() {
    switch (name) {
      case 'health-report': return Icons.description_outlined;
      case 'heart-rate':    return Icons.favorite_outline;
      case 'medication':    return Icons.medication_outlined;
      case 'family':        return Icons.people_outline;
      case 'bell':          return Icons.notifications_outlined;
      case 'camera':        return Icons.camera_alt_outlined;
      case 'voice':         return Icons.mic_none_outlined;
      case 'chevron-down':  return Icons.keyboard_arrow_down;
      default:              return Icons.help_outline;
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = color ?? BhTokens.colorBrand600;
    return Icon(_fallback(), size: size, color: c);
  }

  static List<String> get availableNames => BhIcons.names;
}
