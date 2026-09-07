import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../events/bus.dart';
import '../models/desktop.dart';
import 'auth_session.dart';
import 'providers.dart';
import 'workspace_scope.dart';

class DesktopApi {
  DesktopApi(this._dio, this._auth, this._workspace);

  final Dio _dio;
  final AuthSession _auth;
  final WorkspaceScope _workspace;

  Options _options(DesktopScope scope) {
    if (_auth.userId != scope.userId ||
        _workspace.currentId != scope.workspaceId) {
      throw StateError('Desktop request scope changed');
    }
    return Options(headers: {'X-Workspace-Id': scope.workspaceId});
  }

  Future<DesktopStatus> status(
    DesktopScope scope, {
    CancelToken? cancel,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/desktop/status',
      options: _options(scope),
      cancelToken: cancel,
    );
    return DesktopStatus.fromJson(response.data ?? const {});
  }

  /// Explicit retry only; the backend still enforces subscription + role.
  Future<DesktopStatus> retry(DesktopScope scope) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/desktop/provision',
      options: _options(scope),
    );
    return DesktopStatus.fromJson(response.data ?? const {});
  }

  Future<Map<String, dynamic>> ticket(
    DesktopScope scope, {
    String? taskId,
    CancelToken? cancel,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/desktop/ticket',
      options: _options(scope),
      queryParameters: taskId == null ? null : {'task_id': taskId},
      cancelToken: cancel,
    );
    return response.data ?? const {};
  }
}

final desktopApiProvider = Provider<DesktopApi>(
  (ref) => DesktopApi(
    ref.watch(apiDioProvider),
    ref.watch(authSessionProvider),
    ref.watch(workspaceScopeProvider),
  ),
);

/// One read-only, cancelable poll shared by the global progress UI and viewer.
/// Both user and workspace are part of the cache key and request guard.
final desktopStatusProvider = FutureProvider.autoDispose
    .family<DesktopStatus, DesktopScope>((ref, scope) async {
      final cancel = CancelToken();
      Timer? timer;
      var disposed = false;
      final events = ref
          .watch(appEventBusProvider)
          .on('billing.changed')
          .listen((_) => ref.invalidateSelf());
      ref.onDispose(() {
        disposed = true;
        cancel.cancel();
        timer?.cancel();
        unawaited(events.cancel());
      });
      var interval = const Duration(seconds: 15);
      try {
        final status = await ref
            .watch(desktopApiProvider)
            .status(scope, cancel: cancel);
        if (!['running', 'subscription_required'].contains(status.state)) {
          interval = const Duration(seconds: 3);
        }
        final remaining = status.subscriptionEndsAt?.difference(DateTime.now());
        if (remaining != null &&
            remaining > Duration.zero &&
            remaining < interval) {
          interval = remaining;
        }
        return status;
      } finally {
        if (!disposed) timer = Timer(interval, ref.invalidateSelf);
      }
    });
