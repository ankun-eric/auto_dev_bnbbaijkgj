import 'package:flutter/material.dart';

class FunctionButton {
  final int id;
  final String name;
  final String? iconUrl;
  final String buttonType;
  final int sortWeight;
  final bool isEnabled;
  final Map<String, dynamic>? params;
  // [PRD-AICHAT-CAPSULE-V2 2026-05-15] 新增字段，对齐后端 chat_function_buttons 表
  final String? icon; // Emoji
  final String? presetPrompt; // quick_ask 预设话术
  final String? autoUserMessage; // 自动用户消息
  final String? externalUrl;
  final int? promptTemplateId;

  FunctionButton({
    required this.id,
    required this.name,
    this.iconUrl,
    required this.buttonType,
    this.sortWeight = 0,
    this.isEnabled = true,
    this.params,
    this.icon,
    this.presetPrompt,
    this.autoUserMessage,
    this.externalUrl,
    this.promptTemplateId,
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
      icon: json['icon'] as String?,
      presetPrompt: json['preset_prompt'] as String?,
      autoUserMessage: json['auto_user_message'] as String?,
      externalUrl: json['external_url'] as String?,
      promptTemplateId: json['prompt_template_id'] as int?,
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
      case 'photo_recognize_drug':
        return Icons.medication_outlined;
      case 'external_link':
        return Icons.open_in_new;
      case 'quick_ask':
      case 'prompt_template':
        return Icons.bolt;
      default:
        return Icons.widgets;
    }
  }
}
