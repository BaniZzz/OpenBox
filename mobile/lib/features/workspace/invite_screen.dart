import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../shared/appearance/tokens.dart';
import '../../shared/appearance/type_scale.dart';
import '../../shared/i18n/i18n.dart';
import '../../shared/router/paths.dart';
import '../../shared/utils/error_text.dart';
import 'api/workspace_api.dart';
import 'state/active_workspace_store.dart';

class InviteScreen extends ConsumerStatefulWidget {
  const InviteScreen({super.key, required this.token});

  final String token;

  @override
  ConsumerState<InviteScreen> createState() => _InviteScreenState();
}

class _InviteScreenState extends ConsumerState<InviteScreen> {
  bool _loading = false;
  bool _accepted = false;
  String? _error;

  Future<void> _accept() async {
    if (widget.token.isEmpty || _loading) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final workspaceId = await ref
          .read(workspaceApiProvider)
          .acceptInvitation(widget.token);
      if (workspaceId.isEmpty) throw StateError('Missing workspace id');
      await ref
          .read(activeWorkspaceProvider.notifier)
          .selectAndRefresh(workspaceId);
      ref.invalidate(currentWorkspaceDetailProvider);
      ref.invalidate(pendingWorkspaceInvitationsProvider);
      if (mounted) setState(() => _accepted = true);
    } catch (error) {
      if (mounted) {
        setState(() => _error = errorText(ref.read(i18nProvider), error));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    final i18n = ref.watch(i18nProvider);
    return Scaffold(
      backgroundColor: t.bg,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Container(
              width: double.infinity,
              constraints: const BoxConstraints(maxWidth: 440),
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: t.card,
                border: Border.all(color: t.hair),
                borderRadius: BorderRadius.circular(Radii.xl),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.group_add_outlined, size: 36, color: t.a700),
                  const SizedBox(height: 14),
                  Text(
                    i18n.t('settings:team.acceptTitle'),
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: FontSizes.xl,
                      fontWeight: FontWeight.w500,
                      color: t.ink,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    i18n.t(
                      _accepted
                          ? 'settings:team.accepted'
                          : 'settings:team.acceptHint',
                    ),
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: FontSizes.sm,
                      height: 1.5,
                      color: t.n600,
                    ),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(
                      _error!,
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: FontSizes.sm, color: t.danger),
                    ),
                  ],
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _accepted
                          ? () => context.go(Paths.app)
                          : (_loading ? null : _accept),
                      style: FilledButton.styleFrom(
                        backgroundColor: t.ink,
                        foregroundColor: t.bg,
                      ),
                      child: Text(
                        i18n.t(
                          _accepted
                              ? 'settings:team.enterWorkspace'
                              : 'settings:team.accept',
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
