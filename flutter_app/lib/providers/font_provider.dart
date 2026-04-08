import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class FontProvider extends ChangeNotifier {
  static const String _fontLevelKey = 'font_level';

  /// 0 = 标准, 1 = 大, 2 = 超大
  int _fontLevel = 0;

  double _standardSize = 14.0;
  double _largeSize = 18.0;
  double _xlargeSize = 22.0;

  int get fontLevel => _fontLevel;
  double get standardSize => _standardSize;
  double get largeSize => _largeSize;
  double get xlargeSize => _xlargeSize;

  double get baseFontSize {
    switch (_fontLevel) {
      case 1:
        return _largeSize;
      case 2:
        return _xlargeSize;
      default:
        return _standardSize;
    }
  }

  String get fontLevelLabel {
    switch (_fontLevel) {
      case 1:
        return '大';
      case 2:
        return '超大';
      default:
        return '标准';
    }
  }

  double scaledSize(double base) {
    final ratio = baseFontSize / _standardSize;
    return base * ratio;
  }

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _fontLevel = prefs.getInt(_fontLevelKey) ?? 0;
    notifyListeners();
  }

  void applyConfig(Map<String, dynamic> config) {
    if (config['font_standard_size'] != null) {
      _standardSize = (config['font_standard_size'] as num).toDouble();
    }
    if (config['font_large_size'] != null) {
      _largeSize = (config['font_large_size'] as num).toDouble();
    }
    if (config['font_xlarge_size'] != null) {
      _xlargeSize = (config['font_xlarge_size'] as num).toDouble();
    }
    if (config['font_default_level'] != null && _fontLevel == 0) {
      final raw = config['font_default_level'];
      int defaultLevel;
      if (raw is int) {
        defaultLevel = raw;
      } else {
        const levelMap = {'standard': 0, 'large': 1, 'xlarge': 2};
        defaultLevel = levelMap[raw.toString()] ?? 0;
      }
      if (defaultLevel >= 0 && defaultLevel <= 2) {
        _fontLevel = defaultLevel;
      }
    }
    notifyListeners();
  }

  Future<void> setFontLevel(int level) async {
    if (level < 0 || level > 2) return;
    _fontLevel = level;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_fontLevelKey, level);
  }
}
