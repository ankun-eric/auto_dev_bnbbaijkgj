// PRD-442 ThemeData — 基于 BhTokens 构造 Material ThemeData
import 'package:flutter/material.dart';
import 'tokens.g.dart';

class BhTheme {
  BhTheme._();

  static ThemeData lightTheme() {
    final ColorScheme scheme = ColorScheme.fromSeed(
      seedColor: BhTokens.colorBrand400,
      brightness: Brightness.light,
      primary: BhTokens.colorBrand400,
      onPrimary: BhTokens.colorTextInverse,
      surface: BhTokens.colorBgBase,
      onSurface: BhTokens.colorTextPrimary,
    );
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: BhTokens.colorBgSoft,
      appBarTheme: const AppBarTheme(
        backgroundColor: BhTokens.colorBgBase,
        foregroundColor: BhTokens.colorTextPrimary,
        elevation: 0,
        centerTitle: true,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: BhTokens.colorBrand400,
          foregroundColor: BhTokens.colorTextInverse,
          minimumSize: const Size(64, 44),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(BhTokens.radiusLg),
          ),
        ),
      ),
      cardTheme: CardTheme(
        color: BhTokens.colorBgBase,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(BhTokens.radiusLg),
        ),
      ),
    );
  }
}
