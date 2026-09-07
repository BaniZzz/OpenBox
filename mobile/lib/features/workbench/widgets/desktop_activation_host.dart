import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/api/desktop_api.dart';
import '../../../shared/api/providers.dart';
import '../../../shared/appearance/tokens.dart';
import '../../../shared/config/env.dart';
import '../../../shared/i18n/i18n.dart';
import '../../../shared/models/desktop.dart';

/// Mounted by app composition above every authenticated route, including
/// billing. Dismissing it never cancels the durable server activation.
class DesktopActivationHost extends ConsumerStatefulWidget {
  const DesktopActivationHost({
    super.key,
    required this.scope,
    required this.workspaceName,
    required this.canManage,
    required this.child,
  });

  final DesktopScope scope;
  final String workspaceName;
  final bool canManage;
  final Widget child;

  @override
  ConsumerState<DesktopActivationHost> createState() =>
      _DesktopActivationHostState();
}

class _DesktopActivationHostState extends ConsumerState<DesktopActivationHost>
    with WidgetsBindingObserver {
  String _dismissed = '';
  bool _retrying = false;
  bool _retryFailed = false;
  DesktopStatus? _lastStatus;

  String get _storageKey =>
      'openbox:desktop-ready:${jsonEncode([Env.apiBase, widget.scope.userId, widget.scope.workspaceId])}';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      setState(() => _dismissed = '');
      ref.invalidate(desktopStatusProvider(widget.scope));
    }
  }

  void _dismiss(DesktopStatus status) {
    final id = status.activation?.requestId;
    setState(() => _dismissed = '$id:${status.ready}');
    if (status.ready && id != null) {
      unawaited(ref.read(prefsProvider).setString(_storageKey, id));
    }
  }

  Future<void> _retry() async {
    if (_retrying ||
        !widget.canManage ||
        !(_lastStatus?.hasAccess ?? false) ||
        _lastStatus?.activation?.canRetry != true) {
      return;
    }
    setState(() {
      _retrying = true;
      _retryFailed = false;
    });
    try {
      await ref.read(desktopApiProvider).retry(widget.scope);
    } catch (_) {
      if (mounted) setState(() => _retryFailed = true);
    } finally {
      if (mounted) {
        setState(() => _retrying = false);
        ref.invalidate(desktopStatusProvider(widget.scope));
      }
    }
  }

  @override
  Widget build(BuildContext context) =>
      Overlay.wrap(child: _buildContent(context));

  Widget _buildContent(BuildContext context) {
    // MaterialApp.builder places this host above the routed Navigator. Its
    // global controls need their own Overlay (e.g. IconButton's Tooltip).
    final query = ref.watch(desktopStatusProvider(widget.scope));
    if (query.valueOrNull != null) _lastStatus = query.valueOrNull;
    final status = _lastStatus;
    if (status == null || !status.hasActivation) {
      // Keep the routed child at the same element path when the dialog opens
      // or closes; otherwise a Navigator/WebView could be remounted.
      return Stack(fit: StackFit.expand, children: [widget.child]);
    }
    final requestId = status.activation!.requestId;
    final acknowledged =
        status.ready &&
        ref.read(prefsProvider).getString(_storageKey) == requestId;
    final open = !acknowledged && _dismissed != '$requestId:${status.ready}';
    final i18n = ref.watch(i18nProvider);
    final t = context.tokens;
    return Stack(
      fit: StackFit.expand,
      children: [
        widget.child,
        if (!open && !status.ready)
          Positioned(
            left: 20,
            right: 20,
            bottom: 16,
            child: SafeArea(
              child: Center(
                child: FilledButton.icon(
                  key: const Key('desktop-progress-open'),
                  onPressed: () => setState(() => _dismissed = ''),
                  icon: const Icon(Icons.desktop_windows_outlined, size: 18),
                  label: Text(i18n.t('workbench:activation.viewProgress')),
                ),
              ),
            ),
          ),
        if (open) ...[
          ModalBarrier(
            color: t.n900.withValues(alpha: 0.4),
            dismissible: true,
            onDismiss: () => _dismiss(status),
            semanticsLabel: i18n.t('workbench:activation.close'),
          ),
          Dialog(
            key: const Key('desktop-activation-dialog'),
            backgroundColor: t.card,
            insetPadding: const EdgeInsets.symmetric(
              horizontal: 20,
              vertical: 32,
            ),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          status.ready
                              ? Icons.check_circle_outline
                              : Icons.desktop_windows_outlined,
                          size: 32,
                          color: t.a700,
                        ),
                        const Spacer(),
                        IconButton(
                          tooltip: i18n.t('workbench:activation.close'),
                          onPressed: () => _dismiss(status),
                          icon: const Icon(Icons.close, size: 20),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      i18n.t(
                        'workbench:activation.${status.ready
                            ? 'ready'
                            : status.needsAttention
                            ? 'attention'
                            : 'title'}',
                      ),
                      style: TextStyle(
                        color: t.ink,
                        fontSize: 20,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(widget.workspaceName, style: TextStyle(color: t.n500)),
                    const SizedBox(height: 12),
                    Text(
                      i18n.t(
                        'workbench:activation.${status.ready ? 'readyHint' : 'hint'}',
                      ),
                      style: TextStyle(color: t.n600, height: 1.5),
                    ),
                    const SizedBox(height: 20),
                    for (final (index, step) in [
                      'paid',
                      'assigning',
                      'starting',
                      'connecting',
                      'ready',
                    ].indexed)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 14),
                        child: Row(
                          children: [
                            SizedBox(
                              width: 24,
                              height: 24,
                              child:
                                  status.ready ||
                                      index < status.progressPosition
                                  ? Icon(
                                      Icons.check_circle,
                                      color: t.a700,
                                      size: 24,
                                    )
                                  : index == status.progressPosition &&
                                        !status.needsAttention
                                  ? const Padding(
                                      padding: EdgeInsets.all(4),
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                      ),
                                    )
                                  : Center(
                                      child: Text(
                                        '${index + 1}',
                                        style: TextStyle(color: t.n500),
                                      ),
                                    ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                i18n.t('workbench:activation.steps.$step'),
                                style: TextStyle(color: t.n700),
                              ),
                            ),
                          ],
                        ),
                      ),
                    if (query.hasError ||
                        status.needsAttention ||
                        status.activation?.state == 'retrying')
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Text(
                          i18n.t(
                            'workbench:activation.${query.hasError
                                ? 'reconnecting'
                                : status.needsAttention
                                ? 'attentionHint'
                                : 'retrying'}',
                          ),
                          style: TextStyle(color: t.n600, height: 1.5),
                        ),
                      ),
                    if (_retryFailed)
                      Text(
                        i18n.t('workbench:activation.retryFailed'),
                        style: TextStyle(color: t.dangerInk),
                      ),
                    Wrap(
                      alignment: WrapAlignment.end,
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        if (status.activation?.canRetry == true &&
                            widget.canManage)
                          OutlinedButton(
                            onPressed: _retrying ? null : _retry,
                            child: Text(i18n.t('workbench:activation.retry')),
                          ),
                        FilledButton(
                          onPressed: () => _dismiss(status),
                          child: Text(
                            i18n.t(
                              'workbench:activation.${status.ready ? 'done' : 'continueChat'}',
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ],
    );
  }
}
