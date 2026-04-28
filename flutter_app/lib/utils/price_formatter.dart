/// 格式化价格显示：去掉末尾多余的零
/// 19.00 → "19"，19.10 → "19.1"，19.12 → "19.12"
///
/// 先四舍五入到 2 位小数以消除浮点运算误差（如 53.730000000000004 → 53.73），
/// 再去掉末尾零。
String formatPrice(dynamic value) {
  if (value == null) return '0';
  final num numValue =
      value is num ? value : num.tryParse(value.toString()) ?? 0;
  final double rounded =
      (numValue * 100).round() / 100;
  if (rounded == rounded.toInt()) {
    return rounded.toInt().toString();
  }
  String str = rounded.toStringAsFixed(2);
  str = str.replaceAll(RegExp(r'0+$'), '');
  str = str.replaceAll(RegExp(r'\.$'), '');
  return str;
}
