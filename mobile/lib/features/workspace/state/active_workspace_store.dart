import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/api/auth_store.dart';
import '../../../shared/api/providers.dart';
import '../../../shared/models/workspace.dart';
import '../api/workspace_api.dart';

const _workspaceStorageKey = 'openbox:workspace-id';

class ActiveWorkspaceState {
  const ActiveWorkspaceState({this.items = const [], this.currentId});

  final List<WorkspaceSummary> items;
  final String? currentId;

  WorkspaceSummary? get current {
    for (final item in items) {
      if (item.id == currentId) return item;
    }
    return null;
  }

  ActiveWorkspaceState copyWith({
    List<WorkspaceSummary>? items,
    String? currentId,
  }) => ActiveWorkspaceState(
    items: items ?? this.items,
    currentId: currentId ?? this.currentId,
  );
}

/// Auth-scoped workspace bootstrap. The selected id is persisted like the web
/// store and mirrored into [workspaceScopeProvider] for synchronous transport
/// header injection.
class ActiveWorkspaceController extends AsyncNotifier<ActiveWorkspaceState> {
  @override
  Future<ActiveWorkspaceState> build() async {
    final userId = ref.watch(authProvider.select((state) => state.user?.id));
    final scope = ref.read(workspaceScopeProvider);
    if (userId == null) {
      scope.clear();
      return const ActiveWorkspaceState();
    }

    final prefs = ref.read(prefsProvider);
    final persisted = prefs.getString(_workspaceStorageKey);
    // A valid persisted scope may safely accompany the list bootstrap; the
    // list endpoint itself is user-scoped and ignores workspace membership.
    scope.currentId = persisted;
    final result = await ref.read(workspaceApiProvider).listWorkspaces();
    final selected = result.items.any((item) => item.id == persisted)
        ? persisted
        : result.defaultWorkspaceId ??
              (result.items.isEmpty ? null : result.items.first.id);
    scope.currentId = selected;
    await _persist(selected);
    return ActiveWorkspaceState(items: result.items, currentId: selected);
  }

  Future<void> refresh() async {
    await _refresh();
  }

  Future<void> _refresh({String? preferredId}) async {
    final result = await ref.read(workspaceApiProvider).listWorkspaces();
    final preferred = preferredId ?? state.valueOrNull?.currentId;
    final selected = result.items.any((item) => item.id == preferred)
        ? preferred
        : result.defaultWorkspaceId ??
              (result.items.isEmpty ? null : result.items.first.id);
    ref.read(workspaceScopeProvider).currentId = selected;
    await _persist(selected);
    state = AsyncData(
      ActiveWorkspaceState(items: result.items, currentId: selected),
    );
  }

  Future<void> select(String workspaceId) async {
    final data = state.valueOrNull;
    if (data == null ||
        data.currentId == workspaceId ||
        !data.items.any((item) => item.id == workspaceId)) {
      return;
    }
    ref.read(workspaceScopeProvider).currentId = workspaceId;
    await _persist(workspaceId);
    state = AsyncData(data.copyWith(currentId: workspaceId));
  }

  Future<void> selectAndRefresh(String workspaceId) async {
    ref.read(workspaceScopeProvider).currentId = workspaceId;
    await _persist(workspaceId);
    await _refresh(preferredId: workspaceId);
  }

  Future<void> _persist(String? workspaceId) async {
    final prefs = ref.read(prefsProvider);
    if (workspaceId == null) {
      await prefs.remove(_workspaceStorageKey);
    } else {
      await prefs.setString(_workspaceStorageKey, workspaceId);
    }
  }
}

final activeWorkspaceProvider =
    AsyncNotifierProvider<ActiveWorkspaceController, ActiveWorkspaceState>(
      ActiveWorkspaceController.new,
    );

final currentWorkspaceDetailProvider = FutureProvider<WorkspaceDetail>((ref) {
  final workspaceId = ref.watch(activeWorkspaceProvider).valueOrNull?.currentId;
  if (workspaceId == null) {
    return Future.error(StateError('No active workspace'));
  }
  return ref.read(workspaceApiProvider).getCurrentWorkspace();
});

final pendingWorkspaceInvitationsProvider =
    FutureProvider<List<WorkspaceInvitation>>((ref) {
      ref.watch(authProvider.select((state) => state.user?.id));
      return ref.read(workspaceApiProvider).listPendingInvitations();
    });
