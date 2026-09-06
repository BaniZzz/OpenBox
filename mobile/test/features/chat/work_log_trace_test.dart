import 'dart:async';

import 'package:bossip_mobile/features/chat/api/assets_api.dart';
import 'package:bossip_mobile/features/chat/utils/content_view.dart';
import 'package:bossip_mobile/features/chat/widgets/traces/work_log_trace.dart';
import 'package:bossip_mobile/shared/appearance/tokens.dart';
import 'package:bossip_mobile/shared/i18n/i18n.dart';
import 'package:bossip_mobile/shared/models/message_part.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

I18nBundle _bundle() => I18nBundle({
  'en-US': {
    'chat': {
      'trace': {
        'work': {
          'titleDone': 'Work log',
          'titleActive': 'Working',
          'checkpoint': 'Checkpoint',
          'omitted_other': '{{count}} omitted',
        },
      },
    },
  },
});

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'renders historical screenshot evidence inside the scrolling transcript',
    (tester) async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final unresolvedAsset = Completer<AssetUrl>();
      final evidence = ArtifactGroup(
        id: 'computer-checkpoint',
        order: 0,
        artifactKind: 'computer_screenshot',
        role: 'evidence',
        label: 'Browser checkpoint',
        caption: null,
        ordinal: null,
        revision: null,
        metadata: const {},
        sourceTool: null,
        parts: const [
          FilePart(
            id: 'screenshot-1',
            path: 'checkpoint.png',
            mimeType: 'image/png',
            assetId: 'asset-1',
          ),
        ],
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            i18nProvider.overrideWith(() => I18nController(_bundle(), prefs)),
            assetUrlProvider.overrideWith(
              (ref, assetId) => unresolvedAsset.future,
            ),
          ],
          child: MaterialApp(
            theme: ThemeData(
              extensions: [
                BossipTokens.resolve(
                  BossipThemeName.default_,
                  Brightness.light,
                ),
              ],
            ),
            home: Scaffold(
              body: SizedBox(
                width: 390,
                height: 700,
                child: ListView(
                  children: [
                    WorkLogTrace(events: [evidence], active: false),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pump();

      expect(tester.takeException(), isNull);
      expect(find.text('Work log'), findsOneWidget);
      expect(find.text('Browser checkpoint'), findsOneWidget);
      expect(find.byType(GridView), findsOneWidget);
    },
  );
}
