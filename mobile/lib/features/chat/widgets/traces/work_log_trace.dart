import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../shared/appearance/tokens.dart';
import '../../../../shared/appearance/type_scale.dart';
import '../../../../shared/i18n/i18n.dart';
import '../../../../shared/widgets/shimmer_text.dart';
import '../../utils/content_view.dart';
import '../attachment_gallery.dart';
import '../markdown_view.dart';

/// Work log (web `WorkLogTrace`): tool-step narration and working evidence,
/// in the order they happened, always visible in the answer's reading column.
///
/// Computer-use produces a screenshot per action; keeping every one of them
/// turns the log into a flip-book, so only the first, middle and last frames
/// are kept and the count of what was dropped is stated rather than implied.
class WorkLogTrace extends ConsumerWidget {
  const WorkLogTrace({super.key, required this.events, required this.active});

  final List<WorkEvent> events;
  final bool active;

  static const _maxComputerCheckpoints = 3;

  Set<String> _keyComputerIds() {
    final screenshots = events
        .whereType<ArtifactGroup>()
        .where((g) => g.artifactKind == 'computer_screenshot')
        .toList();
    if (screenshots.length <= _maxComputerCheckpoints) {
      return {for (final item in screenshots) item.id};
    }
    final middle = ((screenshots.length - 1) / 2).round();
    return {screenshots.first.id, screenshots[middle].id, screenshots.last.id};
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (events.isEmpty) return const SizedBox.shrink();
    final t = context.tokens;
    final i18n = ref.watch(i18nProvider);
    final keyIds = _keyComputerIds();
    final displayed = events
        .where(
          (event) =>
              event is! ArtifactGroup ||
              event.artifactKind != 'computer_screenshot' ||
              keyIds.contains(event.id),
        )
        .toList();
    final hidden = events.length - displayed.length;

    final title = active
        ? i18n.t('chat:trace.work.titleActive')
        : i18n.t('chat:trace.work.titleDone');

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Semantics(
        label: title,
        container: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: ShimmerText(
                title,
                enabled: active,
                style: TextStyle(
                  fontSize: FontSizes.xs,
                  fontWeight: FontWeight.w500,
                  color: t.n600,
                ),
              ),
            ),
            for (final (index, event) in displayed.indexed)
              _WorkRow(
                event: event,
                isFirst: index == 0,
                isLast: index == displayed.length - 1,
                streaming: active,
              ),
            if (hidden > 0)
              Padding(
                padding: EdgeInsets.only(
                  top: 4,
                  left: displayed.isEmpty ? 0 : 22,
                ),
                child: Text(
                  i18n.t('chat:trace.work.omitted', count: hidden),
                  style: TextStyle(fontSize: FontSizes.xs2, color: t.n600),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// One entry with the connector rail the tool chain uses, so the two traces
/// read as the same kind of timeline.
class _WorkRow extends ConsumerWidget {
  const _WorkRow({
    required this.event,
    required this.isFirst,
    required this.isLast,
    required this.streaming,
  });

  final WorkEvent event;
  final bool isFirst;
  final bool isLast;
  final bool streaming;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = context.tokens;
    final i18n = ref.watch(i18nProvider);
    // `IntrinsicHeight` cannot contain AttachmentGallery's shrink-wrapped
    // GridView. It asks the viewport for an intrinsic height, which Flutter
    // deliberately rejects and leaves the whole historical transcript blank.
    // Let the real content size this Stack, then overlay the rail into the
    // resulting height without making any intrinsic-dimension queries.
    return Stack(
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 22, bottom: 8),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 13),
            child: switch (event) {
              WorkNarration(:final text) => MarkdownView(
                text,
                variant: MarkdownVariant.thinking,
                streaming: streaming,
              ),
              final ArtifactGroup group => Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    group.sourceTool?.title?.trim().isNotEmpty == true
                        ? group.sourceTool!.title!
                        : group.label ?? i18n.t('chat:trace.work.checkpoint'),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: FontSizes.xs,
                      fontWeight: FontWeight.w500,
                      color: t.n700,
                    ),
                  ),
                  const SizedBox(height: 5),
                  AttachmentGallery(
                    parts: group.parts.where(isGalleryMedia).toList(),
                    compact: true,
                  ),
                ],
              ),
            },
          ),
        ),
        Positioned(
          left: 0,
          top: 0,
          bottom: 0,
          width: 14,
          child: Column(
            children: [
              SizedBox(
                height: 7,
                child: isFirst
                    ? null
                    : Center(child: Container(width: 1, color: t.hair)),
              ),
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: t.n500,
                  shape: BoxShape.circle,
                ),
              ),
              if (!isLast)
                Expanded(
                  child: Center(child: Container(width: 1, color: t.hair)),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
