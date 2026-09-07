import 'json.dart';

typedef DesktopScope = ({String userId, String workspaceId});

/// Server-owned subscription/activation state. The client never starts a
/// purchase or provisions a desktop simply by opening a page.
class DesktopStatus {
  const DesktopStatus({
    required this.state,
    this.mode,
    this.entitled,
    this.retained = false,
    this.subscriptionEndsAt,
    this.error,
    this.channel,
    this.activation,
  });

  factory DesktopStatus.fromJson(Map<String, dynamic> json) => DesktopStatus(
    state: asString(json['state']) ?? '',
    mode: asString(json['mode']),
    entitled: json['entitled'] is bool ? json['entitled'] as bool : null,
    retained: json['retained'] == true,
    subscriptionEndsAt: asDate(json['subscription_ends_at']),
    error: asString(json['error']),
    channel: json['channel'] is Map<String, dynamic>
        ? DesktopChannelStatus.fromJson(asMap(json['channel']))
        : null,
    activation: json['activation'] is Map<String, dynamic>
        ? DesktopActivation.fromJson(asMap(json['activation']))
        : null,
  );

  final String state;
  final String? mode;
  final bool? entitled;
  final bool retained;
  final DateTime? subscriptionEndsAt;
  final String? error;
  final DesktopChannelStatus? channel;
  final DesktopActivation? activation;

  bool hasAccessAt(DateTime now) =>
      state != 'subscription_required' &&
      entitled != false &&
      (mode != 'per_user' || entitled == true) &&
      (subscriptionEndsAt == null || now.isBefore(subscriptionEndsAt!));

  bool get hasAccess => hasAccessAt(DateTime.now());
  bool get ready => state == 'running' && hasAccess;
  bool get hasActivation =>
      mode == 'per_user' &&
      entitled == true &&
      hasAccess &&
      (activation?.requestId?.isNotEmpty ?? false);
  bool get needsAttention => activation?.state == 'needs_attention';

  int get progressPosition => ready
      ? 4
      : switch (activation?.step) {
          'starting' => 2,
          'connecting' => 3,
          'ready' => 4,
          _ => 1,
        };
}

class DesktopActivation {
  const DesktopActivation({
    this.requestId,
    required this.state,
    required this.step,
    this.attempts = 0,
    this.error,
    this.updatedAt,
    this.nextRetryAt,
    this.canRetry = false,
  });

  factory DesktopActivation.fromJson(Map<String, dynamic> json) =>
      DesktopActivation(
        requestId: asString(json['request_id']),
        state: asString(json['state']) ?? '',
        step: asString(json['step']) ?? '',
        attempts: asInt(json['attempts']) ?? 0,
        error: asString(json['error']),
        updatedAt: asDate(json['updated_at']),
        nextRetryAt: asDate(json['next_retry_at']),
        canRetry: json['can_retry'] == true,
      );

  final String? requestId;
  final String state;
  final String step;
  final int attempts;
  final String? error;
  final DateTime? updatedAt;
  final DateTime? nextRetryAt;
  final bool canRetry;
}

class DesktopChannelStatus {
  const DesktopChannelStatus({
    required this.state,
    this.lastSeenAt,
    this.error,
  });

  factory DesktopChannelStatus.fromJson(Map<String, dynamic> json) =>
      DesktopChannelStatus(
        state: asString(json['state']) ?? '',
        lastSeenAt: asDate(json['last_seen_at']),
        error: asString(json['error']),
      );

  final String state;
  final DateTime? lastSeenAt;
  final String? error;
}
