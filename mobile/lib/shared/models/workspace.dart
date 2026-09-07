import 'json.dart';

enum WorkspaceKind { personal, team }

enum WorkspaceRole { owner, admin, member }

extension WorkspaceRoleWire on WorkspaceRole {
  String get wire => name;

  bool get canManage =>
      this == WorkspaceRole.owner || this == WorkspaceRole.admin;
}

WorkspaceRole workspaceRoleFrom(String? value) => switch (value) {
  'owner' => WorkspaceRole.owner,
  'admin' => WorkspaceRole.admin,
  _ => WorkspaceRole.member,
};

class WorkspaceSummary {
  const WorkspaceSummary({
    required this.id,
    required this.name,
    required this.ownerUserId,
    required this.kind,
    required this.role,
  });

  factory WorkspaceSummary.fromJson(Map<String, dynamic> json) =>
      WorkspaceSummary(
        id: asString(json['id']) ?? '',
        name: asString(json['name']) ?? '',
        ownerUserId: asString(json['owner_user_id']) ?? '',
        kind: asString(json['kind']) == 'team'
            ? WorkspaceKind.team
            : WorkspaceKind.personal,
        role: workspaceRoleFrom(asString(json['role'])),
      );

  final String id;
  final String name;
  final String ownerUserId;
  final WorkspaceKind kind;
  final WorkspaceRole role;
}

class WorkspaceMember {
  const WorkspaceMember({
    required this.userId,
    required this.username,
    this.email,
    required this.role,
    required this.status,
    required this.createdAt,
  });

  factory WorkspaceMember.fromJson(Map<String, dynamic> json) =>
      WorkspaceMember(
        userId: asString(json['user_id']) ?? '',
        username: asString(json['username']) ?? '',
        email: asString(json['email']),
        role: workspaceRoleFrom(asString(json['role'])),
        status: asString(json['status']) ?? 'active',
        createdAt: asDate(json['created_at']) ?? DateTime.now(),
      );

  final String userId;
  final String username;
  final String? email;
  final WorkspaceRole role;
  final String status;
  final DateTime createdAt;
}

class WorkspaceInvitation {
  const WorkspaceInvitation({
    required this.id,
    required this.workspaceId,
    this.workspaceName,
    required this.target,
    required this.role,
    required this.expiresAt,
    this.token,
    this.acceptedAt,
  });

  factory WorkspaceInvitation.fromJson(Map<String, dynamic> json) =>
      WorkspaceInvitation(
        id: asString(json['id']) ?? '',
        workspaceId: asString(json['workspace_id']) ?? '',
        workspaceName: asString(json['workspace_name']),
        target: asString(json['target']) ?? '',
        role: workspaceRoleFrom(asString(json['role'])),
        expiresAt: asDate(json['expires_at']) ?? DateTime.now(),
        token: asString(json['token']),
        acceptedAt: asDate(json['accepted_at']),
      );

  final String id;
  final String workspaceId;
  final String? workspaceName;
  final String target;
  final WorkspaceRole role;
  final DateTime expiresAt;
  final String? token;
  final DateTime? acceptedAt;
}

class WorkspaceDetail {
  const WorkspaceDetail({
    required this.summary,
    this.members = const [],
    this.invitations = const [],
  });

  factory WorkspaceDetail.fromJson(Map<String, dynamic> json) =>
      WorkspaceDetail(
        summary: WorkspaceSummary.fromJson(json),
        members: asList(json['members'])
            .whereType<Map<String, dynamic>>()
            .map(WorkspaceMember.fromJson)
            .toList(),
        invitations: asList(json['invitations'])
            .whereType<Map<String, dynamic>>()
            .map(WorkspaceInvitation.fromJson)
            .toList(),
      );

  final WorkspaceSummary summary;
  final List<WorkspaceMember> members;
  final List<WorkspaceInvitation> invitations;

  WorkspaceRole get role => summary.role;
}

class WorkspaceListResult {
  const WorkspaceListResult({required this.items, this.defaultWorkspaceId});

  factory WorkspaceListResult.fromJson(Map<String, dynamic> json) =>
      WorkspaceListResult(
        items: asList(json['items'])
            .whereType<Map<String, dynamic>>()
            .map(WorkspaceSummary.fromJson)
            .where((item) => item.id.isNotEmpty)
            .toList(),
        defaultWorkspaceId: asString(json['default_workspace_id']),
      );

  final List<WorkspaceSummary> items;
  final String? defaultWorkspaceId;
}
