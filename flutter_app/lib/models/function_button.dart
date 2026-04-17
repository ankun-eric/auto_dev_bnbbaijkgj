import 'package:flutter/material.dart';

class FunctionButton {
  final int id;
  final String name;
  final String? iconUrl;
  final String buttonType;
  final int sortWeight;
  final bool isEnabled;
  final Map<String, dynamic>? params;

  FunctionButton({
    required this.id,
    required this.name,
    this.iconUrl,
    required this.buttonType,
    this.sortWeight = 0,
    this.isEnabled = true,
    this.params,
  });

  factory FunctionButton.fromJson(Map<String, dynamic> json) {
    return FunctionButton(
      id: json['id'] ?? 0,
      name: json['name'] ?? '',
      iconUrl: json['icon_url'] as String?,
      buttonType: json['button_type'] ?? '',
      sortWeight: json['sort_weight'] ?? 0,
      isEnabled: json['is_enabled'] ?? true,
      params: json['params'] as Map<String, dynamic>?,
    );
  }

  IconData get fallbackIcon {
    switch (buttonType) {
      case 'digital_human_call':
        return Icons.videocam;
      case 'photo_upload':
        return Icons.camera_alt;
      case 'file_upload':
        return Icons.attach_file;
      case 'ai_dialog_trigger':
        return Icons.auto_awesome;
      case 'drug_identify':
        return Icons.medication_outlined;
      case 'external_link':
        return Icons.open_in_new;
      default:
        return Icons.widgets;
    }
  }
}
