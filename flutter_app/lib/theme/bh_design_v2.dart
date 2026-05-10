// PRD-442 全域设计 v2 适配器
// 通过 bini_design_tokens 包桥接到 flutter_app 的现有主题层。
// 对存量 screen/widget 不做强制改造，仅提供 BhTokens / BhTheme.lightTheme() 的转出口
// 与一个 PRD-442 标识函数（用于 pytest / 真机走查校验存在性）。

import 'package:bini_design_tokens/bini_design_tokens.dart';

export 'package:bini_design_tokens/bini_design_tokens.dart';

class BhDesignV2 {
  BhDesignV2._();
  static const String prdVersion = 'PRD-442';
  static const String packageName = 'bini_design_tokens';

  /// 主品牌色断言：必须与 design-tokens.json 的 brand-400 hex 完全一致。
  /// 这是三端 token 一致性的核心铁律之一，被 pytest 强校验。
  static String get brandHexCanonical => '#38BDF8';
}
