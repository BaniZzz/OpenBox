import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/api/auth_store.dart';
import '../../../shared/api/containers_api.dart';
import '../../../shared/api/desktop_api.dart';
import '../../../shared/appearance/tokens.dart';
import '../../../shared/i18n/i18n.dart';
import '../../../shared/models/desktop.dart';
import '../../../shared/router/paths.dart';
import '../../../shared/utils/error_text.dart';
import '../../workspace/state/active_workspace_store.dart';
import 'desktop_subscription_notice.dart';

/// Terminal/browser/files follow the same entitlement as the desktop viewer.
/// No legacy Docker "create sandbox" action can bypass subscription setup.
class SubscriptionSandboxSurface extends ConsumerWidget {
  const SubscriptionSandboxSurface({super.key, required this.builder});
  final Widget Function(String containerId) builder;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authProvider).user;
    final workspaceId = ref
        .watch(activeWorkspaceProvider)
        .valueOrNull
        ?.currentId;
    if (user == null || workspaceId == null) {
      return const Center(child: CircularProgressIndicator());
    }
    final scope = (userId: user.id, workspaceId: workspaceId);
    return _ScopedSurface(key: ValueKey(scope), scope: scope, builder: builder);
  }
}

class _ScopedSurface extends ConsumerWidget {
  const _ScopedSurface({super.key, required this.scope, required this.builder});
  final DesktopScope scope;
  final Widget Function(String containerId) builder;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final i18n = ref.watch(i18nProvider);
    Widget message(String text) => Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              text,
              textAlign: TextAlign.center,
              style: TextStyle(color: context.tokens.n600, height: 1.5),
            ),
            const SizedBox(height: 16),
            OutlinedButton(
              onPressed: () => context.push(Paths.desktop),
              child: Text(i18n.t('workbench:tabs.desktop')),
            ),
          ],
        ),
      ),
    );
    return ref
        .watch(desktopStatusProvider(scope))
        .when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => message(errorText(i18n, error)),
          data: (status) {
            if (!status.hasAccess) return const DesktopSubscriptionNotice();
            if (!status.ready) {
              return message(i18n.t('workbench:activation.hint'));
            }
            return ref
                .watch(runningScopedContainerProvider(scope))
                .when(
                  loading: () =>
                      const Center(child: CircularProgressIndicator()),
                  error: (error, _) => message(errorText(i18n, error)),
                  data: (container) => container == null
                      ? message(i18n.t('workbench:sandbox.none'))
                      : builder(container.id),
                );
          },
        );
  }
}
