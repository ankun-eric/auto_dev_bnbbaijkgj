// ============================================================
// bini-health · 菜单模式 PRD-442 · 晴空诊室风格
// Flutter Design Tokens v1.0 (2026-05-10)
//
// 与 H5（design-tokens.css）和小程序（menu-mode-tokens.wxss）
// 三端共用同一套晴空诊室色板。
//
// 使用：
//   import 'package:bini_health/theme/menu_mode_theme.dart';
//   final colors = MenuModeColors;
//   final spacing = MenuModeSpacing;
// ============================================================

import 'package:flutter/material.dart';

/// PRD-442 晴空诊室 11 级天蓝色阶（与 H5/小程序完全一致）
class MenuModeColors {
  static const sky50  = Color(0xFFF0F9FF);
  static const sky100 = Color(0xFFE0F2FE);
  static const sky200 = Color(0xFFBAE6FD);
  static const sky300 = Color(0xFF7DD3FC);
  static const sky400 = Color(0xFF38BDF8); // 主色 · 病历卡左竖线
  static const sky500 = Color(0xFF0EA5E9);
  static const sky600 = Color(0xFF0284C7);
  static const sky700 = Color(0xFF0369A1);
  static const sky800 = Color(0xFF075985); // Hero 深蓝
  static const sky900 = Color(0xFF0C4A6E);
  static const sky950 = Color(0xFF082F49);

  // 语义辅助色（严格控量）
  static const success = Color(0xFF22C55E);
  static const danger  = Color(0xFFEF4444);
  static const member  = Color(0xFFF59E0B);

  // 文字
  static const text1 = Color(0xFF0F172A);
  static const text2 = Color(0xFF475569);
  static const text3 = Color(0xFF94A3B8);

  // 背景
  static const bgBase = Color(0xFFFFFFFF);
  static const bgSoft = Color(0xFFF8FAFC);
  static const borderLight = Color(0xFFE2E8F0);
  static const borderDivider = Color(0xFFF1F5F9);
}

/// PRD-442 字号 8 级（中老年友好 · 14px 起）
class MenuModeFontSize {
  static const fs12 = 12.0;
  static const fs14 = 14.0; // 正文最小
  static const fs16 = 16.0;
  static const fs18 = 18.0;
  static const fs20 = 20.0;
  static const fs24 = 24.0;
  static const fs30 = 30.0;
  static const fs36 = 36.0; // 关键指标（健康评分）
}

/// PRD-442 间距 8 级
class MenuModeSpacing {
  static const sp1 = 4.0;
  static const sp2 = 8.0;
  static const sp3 = 12.0;
  static const sp4 = 16.0;
  static const sp5 = 20.0;
  static const sp6 = 24.0;
  static const sp8 = 32.0;
  static const sp10 = 40.0;
}

/// PRD-442 圆角 5 级
class MenuModeRadius {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 16.0;
  static const xl = 24.0; // 登录卡 / 主卡片专用
}

/// PRD-442 阴影 4 级（统一天蓝色阴影，禁止纯黑）
class MenuModeShadow {
  static const List<BoxShadow> shadow1 = [
    BoxShadow(color: Color(0x1438BDF8), offset: Offset(0, 1), blurRadius: 2),
  ];
  static const List<BoxShadow> shadow2 = [
    BoxShadow(color: Color(0x1A38BDF8), offset: Offset(0, 4), blurRadius: 12),
  ];
  static const List<BoxShadow> shadow3 = [
    BoxShadow(color: Color(0x1F38BDF8), offset: Offset(0, 8), blurRadius: 24),
  ];
  static const List<BoxShadow> shadow4 = [
    BoxShadow(color: Color(0x2938BDF8), offset: Offset(0, 16), blurRadius: 40),
  ];
}

/// PRD-442 渐变三层级
class MenuModeGradient {
  /// A1 顶栏 · 三层级渐变最浅级
  static const topbarA1 = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFF0F9FF), Color(0xFFBAE6FD)],
  );

  /// 主按钮 · 三层级渐变中段
  static const btnPrimary = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF38BDF8), Color(0xFF0284C7)],
  );

  /// Hero · 三层级渐变最深
  static const heroDeep = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF075985), Color(0xFF0C4A6E)],
  );

  /// 登录页全屏背景
  static const loginBg = LinearGradient(
    begin: Alignment(-0.3, -1),
    end: Alignment(0.3, 1),
    colors: [Color(0xFFE0F2FE), Color(0xFFBAE6FD), Color(0xFF7DD3FC)],
    stops: [0.0, 0.5, 1.0],
  );
}

/// PRD-442 动效时长
class MenuModeDuration {
  static const fast = Duration(milliseconds: 180);
  static const base = Duration(milliseconds: 240);
  static const slow = Duration(milliseconds: 360);
}

/// 构建符合 PRD-442 晴空诊室风格的 ThemeData
ThemeData buildMenuModeTheme({Brightness brightness = Brightness.light}) {
  final base = ThemeData(brightness: brightness);

  return base.copyWith(
    primaryColor: MenuModeColors.sky400,
    scaffoldBackgroundColor: MenuModeColors.bgSoft,
    colorScheme: ColorScheme.fromSeed(
      seedColor: MenuModeColors.sky500,
      brightness: brightness,
      primary: MenuModeColors.sky500,
      secondary: MenuModeColors.sky400,
      error: MenuModeColors.danger,
      surface: MenuModeColors.bgBase,
    ),
    textTheme: const TextTheme(
      bodySmall:   TextStyle(fontSize: MenuModeFontSize.fs12, color: MenuModeColors.text3, letterSpacing: 0.28),
      bodyMedium:  TextStyle(fontSize: MenuModeFontSize.fs14, color: MenuModeColors.text1, letterSpacing: 0.28),
      bodyLarge:   TextStyle(fontSize: MenuModeFontSize.fs16, color: MenuModeColors.text1, letterSpacing: 0.32),
      titleSmall:  TextStyle(fontSize: MenuModeFontSize.fs16, color: MenuModeColors.text1, fontWeight: FontWeight.w600),
      titleMedium: TextStyle(fontSize: MenuModeFontSize.fs18, color: MenuModeColors.text1, fontWeight: FontWeight.w600),
      titleLarge:  TextStyle(fontSize: MenuModeFontSize.fs20, color: MenuModeColors.text1, fontWeight: FontWeight.w700),
      headlineSmall:  TextStyle(fontSize: MenuModeFontSize.fs24, color: MenuModeColors.text1, fontWeight: FontWeight.w700),
      headlineMedium: TextStyle(fontSize: MenuModeFontSize.fs30, color: MenuModeColors.text1, fontWeight: FontWeight.w700),
      headlineLarge:  TextStyle(fontSize: MenuModeFontSize.fs36, color: MenuModeColors.text1, fontWeight: FontWeight.w700),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: MenuModeColors.bgBase,
      foregroundColor: MenuModeColors.text1,
      elevation: 0,
      centerTitle: true,
      titleTextStyle: TextStyle(
        fontSize: MenuModeFontSize.fs18,
        color: MenuModeColors.text1,
        fontWeight: FontWeight.w600,
      ),
    ),
    cardTheme: const CardThemeData(
      color: MenuModeColors.bgBase,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.all(Radius.circular(MenuModeRadius.lg)),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        minimumSize: const Size(double.infinity, 48),
        backgroundColor: MenuModeColors.sky500,
        foregroundColor: Colors.white,
        elevation: 0,
        textStyle: const TextStyle(fontSize: MenuModeFontSize.fs16, fontWeight: FontWeight.w600, letterSpacing: 0.32),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(MenuModeRadius.md)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(double.infinity, 48),
        foregroundColor: MenuModeColors.sky700,
        side: const BorderSide(color: MenuModeColors.sky300),
        textStyle: const TextStyle(fontSize: MenuModeFontSize.fs16, fontWeight: FontWeight.w600, letterSpacing: 0.32),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(MenuModeRadius.md)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: MenuModeColors.bgSoft,
      contentPadding: const EdgeInsets.symmetric(horizontal: MenuModeSpacing.sp4, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(MenuModeRadius.md),
        borderSide: const BorderSide(color: MenuModeColors.borderLight),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(MenuModeRadius.md),
        borderSide: const BorderSide(color: MenuModeColors.borderLight),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(MenuModeRadius.md),
        borderSide: const BorderSide(color: MenuModeColors.sky400, width: 2),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(MenuModeRadius.md),
        borderSide: const BorderSide(color: MenuModeColors.danger),
      ),
      hintStyle: const TextStyle(color: MenuModeColors.text3, fontSize: MenuModeFontSize.fs14),
    ),
    dividerTheme: const DividerThemeData(color: MenuModeColors.borderDivider, space: 1, thickness: 1),
  );
}

// ============================================================
// 4. 业务组件 Widget（简化版）
// ============================================================

/// 病历卡：白底 + 左 3px sky-400 竖线 + shadow-2（核心铁律）
class MenuMedicalCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry? padding;
  const MenuMedicalCard({super.key, required this.child, this.padding});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: MenuModeColors.bgBase,
        borderRadius: BorderRadius.circular(MenuModeRadius.lg),
        boxShadow: MenuModeShadow.shadow2,
      ),
      child: Stack(
        children: [
          Positioned(
            left: 0, top: 0, bottom: 0,
            child: Container(
              width: 3,
              decoration: BoxDecoration(
                color: MenuModeColors.sky400,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(MenuModeRadius.lg),
                  bottomLeft: Radius.circular(MenuModeRadius.lg),
                ),
              ),
            ),
          ),
          Padding(
            padding: padding ?? const EdgeInsets.fromLTRB(20, 16, 16, 16),
            child: child,
          ),
        ],
      ),
    );
  }
}

/// Hero 卡（深蓝渐变）
class MenuHeroCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final Gradient? gradient;
  const MenuHeroCard({super.key, required this.child, this.padding, this.gradient});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding ?? const EdgeInsets.all(MenuModeSpacing.sp6),
      decoration: BoxDecoration(
        gradient: gradient ?? MenuModeGradient.heroDeep,
        borderRadius: BorderRadius.circular(MenuModeRadius.xl),
        boxShadow: MenuModeShadow.shadow3,
      ),
      child: DefaultTextStyle.merge(
        style: const TextStyle(color: Colors.white),
        child: child,
      ),
    );
  }
}

/// 主按钮（高 48）
class MenuPrimaryButton extends StatelessWidget {
  final String text;
  final VoidCallback? onPressed;
  final bool fullWidth;
  const MenuPrimaryButton({
    super.key,
    required this.text,
    this.onPressed,
    this.fullWidth = true,
  });

  @override
  Widget build(BuildContext context) {
    final btn = Container(
      height: 48,
      decoration: BoxDecoration(
        gradient: onPressed == null
            ? const LinearGradient(colors: [Color(0xFFE2E8F0), Color(0xFFE2E8F0)])
            : MenuModeGradient.btnPrimary,
        borderRadius: BorderRadius.circular(MenuModeRadius.md),
        boxShadow: onPressed == null ? null : MenuModeShadow.shadow2,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(MenuModeRadius.md),
          onTap: onPressed,
          child: Center(
            child: Text(
              text,
              style: TextStyle(
                color: onPressed == null ? MenuModeColors.text3 : Colors.white,
                fontSize: MenuModeFontSize.fs16,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.32,
              ),
            ),
          ),
        ),
      ),
    );
    return fullWidth ? SizedBox(width: double.infinity, child: btn) : btn;
  }
}

/// 家人 Chip
class MenuFamilyChip extends StatelessWidget {
  final String label;
  final bool active;
  final VoidCallback? onTap;
  const MenuFamilyChip({
    super.key,
    required this.label,
    this.active = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 32,
        padding: const EdgeInsets.symmetric(horizontal: MenuModeSpacing.sp3),
        decoration: BoxDecoration(
          color: active ? MenuModeColors.sky400 : MenuModeColors.bgBase,
          border: Border.all(
            color: active ? MenuModeColors.sky400 : MenuModeColors.borderLight,
          ),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Center(
          child: Text(
            label,
            style: TextStyle(
              fontSize: MenuModeFontSize.fs14,
              color: active ? Colors.white : MenuModeColors.text2,
              fontWeight: active ? FontWeight.w600 : FontWeight.w400,
              letterSpacing: 0.28,
            ),
          ),
        ),
      ),
    );
  }
}

/// 数字徽标（红色 9+）
class MenuNumBadge extends StatelessWidget {
  final int count;
  const MenuNumBadge({super.key, required this.count});
  @override
  Widget build(BuildContext context) {
    if (count <= 0) return const SizedBox.shrink();
    final text = count > 99 ? '99+' : count.toString();
    return Container(
      constraints: const BoxConstraints(minWidth: 18),
      height: 18,
      padding: const EdgeInsets.symmetric(horizontal: 5),
      decoration: BoxDecoration(
        color: MenuModeColors.danger,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: Colors.white, width: 2),
      ),
      alignment: Alignment.center,
      child: Text(
        text,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
