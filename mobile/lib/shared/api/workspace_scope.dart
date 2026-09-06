/// Mutable request scope shared by the workspace store and Dio interceptors.
///
/// It deliberately carries no persistence or UI state. Requests can read the
/// selected id synchronously, including while an access-token refresh is in
/// flight, while Riverpod remains the source of truth for the visible list.
class WorkspaceScope {
  String? currentId;

  void clear() => currentId = null;
}
