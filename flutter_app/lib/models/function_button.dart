import 'package:flutter/material.dart';

class FunctionButton {
  final int id;
  final String name;
  final String? iconUrl;
  final String buttonType;
  final int sortWeight;
  final bool isEnabled;
  // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 两个独立开关：是否推荐 / 是否胶囊
  final bool isRecommended;
  final bool isCapsule;
  final Map<String, dynamic>? params;
  // [PRD-AICHAT-CAPSULE-V2 2026-05-15] 新增字段，对齐后端 chat_function_buttons 表
  final String? icon; // Emoji
  final String? presetPrompt; // quick_ask 预设话术
  final String? autoUserMessage; // 自动用户消息
  final String? externalUrl;
  final int? promptTemplateId;
  // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查 4 字段
  final int? healthCheckTemplateId;
  final String? archiveMissingStrategy;
  final bool? promptOverrideEnabled;
  final String? promptOverrideText;

  FunctionButton({
    required this.id,
    required this.name,
    this.iconUrl,
    required this.buttonType,
    this.sortWeight = 0,
    this.isEnabled = true,
    this.isRecommended = false,
    this.isCapsule = false,
    this.params,
    this.icon,
    this.presetPrompt,
    this.autoUserMessage,
    this.externalUrl,
    this.promptTemplateId,
    this.healthCheckTemplateId,
    this.archiveMissingStrategy,
    this.promptOverrideEnabled,
    this.promptOverrideText,
  });

  factory FunctionButton.fromJson(Map<String, dynamic> json) {
    return FunctionButton(
      id: json['id'] ?? 0,
      name: json['name'] ?? '',
      iconUrl: json['icon_url'] as String?,
      buttonType: json['button_type'] ?? '',
      sortWeight: json['sort_weight'] ?? 0,
      isEnabled: json['is_enabled'] ?? true,
      isRecommended: json['is_recommended'] ?? false,
      isCapsule: json['is_capsule'] ?? false,
      params: json['params'] as Map<String, dynamic>?,
      icon: json['icon'] as String?,
      presetPrompt: json['preset_prompt'] as String?,
      autoUserMessage: json['auto_user_message'] as String?,
      externalUrl: json['external_url'] as String?,
      promptTemplateId: json['prompt_template_id'] as int?,
      healthCheckTemplateId: json['health_check_template_id'] as int?,
      archiveMissingStrategy: json['archive_missing_strategy'] as String?,
      promptOverrideEnabled: json['prompt_override_enabled'] as bool?,
      promptOverrideText: json['prompt_override_text'] as String?,
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
