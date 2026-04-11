import 'package:flutter/material.dart';
import '../models/health_profile.dart';

class DiseaseTagSelector extends StatefulWidget {
  final String title;
  final List<String> presets;
  final List<dynamic> selectedItems;
  final ValueChanged<List<dynamic>> onChanged;
  final Color color;

  const DiseaseTagSelector({
    super.key,
    required this.title,
    required this.presets,
    required this.selectedItems,
    required this.onChanged,
    this.color = const Color(0xFF52C41A),
  });

  @override
  State<DiseaseTagSelector> createState() => _DiseaseTagSelectorState();
}

class _DiseaseTagSelectorState extends State<DiseaseTagSelector> {
  bool _showCustomInput = false;
  final TextEditingController _customController = TextEditingController();
  final int _maxCustomLength = 100;

  List<dynamic> get _items => widget.selectedItems;

  bool _isSelected(String name) {
    return _items.any((item) => HealthProfile.getItemName(item) == name);
  }

  List<dynamic> get _customItems =>
      _items.where((item) => HealthProfile.isCustomItem(item)).toList();

  void _togglePreset(String name) {
    final newList = List<dynamic>.from(_items);
    final idx = newList.indexWhere((item) =>
        !HealthProfile.isCustomItem(item) &&
        HealthProfile.getItemName(item) == name);
    if (idx >= 0) {
      newList.removeAt(idx);
    } else {
      newList.add(name);
    }
    widget.onChanged(newList);
  }

  void _addCustom() {
    final value = _customController.text.trim();
    if (value.isEmpty) return;
    if (_items.any((item) => HealthProfile.getItemName(item) == value)) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('"$value" 已存在'), duration: const Duration(seconds: 1)),
      );
      return;
    }
    final newList = List<dynamic>.from(_items);
    newList.add({'type': 'custom', 'value': value});
    widget.onChanged(newList);
    _customController.clear();
    setState(() => _showCustomInput = false);
  }

  void _removeCustom(dynamic item) {
    final newList = List<dynamic>.from(_items);
    newList.remove(item);
    widget.onChanged(newList);
  }

  @override
  void dispose() {
    _customController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 4,
                height: 16,
                decoration: BoxDecoration(
                  color: widget.color,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                widget.title,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF333333),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              ...widget.presets.map((name) => _buildPresetChip(name)),
              _buildOtherChip(),
            ],
          ),
          if (_showCustomInput) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _customController,
                    maxLength: _maxCustomLength,
                    decoration: InputDecoration(
                      hintText: '请输入自定义名称',
                      hintStyle: const TextStyle(fontSize: 14, color: Color(0xFFBFBFBF)),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                      counterText: '',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: BorderSide(color: Colors.grey[300]!),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: BorderSide(color: widget.color),
                      ),
                      isDense: true,
                    ),
                    style: const TextStyle(fontSize: 14),
                    onSubmitted: (_) => _addCustom(),
                  ),
                ),
                const SizedBox(width: 8),
                TextButton(
                  onPressed: _addCustom,
                  style: TextButton.styleFrom(
                    foregroundColor: widget.color,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  ),
                  child: const Text('确认', style: TextStyle(fontWeight: FontWeight.w600)),
                ),
              ],
            ),
          ],
          if (_customItems.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _customItems.map((item) => _buildCustomChip(item)).toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildPresetChip(String name) {
    final selected = _isSelected(name);
    return FilterChip(
      label: Text(name),
      selected: selected,
      onSelected: (_) => _togglePreset(name),
      selectedColor: widget.color.withOpacity(0.15),
      checkmarkColor: widget.color,
      labelStyle: TextStyle(
        fontSize: 13,
        color: selected ? widget.color : const Color(0xFF666666),
        fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
      ),
      side: BorderSide(
        color: selected ? widget.color : const Color(0xFFE8E8E8),
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 0),
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
    );
  }

  Widget _buildOtherChip() {
    return ActionChip(
      avatar: Icon(Icons.add, size: 16, color: widget.color),
      label: const Text('其它'),
      onPressed: () => setState(() => _showCustomInput = !_showCustomInput),
      labelStyle: TextStyle(fontSize: 13, color: widget.color),
      side: BorderSide(color: widget.color.withOpacity(0.4)),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 0),
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
    );
  }

  Widget _buildCustomChip(dynamic item) {
    final name = HealthProfile.getItemName(item);
    return Chip(
      label: Text(name),
      deleteIcon: const Icon(Icons.close, size: 16),
      onDeleted: () => _removeCustom(item),
      backgroundColor: widget.color.withOpacity(0.08),
      deleteIconColor: widget.color,
      labelStyle: TextStyle(fontSize: 13, color: widget.color, fontWeight: FontWeight.w500),
      side: BorderSide(color: widget.color.withOpacity(0.3)),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 0),
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
    );
  }
}
