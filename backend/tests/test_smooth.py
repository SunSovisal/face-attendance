"""Shown match distance should not tick on every frame."""
import unittest

from backend.app.routes.recognize import smooth_matches


def face(distance: float, person_id: int = 1, matched: bool = True) -> dict:
    return {"person_id": person_id, "distance": distance, "matched": matched, "name": "Rathanak"}


class SmoothTests(unittest.TestCase):
    def shown(self, history, distances, person_id=1, matched=True):
        latest = None
        for distance in distances:
            frame = [face(distance, person_id, matched)]
            smooth_matches(history, frame)
            latest = frame[0]["distance"]
        return latest

    def test_chatter_inside_the_band_settles(self):
        history = {}
        self.shown(history, [0.22, 0.38, 0.25, 0.41, 0.28, 0.36, 0.23, 0.39, 0.27, 0.34])
        settled = self.shown(history, [0.22, 0.38, 0.25, 0.41, 0.28])
        again = self.shown(history, [0.36, 0.23, 0.39, 0.27, 0.34])
        self.assertEqual(settled, again)

    def test_a_real_shift_still_moves_the_score(self):
        history = {}
        low = self.shown(history, [0.22] * 8)
        high = self.shown(history, [0.40] * 12)
        self.assertLess(low, high)

    def test_an_unmatched_frame_is_left_alone(self):
        history = {}
        frame = [face(0.62, person_id=None, matched=False)]
        frame[0]["person_id"] = None
        smooth_matches(history, frame)
        self.assertEqual(frame[0]["distance"], 0.62)
        self.assertEqual(history, {})

    def test_a_short_gap_keeps_the_running_score(self):
        history = {}
        self.shown(history, [0.30] * 6)
        smooth_matches(history, [])
        smooth_matches(history, [])
        held = self.shown(history, [0.30])
        fresh = {}
        restarted = self.shown(fresh, [0.40])
        self.assertNotEqual(held, restarted)


if __name__ == "__main__":
    unittest.main()
