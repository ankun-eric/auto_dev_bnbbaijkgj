class FamilyManagementModel {
  final int id;
  final int managerUserId;
  final String managerNickname;
  final int managedUserId;
  final String managedUserNickname;
  final int managedMemberId;
  final String status;
  final String? createdAt;

  FamilyManagementModel({
    required this.id,
    required this.managerUserId,
    required this.managerNickname,
    required this.managedUserId,
    required this.managedUserNickname,
    required this.managedMemberId,
    required this.status,
    this.createdAt,
  });

  factory FamilyManagementModel.fromJson(Map<String, dynamic> json) {
    return FamilyManagementModel(
      id: json['id'] ?? 0,
      managerUserId: json['manager_user_id'] ?? 0,
      managerNickname: json['manager_nickname'] ?? '',
      managedUserId: json['managed_user_id'] ?? 0,
      managedUserNickname: json['managed_user_nickname'] ?? '',
      managedMemberId: json['managed_member_id'] ?? 0,
      status: json['status'] ?? '',
      createdAt: json['created_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'manager_user_id': managerUserId,
      'manager_nickname': managerNickname,
      'managed_user_id': managedUserId,
      'managed_user_nickname': managedUserNickname,
      'managed_member_id': managedMemberId,
      'status': status,
      'created_at': createdAt,
    };
  }
}

class ManagedByModel {
  final int id;
  final int managerUserId;
  final String managerNickname;
  final String status;
  final String? createdAt;

  ManagedByModel({
    required this.id,
    required this.managerUserId,
    required this.managerNickname,
    required this.status,
    this.createdAt,
  });

  factory ManagedByModel.fromJson(Map<String, dynamic> json) {
    return ManagedByModel(
      id: json['id'] ?? 0,
      managerUserId: json['manager_user_id'] ?? 0,
      managerNickname: json['manager_nickname'] ?? '',
      status: json['status'] ?? '',
      createdAt: json['created_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'manager_user_id': managerUserId,
      'manager_nickname': managerNickname,
      'status': status,
      'created_at': createdAt,
    };
  }
}

class FamilyInvitationModel {
  final String inviteCode;
  final String status;
  final String inviterNickname;
  final String memberNickname;
  final String? expiresAt;

  FamilyInvitationModel({
    required this.inviteCode,
    required this.status,
    required this.inviterNickname,
    required this.memberNickname,
    this.expiresAt,
  });

  factory FamilyInvitationModel.fromJson(Map<String, dynamic> json) {
    return FamilyInvitationModel(
      inviteCode: json['invite_code'] ?? '',
      status: json['status'] ?? '',
      inviterNickname: json['inviter_nickname'] ?? '',
      memberNickname: json['member_nickname'] ?? '',
      expiresAt: json['expires_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'invite_code': inviteCode,
      'status': status,
      'inviter_nickname': inviterNickname,
      'member_nickname': memberNickname,
      'expires_at': expiresAt,
    };
  }
}

class OperationLogModel {
  final int id;
  final String operatorNickname;
  final String operationType;
  final String operationDetail;
  final String? createdAt;

  OperationLogModel({
    required this.id,
    required this.operatorNickname,
    required this.operationType,
    required this.operationDetail,
    this.createdAt,
  });

  factory OperationLogModel.fromJson(Map<String, dynamic> json) {
    return OperationLogModel(
      id: json['id'] ?? 0,
      operatorNickname: json['operator_nickname'] ?? '',
      operationType: json['operation_type'] ?? '',
      operationDetail: json['operation_detail'] ?? '',
      createdAt: json['created_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'operator_nickname': operatorNickname,
      'operation_type': operationType,
      'operation_detail': operationDetail,
      'created_at': createdAt,
    };
  }
}
