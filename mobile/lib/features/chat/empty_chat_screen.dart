import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../shared/api/api_error.dart';
import '../../shared/events/bus.dart';
import '../../shared/i18n/i18n.dart';
import '../../shared/router/paths.dart';
import '../../shared/utils/error_text.dart';
import '../../shared/widgets/toast.dart';
import 'api/chat_api.dart';
import 'state/chat_session_controller.dart';
import 'state/config_providers.dart';
import 'utils/reasoning.dart';
import 'widgets/composer/composer.dart';
import 'widgets/composer/resource_slot.dart';
import 'widgets/empty_state.dart';

const draftSessionKey = 'draft';

/// Empty chat (web `EmptyChatRoute`): greeting + suggestions + composer.
/// The first send creates the session, then navigates into it
/// (web `useStartChat`).
class EmptyChatScreen extends ConsumerStatefulWidget {
  const EmptyChatScreen({
    super.key,
    this.projectId,
    this.projectName,
    this.resources,
  });

  final String? projectId;
  final String? projectName;

  /// Resource centre, handed down by the app layer.
  final ComposerResourceSlot? resources;

  @override
  ConsumerState<EmptyChatScreen> createState() => _EmptyChatScreenState();
}

class _EmptyChatScreenState extends ConsumerState<EmptyChatScreen> {
  Future<void> _startChat(
    String text, [
    List<String> attachments = const [],
  ]) async {
    if (text.trim().isEmpty && attachments.isEmpty) return;
    String? createdSessionId;
    try {
      final model = ref.read(pickedModelProvider(draftSessionKey)) ?? '';
      final agent = ref.read(pickedAgentProvider(draftSessionKey)) ?? 'build';
      // The reasoning pick belongs to the model it was made against, and the
      // conversation stores it at birth (web `useStartChat`). Nothing is
      // carried onto the new session key: from there the persisted value is
      // what the picker restores.
      final config = ref.read(appConfigProvider).valueOrNull;
      final modelId = activeModelId(
        picked: model,
        defaultModel: config?.defaultModel,
      );
      final variant = resolveReasoning(
        model: config?.byId(modelId),
        pick: ref.read(
          pickedVariantProvider(reasoningKey(draftSessionKey, modelId)),
        ),
      ).value;
      final session = await ref
          .read(chatApiProvider)
          .createSession(
            projectId: widget.projectId,
            model: model,
            agent: agent,
            variant: variant,
          );
      createdSessionId = session.id;
      // Carry the draft picks onto the real session.
      ref.read(pickedModelProvider(session.id).notifier).state = model.isEmpty
          ? null
          : model;
      ref.read(pickedAgentProvider(session.id).notifier).state = agent;
      // The video pick too: it is made on the empty screen like the others,
      // and dropping it here silently generated the first shot with the
      // deployment default — a different model at a different price from the
      // one the person had selected.
      ref.read(pickedVideoProvider(session.id).notifier).state = ref.read(
        pickedVideoProvider(draftSessionKey),
      );
      await ref
          .read(chatSessionProvider(session.id).notifier)
          .send(text, attachments: attachments);
      ref.read(appEventBusProvider).emit('workspace.refresh');
      if (mounted) context.go(Paths.chat(session.id));
    } catch (e) {
      if (apiErrorOf(e)?.code == 'DESKTOP_NOT_READY') {
        ref.read(appEventBusProvider).emit('workbench.open', {
          'kind': 'desktop',
          'sessionId': ?createdSessionId,
        });
      }
      if (mounted) {
        ref
            .read(toastProvider.notifier)
            .error(errorText(ref.read(i18nProvider), e));
      }
      // Rethrow so the composer knows the send never happened and keeps the
      // draft. Swallowing it left an empty box that read as "sent".
      rethrow;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: ChatEmptyState(
            projectName: widget.projectName,
            // A suggestion tap has no draft to preserve, so the rethrow that
            // the composer relies on is nothing to act on here.
            onPick: (text) => unawaited(_startChat(text).catchError((_) {})),
          ),
        ),
        SafeArea(
          top: false,
          child: Composer(
            sessionKey: draftSessionKey,
            busy: false,
            resources: widget.resources,
            onSend: _startChat,
          ),
        ),
      ],
    );
  }
}
