import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/api/providers.dart';
import '../../../shared/models/container.dart';
import '../../../shared/models/diff.dart';
import '../../../shared/models/json.dart';

/// Review/files/containers REST calls (web `features/workbench/api/*`).
class WorkbenchApi {
  WorkbenchApi(this._dio);

  final Dio _dio;

  Future<DesktopStatus> desktopStatus() async {
    final resp =
        await _dio.get<Map<String, dynamic>>('/api/desktop/status');
    return DesktopStatus.fromJson(resp.data ?? const {});
  }

  Future<DesktopStatus> provisionDesktop() async {
    final resp =
        await _dio.post<Map<String, dynamic>>('/api/desktop/provision');
    return DesktopStatus.fromJson(resp.data ?? const {});
  }

  Future<List<DiffEntry>> sessionDiff(String sessionId) async {
    final resp = await _dio.get<List<dynamic>>(
      '/api/agent/session/$sessionId/diff',
      queryParameters: {'full': true},
    );
    return (resp.data ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(DiffEntry.fromJson)
        .toList();
  }

  /// The session's project workdir (`directory` on `GET /session/{id}`),
  /// used as the files-tab root (web D.4.7 — never climb above it).
  Future<String?> sessionDirectory(String sessionId) async {
    final resp = await _dio
        .get<Map<String, dynamic>>('/api/agent/session/$sessionId');
    return asString(resp.data?['directory']);
  }

  /// The session's owning project (the cron tab scopes to it).
  Future<String?> sessionProjectId(String sessionId) async {
    final resp = await _dio
        .get<Map<String, dynamic>>('/api/agent/session/$sessionId');
    return asString(resp.data?['project_id']);
  }

  Future<List<FileEntry>> listFiles(String containerId, String path) async {
    final resp = await _dio.post<dynamic>(
      '/api/containers/$containerId/files/list',
      data: {'path': path},
    );
    return FileEntry.listFrom(resp.data);
  }

  Future<FileContent> fileContent(String containerId, String path) async {
    final resp = await _dio.get<Map<String, dynamic>>(
      '/api/containers/$containerId/files/content',
      queryParameters: {'path': path},
    );
    return FileContent.fromJson(resp.data ?? const {});
  }
}

final workbenchApiProvider =
    Provider<WorkbenchApi>((ref) => WorkbenchApi(ref.watch(apiDioProvider)));

class DesktopStatus {
  const DesktopStatus({
    required this.state,
    this.mode,
    this.error,
    this.channel,
  });

  factory DesktopStatus.fromJson(Map<String, dynamic> json) => DesktopStatus(
        state: asString(json['state']) ?? '',
        mode: asString(json['mode']),
        error: asString(json['error']),
        channel: json['channel'] is Map<String, dynamic>
            ? DesktopChannelStatus.fromJson(
                json['channel'] as Map<String, dynamic>,
              )
            : null,
      );

  final String state;
  final String? mode;
  final String? error;
  final DesktopChannelStatus? channel;
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
