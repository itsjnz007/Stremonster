import unittest

from app.core.torrent import Torrent


class SpeedCategoryTests(unittest.TestCase):
    def test_speed_category_accounts_for_quality(self) -> None:
        self.assertEqual(Torrent.get_speed_category(1200, "4k"), ("slow", 2))
        self.assertEqual(Torrent.get_speed_category(1200, "1080p"), ("medium", 3))
        self.assertEqual(Torrent.get_speed_category(1200, "720p"), ("ultra fast", 5))

    def test_quality_target_marks_headroom_as_fast(self) -> None:
        self.assertEqual(Torrent.get_speed_category(4500, "4k"), ("fast", 4))
        self.assertEqual(Torrent.get_speed_category(1, "4k"), ("very slow", 1))

    def test_unknown_quality_keeps_legacy_speed_categories(self) -> None:
        self.assertEqual(Torrent.get_speed_category(1200), ("ultra fast", 5))
        self.assertEqual(Torrent.get_speed_category(0), ("dead", 0))


if __name__ == "__main__":
    unittest.main()
