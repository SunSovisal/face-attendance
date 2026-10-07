"""A punch holds the person until they leave and the cooldown has passed."""
import unittest
from datetime import datetime, timedelta, timezone

from backend.app.config import settings
from backend.app.desk import (
    RELEASE_MISSES,
    claim_punch,
    clear_desk,
    complete_punch,
    match_band,
    note_seen,
    punch_blocked,
    release_claim,
)


class MatchBandTests(unittest.TestCase):
    def setUp(self):
        self.auto = settings.auto_match_threshold
        self.match = settings.match_threshold
        settings.auto_match_threshold = 0.40
        settings.match_threshold = 0.50

    def tearDown(self):
        settings.auto_match_threshold = self.auto
        settings.match_threshold = self.match

    def test_clear_match_is_sure_and_borderline_is_close(self):
        self.assertEqual(match_band(0.40), "sure")
        self.assertEqual(match_band(0.41), "close")

    def test_auto_threshold_cannot_be_looser_than_the_match(self):
        settings.auto_match_threshold = 0.60
        settings.match_threshold = 0.50
        self.assertEqual(match_band(0.50), "sure")
        self.assertEqual(match_band(0.51), "close")


class HoldTests(unittest.TestCase):
    def setUp(self):
        clear_desk()
        self.start = datetime(2026, 10, 6, 1, 0, tzinfo=timezone.utc)

    def tearDown(self):
        clear_desk()

    def test_a_second_punch_is_refused_until_the_first_finishes(self):
        self.assertTrue(claim_punch(2))
        self.assertFalse(claim_punch(2))
        release_claim(2)
        self.assertTrue(claim_punch(2))

    def test_standing_at_the_desk_does_not_release_the_hold(self):
        complete_punch(1, 45, now=self.start)
        moment = self.start
        for _ in range(30):
            moment += timedelta(seconds=2)
            note_seen({1}, now=moment)
        self.assertTrue(punch_blocked(1))
        for _ in range(RELEASE_MISSES):
            moment += timedelta(milliseconds=300)
            note_seen(set(), now=moment)
        self.assertFalse(punch_blocked(1))

    def test_a_camera_gap_after_the_cooldown_lets_them_punch_again(self):
        complete_punch(1, 45, now=self.start)
        note_seen({1}, now=self.start)
        note_seen(set(), now=self.start + timedelta(hours=16))
        self.assertFalse(punch_blocked(1))

    def test_a_camera_gap_during_the_cooldown_keeps_the_hold(self):
        complete_punch(1, 45, now=self.start)
        note_seen({1}, now=self.start)
        note_seen({1}, now=self.start + timedelta(seconds=10))
        self.assertTrue(punch_blocked(1))


if __name__ == "__main__":
    unittest.main()
