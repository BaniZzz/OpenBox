import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/auth_user.dart';
import '../models/json.dart';
import '../ws/ws_client.dart';
import 'logto_session.dart';
import 'providers.dart';

/// Global auth store, mirroring frontend-v2 `shared/api/auth-store.ts`:
/// access token in memory only (on [AuthSession]); refresh token rides the
/// cookie jar; `isLoading` is true until the boot refresh settles.
class AuthState {
  const AuthState({this.user, this.isLoading = true});

  final AuthUser? user;
  final bool isLoading;

  bool get isAuthenticated => user != null;

  String get userId => user?.id ?? 'anonymous';
}

class AuthController extends Notifier<AuthState> {
  @override
  AuthState build() {
    ref.read(authSessionProvider).refreshFn = _doRefresh;
    return const AuthState();
  }

  /// Boot-time silent sign-in (web `refreshAccessToken()` before first
  /// paint): tries the refresh cookie; settles `isLoading`.
  Future<void> bootstrap() async {
    await ref.read(authSessionProvider).refresh();
    if (state.isLoading) state = AuthState(user: state.user, isLoading: false);
  }

  void setAuth(String accessToken, AuthUser user) {
    final session = ref.read(authSessionProvider);
    session.accessToken = accessToken;
    session.userId = user.id;
    state = AuthState(user: user, isLoading: false);
  }

  void clearAuth() {
    final session = ref.read(authSessionProvider);
    session.accessToken = null;
    session.userId = null;
    ref.read(workspaceScopeProvider).clear();
    state = const AuthState(isLoading: false);
  }

  /// Sign out of both OpenBox and Logto. OpenBox state is always cleared even
  /// if either server is unavailable; Logto's SDK also removes native tokens
  /// in its own best-effort cleanup path.
  Future<void> signOut() async {
    final logtoConfig = ref.read(logtoSsoProvider.future);
    try {
      await ref.read(apiDioProvider).post<dynamic>('/api/auth/logout');
    } catch (_) {
      // Sign out locally regardless.
    }
    ref.read(wsClientProvider).disconnect();
    clearAuth();
    try {
      await ref.read(logtoSessionProvider).signOut(await logtoConfig);
    } catch (_) {
      // The local OpenBox and Logto token state has already been cleared. A
      // canceled/unreachable browser logout must never restore this session.
    }
  }

  /// POST /api/auth/refresh (cookie) → GET /api/auth/me. Returns the new
  /// access token or null (→ signed out). Wired into [AuthSession] so
  /// concurrent 401s share one round-trip.
  Future<String?> _doRefresh() async {
    final dio = ref.read(refreshDioProvider);
    try {
      final refreshResp = await dio.post<Map<String, dynamic>>(
        '/api/auth/refresh',
      );
      final token = asString(refreshResp.data?['access_token']);
      if (token == null) {
        clearAuth();
        return null;
      }
      final meResp = await dio.get<Map<String, dynamic>>(
        '/api/auth/me',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      final authSession = ref.read(authSessionProvider);
      authSession.accessToken = token;
      final user = AuthUser.fromJson(meResp.data ?? const {});
      authSession.userId = user.id;
      state = AuthState(user: user, isLoading: false);
      return token;
    } on DioException {
      clearAuth();
      return null;
    }
  }
}

final authProvider = NotifierProvider<AuthController, AuthState>(
  AuthController.new,
);
