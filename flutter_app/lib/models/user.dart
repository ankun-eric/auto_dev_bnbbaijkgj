class User {
  final String id;
  final String phone;
  final String? nickname;
  final String? avatar;
  final String? gender;
  final String? birthday;
  final int? age;
  /// Backend returns int; stored as string for display compatibility.
  final String? memberLevel;
  final String? memberCardNo;
  final String? userNo;
  final String? referrerNo;
  final String? role;
  final String? status;
  final int points;
  final String? createdAt;

  User({
    required this.id,
    required this.phone,
    this.nickname,
    this.avatar,
    this.gender,
    this.birthday,
    this.age,
    this.memberLevel,
    this.memberCardNo,
    this.userNo,
    this.referrerNo,
    this.role,
    this.status,
    this.points = 0,
    this.createdAt,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    final ml = json['member_level'];
    return User(
      id: json['id']?.toString() ?? '',
      phone: json['phone']?.toString() ?? '',
      nickname: json['nickname']?.toString(),
      avatar: json['avatar']?.toString(),
      gender: json['gender']?.toString(),
      birthday: json['birthday']?.toString(),
      age: json['age'] is int ? json['age'] as int : int.tryParse(json['age']?.toString() ?? ''),
      memberLevel: ml == null ? null : ml.toString(),
      memberCardNo: json['member_card_no']?.toString(),
      userNo: json['user_no']?.toString(),
      referrerNo: json['referrer_no']?.toString(),
      role: json['role']?.toString(),
      status: json['status']?.toString(),
      points: json['points'] is int ? json['points'] as int : int.tryParse(json['points']?.toString() ?? '') ?? 0,
      createdAt: json['created_at']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'phone': phone,
      'nickname': nickname,
      'avatar': avatar,
      'gender': gender,
      'birthday': birthday,
      'age': age,
      'member_level': memberLevel,
      'member_card_no': memberCardNo,
      'user_no': userNo,
      'referrer_no': referrerNo,
      'role': role,
      'status': status,
      'points': points,
      'created_at': createdAt,
    };
  }

  User copyWith({
    String? nickname,
    String? avatar,
    String? gender,
    String? birthday,
    int? age,
    String? memberLevel,
    String? memberCardNo,
    String? userNo,
    String? referrerNo,
    String? role,
    String? status,
    int? points,
  }) {
    return User(
      id: id,
      phone: phone,
      nickname: nickname ?? this.nickname,
      avatar: avatar ?? this.avatar,
      gender: gender ?? this.gender,
      birthday: birthday ?? this.birthday,
      age: age ?? this.age,
      memberLevel: memberLevel ?? this.memberLevel,
      memberCardNo: memberCardNo ?? this.memberCardNo,
      userNo: userNo ?? this.userNo,
      referrerNo: referrerNo ?? this.referrerNo,
      role: role ?? this.role,
      status: status ?? this.status,
      points: points ?? this.points,
      createdAt: createdAt,
    );
  }
}
