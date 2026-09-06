import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/appearance/tokens.dart';
import '../../../shared/appearance/type_scale.dart';
import '../../../shared/i18n/i18n.dart';
import '../../../shared/models/workspace.dart';
import '../../../shared/router/paths.dart';
import '../state/active_workspace_store.dart';

/// Compact mobile equivalent of the sidebar workspace switcher. Like web it
/// stays out of the way for single-workspace accounts.
class WorkspaceSwitcher extends ConsumerWidget {
  const WorkspaceSwitcher({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final data = ref.watch(activeWorkspaceProvider).valueOrNull;
    if (data == null || data.items.length <= 1 || data.current == null) {
      return const SizedBox.shrink();
    }
    final t = context.tokens;
    final i18n = ref.watch(i18nProvider);
    return Padding(
      padding: const EdgeInsets.only(top: 10, bottom: 2),
      child: Material(
        color: t.n100.withValues(alpha: 0.65),
        borderRadius: BorderRadius.circular(Radii.full),
        child: InkWell(
          borderRadius: BorderRadius.circular(Radii.full),
          onTap: () => _showPicker(context, ref, data.items, data.currentId!),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
            child: Row(
              children: [
                Icon(Icons.workspaces_outline, size: 16, color: t.n700),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        i18n.t('workspace:workspaceSwitcher'),
                        style: TextStyle(
                          fontSize: FontSizes.xs2,
                          color: t.n500,
                        ),
                      ),
                      Text(
                        data.current!.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: FontSizes.sm,
                          fontWeight: FontWeight.w500,
                          color: t.ink,
                        ),
                      ),
                    ],
                  ),
                ),
                Icon(Icons.unfold_more, size: 16, color: t.n600),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _showPicker(
    BuildContext context,
    WidgetRef ref,
    List<WorkspaceSummary> items,
    String currentId,
  ) async {
    final t = context.tokens;
    final i18n = ref.read(i18nProvider);
    final selected = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: t.card,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 2, 20, 10),
              child: Text(
                i18n.t('workspace:workspaceSwitcher'),
                style: TextStyle(
                  fontSize: FontSizes.lg,
                  fontWeight: FontWeight.w500,
                  color: t.ink,
                ),
              ),
            ),
            for (final item in items)
              ListTile(
                leading: Icon(
                  item.kind == WorkspaceKind.team
                      ? Icons.groups_outlined
                      : Icons.person_outline,
                  color: t.n700,
                ),
                title: Text(item.name, style: TextStyle(color: t.ink)),
                subtitle: Text(
                  i18n.t('settings:team.roles.${item.role.wire}'),
                  style: TextStyle(fontSize: FontSizes.xs, color: t.n600),
                ),
                trailing: item.id == currentId
                    ? Icon(Icons.check_circle, color: t.a700)
                    : null,
                onTap: item.id == currentId
                    ? null
                    : () => Navigator.pop(sheetContext, item.id),
              ),
          ],
        ),
      ),
    );
    if (selected == null || !context.mounted) return;
    await ref.read(activeWorkspaceProvider.notifier).select(selected);
    if (!context.mounted) return;
    // This widget lives in the workspace drawer. Close both the picker and the
    // drawer, then leave any old-session route before its scoped data reloads.
    await Navigator.maybePop(context);
    if (context.mounted) context.go(Paths.app);
  }
}
