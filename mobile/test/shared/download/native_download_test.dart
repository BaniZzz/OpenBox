import 'package:bossip_mobile/shared/download/native_download.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('nativeDownloadFileName', () {
    test('keeps only the final path component', () {
      expect(nativeDownloadFileName('../../reports/final.pdf'), 'final.pdf');
      expect(nativeDownloadFileName(r'C:\reports\final.pdf'), 'final.pdf');
    });

    test('replaces characters rejected by native document providers', () {
      expect(nativeDownloadFileName('a:b?c.pdf'), 'a_b_c.pdf');
    });

    test('uses a safe fallback for empty and traversal names', () {
      expect(nativeDownloadFileName(''), 'download');
      expect(nativeDownloadFileName('..'), 'download');
    });

    test('bounds names without dropping the extension suffix', () {
      final name = '${List.filled(240, 'a').join()}.zip';
      final safe = nativeDownloadFileName(name);
      expect(safe.length, 180);
      expect(safe.endsWith('.zip'), isTrue);
    });
  });
}
