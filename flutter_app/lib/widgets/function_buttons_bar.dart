import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../models/function_button.dart';

class FunctionButtonsBar extends StatelessWidget {
  final List<FunctionButton> buttons;
  final void Function(FunctionButton button) onButtonTap;

  const FunctionButtonsBar({
    super.key,
    required this.buttons,
    required this.onButtonTap,
  });

  @override
  Widget build(BuildContext context) {
    if (buttons.isEmpty) return const SizedBox.shrink();

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border(
          bottom: BorderSide(color: Colors.grey.shade200, width: 0.5),
        ),
      ),
      child: SizedBox(
        height: 65,
        child: ListView.builder(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
          itemCount: buttons.length,
          itemBuilder: (context, index) {
            final btn = buttons[index];
            return _buildButton(btn);
          },
        ),
      ),
    );
  }

  Widget _buildButton(FunctionButton btn) {
    return GestureDetector(
      onTap: () => onButtonTap(btn),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 6),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: const Color(0xFFF5F7FA),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0xFFE8E8E8), width: 0.5),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildIcon(btn),
            const SizedBox(height: 3),
            Text(
              btn.name,
              style: const TextStyle(
                fontSize: 11,
                color: Color(0xFF666666),
                fontWeight: FontWeight.w500,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildIcon(FunctionButton btn) {
    if (btn.iconUrl != null && btn.iconUrl!.isNotEmpty) {
      return CachedNetworkImage(
        imageUrl: btn.iconUrl!,
        width: 24,
        height: 24,
        errorWidget: (_, __, ___) => Icon(btn.fallbackIcon, size: 22, color: const Color(0xFF52C41A)),
      );
    }
    return Icon(btn.fallbackIcon, size: 22, color: const Color(0xFF52C41A));
  }
}
