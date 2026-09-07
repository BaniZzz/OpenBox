import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/appearance/tokens.dart';
import '../../../shared/appearance/type_scale.dart';
import '../../../shared/config/env.dart';
import '../../../shared/i18n/i18n.dart';
import '../../../shared/models/workspace.dart';
import '../../../shared/utils/error_text.dart';
import '../../../shared/widgets/toast.dart';
import '../../workspace/api/workspace_api.dart';
import '../../workspace/state/active_workspace_store.dart';

class TeamSection extends ConsumerStatefulWidget {
  const TeamSection({super.key});

  @override
  ConsumerState<TeamSection> createState() => _TeamSectionState();
}

class _TeamSectionState extends ConsumerState<TeamSection> {
  final _target = TextEditingController();
  WorkspaceRole _inviteRole = WorkspaceRole.member;
  bool _submitting = false;
  String? _inviteUrl;

  @override
  void dispose() {
    _target.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final detail = ref.watch(currentWorkspaceDetailProvider);
    final pending = ref.watch(pendingWorkspaceInvitationsProvider);
    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          detail.when(
            loading: () => const _LoadingCard(),
            error: (error, _) => _ErrorCard(
              message: errorText(ref.watch(i18nProvider), error),
              onRetry: () => ref.invalidate(currentWorkspaceDetailProvider),
            ),
            data: (workspace) => Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (workspace.role.canManage) _inviteCard(workspace),
                if (_inviteUrl != null) ...[
                  const SizedBox(height: 12),
                  _InviteLink(url: _inviteUrl!),
                ],
                const SizedBox(height: 16),
                _membersCard(workspace),
              ],
            ),
          ),
          const SizedBox(height: 16),
          pending.when(
            loading: () => const _LoadingCard(),
            error: (error, _) => _ErrorCard(
              message: errorText(ref.watch(i18nProvider), error),
              onRetry: () =>
                  ref.invalidate(pendingWorkspaceInvitationsProvider),
            ),
            data: _pendingCard,
          ),
        ],
      ),
    );
  }

  Widget _inviteCard(WorkspaceDetail workspace) {
    final t = context.tokens;
    final i18n = ref.watch(i18nProvider);
    return _SectionCard(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          children: [
            TextField(
              controller: _target,
              enabled: !_submitting,
              decoration: InputDecoration(
                hintText: i18n.t('settings:team.targetPlaceholder'),
                prefixIcon: const Icon(Icons.person_add_alt_1_outlined),
              ),
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _invite(workspace),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<WorkspaceRole>(
                    initialValue: _inviteRole,
                    items: [WorkspaceRole.member, WorkspaceRole.admin]
                        .map(
                          (role) => DropdownMenuItem(
                            value: role,
                            child: Text(
                              i18n.t('settings:team.roles.${role.wire}'),
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: _submitting
                        ? null
                        : (role) => setState(
                            () => _inviteRole = role ?? WorkspaceRole.member,
                          ),
                  ),
                ),
                const SizedBox(width: 10),
                FilledButton(
                  onPressed: _submitting ? null : () => _invite(workspace),
                  style: FilledButton.styleFrom(
                    backgroundColor: t.ink,
                    foregroundColor: t.bg,
                  ),
                  child: Text(i18n.t('settings:team.invite')),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _membersCard(WorkspaceDetail workspace) {
    final i18n = ref.watch(i18nProvider);
    return _SectionCard(
      title: i18n.t('settings:team.members'),
      child: Column(
        children: [
          for (final (index, member) in workspace.members.indexed)
            _MemberRow(
              member: member,
              canManage: workspace.role.canManage,
              last: index == workspace.members.length - 1,
              onRole: (role) => _changeRole(workspace, member, role),
              onRemove: () => _remove(workspace, member),
            ),
        ],
      ),
    );
  }

  Widget _pendingCard(List<WorkspaceInvitation> invitations) {
    final t = context.tokens;
    final i18n = ref.watch(i18nProvider);
    return _SectionCard(
      title: i18n.t('settings:team.pending'),
      child: invitations.isEmpty
          ? Padding(
              padding: const EdgeInsets.all(14),
              child: Text(
                i18n.t('settings:team.pendingEmpty'),
                style: TextStyle(fontSize: FontSizes.sm, color: t.n600),
              ),
            )
          : Column(
              children: [
                for (final (index, item) in invitations.indexed)
                  ListTile(
                    title: Text(item.workspaceName ?? item.workspaceId),
                    subtitle: Text(item.target),
                    trailing: Text(
                      i18n.t('settings:team.roles.${item.role.wire}'),
                      style: TextStyle(fontSize: FontSizes.xs, color: t.n600),
                    ),
                    shape: index == invitations.length - 1
                        ? null
                        : Border(bottom: BorderSide(color: t.hair)),
                  ),
              ],
            ),
    );
  }

  Future<void> _invite(WorkspaceDetail workspace) async {
    final target = _target.text.trim();
    if (target.isEmpty) return;
    setState(() => _submitting = true);
    try {
      final invitation = await ref
          .read(workspaceApiProvider)
          .inviteMember(
            workspaceId: workspace.summary.id,
            target: target,
            role: _inviteRole,
          );
      final token = invitation.token ?? '';
      final url = '${Env.webBase}/invite/${Uri.encodeComponent(token)}';
      await Clipboard.setData(ClipboardData(text: url));
      if (!mounted) return;
      setState(() {
        _target.clear();
        _inviteUrl = url;
      });
      ref
          .read(toastProvider.notifier)
          .success(
            ref
                .read(i18nProvider)
                .t('settings:team.inviteCreated', vars: {'url': url}),
          );
      ref.invalidate(currentWorkspaceDetailProvider);
    } catch (error) {
      ref
          .read(toastProvider.notifier)
          .error(errorText(ref.read(i18nProvider), error));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _changeRole(
    WorkspaceDetail workspace,
    WorkspaceMember member,
    WorkspaceRole role,
  ) async {
    try {
      await ref
          .read(workspaceApiProvider)
          .changeMemberRole(
            workspaceId: workspace.summary.id,
            userId: member.userId,
            role: role,
          );
      ref.invalidate(currentWorkspaceDetailProvider);
    } catch (error) {
      ref
          .read(toastProvider.notifier)
          .error(errorText(ref.read(i18nProvider), error));
    }
  }

  Future<void> _remove(
    WorkspaceDetail workspace,
    WorkspaceMember member,
  ) async {
    try {
      await ref
          .read(workspaceApiProvider)
          .removeMember(
            workspaceId: workspace.summary.id,
            userId: member.userId,
          );
      ref.invalidate(currentWorkspaceDetailProvider);
    } catch (error) {
      ref
          .read(toastProvider.notifier)
          .error(errorText(ref.read(i18nProvider), error));
    }
  }

  Future<void> _refresh() async {
    ref.invalidate(currentWorkspaceDetailProvider);
    ref.invalidate(pendingWorkspaceInvitationsProvider);
    await Future.wait([
      ref.read(currentWorkspaceDetailProvider.future),
      ref.read(pendingWorkspaceInvitationsProvider.future),
    ]);
  }
}

class _MemberRow extends ConsumerWidget {
  const _MemberRow({
    required this.member,
    required this.canManage,
    required this.last,
    required this.onRole,
    required this.onRemove,
  });

  final WorkspaceMember member;
  final bool canManage;
  final bool last;
  final ValueChanged<WorkspaceRole> onRole;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = context.tokens;
    final i18n = ref.watch(i18nProvider);
    final editable = canManage && member.role != WorkspaceRole.owner;
    final joined = MaterialLocalizations.of(
      context,
    ).formatShortDate(member.createdAt.toLocal());
    return Container(
      decoration: BoxDecoration(
        border: last ? null : Border(bottom: BorderSide(color: t.hair)),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
        title: Text(
          member.username,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              member.email ?? i18n.t('settings:account.emailNone'),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            Text(
              i18n.t('settings:team.joined', vars: {'date': joined}),
              style: TextStyle(fontSize: FontSizes.xs2, color: t.n500),
            ),
          ],
        ),
        trailing: editable
            ? PopupMenuButton<String>(
                icon: Icon(Icons.more_horiz, color: t.n600),
                onSelected: (value) {
                  if (value == 'remove') {
                    onRemove();
                  } else {
                    onRole(workspaceRoleFrom(value));
                  }
                },
                itemBuilder: (_) => [
                  for (final role in [
                    WorkspaceRole.member,
                    WorkspaceRole.admin,
                  ])
                    PopupMenuItem(
                      value: role.wire,
                      child: Text(i18n.t('settings:team.roles.${role.wire}')),
                    ),
                  PopupMenuItem(
                    value: 'remove',
                    child: Text(
                      i18n.t('settings:team.remove'),
                      style: TextStyle(color: t.danger),
                    ),
                  ),
                ],
              )
            : _RolePill(role: member.role),
      ),
    );
  }
}

class _RolePill extends ConsumerWidget {
  const _RolePill({required this.role});

  final WorkspaceRole role;

  @override
  Widget build(BuildContext context, WidgetRef ref) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
    decoration: BoxDecoration(
      color: context.tokens.n100,
      borderRadius: BorderRadius.circular(Radii.full),
    ),
    child: Text(
      ref.watch(i18nProvider).t('settings:team.roles.${role.wire}'),
      style: TextStyle(fontSize: FontSizes.xs, color: context.tokens.n700),
    ),
  );
}

class _InviteLink extends ConsumerWidget {
  const _InviteLink({required this.url});

  final String url;

  @override
  Widget build(BuildContext context, WidgetRef ref) => _SectionCard(
    title: ref.watch(i18nProvider).t('settings:team.inviteLink'),
    child: ListTile(
      title: SelectableText(
        url,
        style: const TextStyle(fontSize: FontSizes.xs),
      ),
      trailing: IconButton(
        icon: const Icon(Icons.copy_outlined),
        onPressed: () => Clipboard.setData(ClipboardData(text: url)),
      ),
    ),
  );
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({this.title, required this.child});

  final String? title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final t = context.tokens;
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: t.card,
        border: Border.all(color: t.hair),
        borderRadius: BorderRadius.circular(Radii.xl),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (title != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
              decoration: BoxDecoration(
                border: Border(bottom: BorderSide(color: t.hair)),
              ),
              child: Text(
                title!,
                style: TextStyle(
                  fontSize: FontSizes.sm,
                  fontWeight: FontWeight.w500,
                  color: t.ink,
                ),
              ),
            ),
          child,
        ],
      ),
    );
  }
}

class _LoadingCard extends StatelessWidget {
  const _LoadingCard();

  @override
  Widget build(BuildContext context) => const Padding(
    padding: EdgeInsets.all(32),
    child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
  );
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(16),
    child: Column(
      children: [
        Text(message, textAlign: TextAlign.center),
        const SizedBox(height: 10),
        OutlinedButton(onPressed: onRetry, child: const Icon(Icons.refresh)),
      ],
    ),
  );
}
