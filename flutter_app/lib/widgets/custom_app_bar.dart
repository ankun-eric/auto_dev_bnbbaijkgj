import 'package:flutter/material.dart';

class CustomAppBar extends StatelessWidget implements PreferredSizeWidget {
  final String title;
  final List<Widget>? actions;
  final bool showBack;
  final VoidCallback? onBack;
  final Color? backgroundColor;
  final Color? titleColor;
  final double elevation;
  final Widget? leading;
  final bool centerTitle;

  const CustomAppBar({
    super.key,
    required this.title,
    this.actions,
    this.showBack = true,
    this.onBack,
    this.backgroundColor,
    this.titleColor,
    this.elevation = 0,
    this.leading,
    this.centerTitle = true,
  });

  @override
  Widget build(BuildContext context) {
    return AppBar(
      title: Text(
        title,
        style: TextStyle(
          color: titleColor ?? Colors.white,
          fontSize: 18,
          fontWeight: FontWeight.w600,
        ),
      ),
      centerTitle: centerTitle,
      backgroundColor: backgroundColor ?? const Color(0xFF52C41A),
      elevation: elevation,
      leading: leading ??
          (showBack
              ? IconButton(
                  icon: Icon(Icons.arrow_back_ios, color: titleColor ?? Colors.white, size: 20),
                  onPressed: onBack ?? () => Navigator.of(context).pop(),
                )
              : null),
      automaticallyImplyLeading: false,
      actions: actions,
    );
  }

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);
}
