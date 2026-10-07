"""A photo must not become a match."""
import unittest

import numpy as np

from backend.app import engine


class LivenessTests(unittest.TestCase):
    def setUp(self):
        self._detect = engine.detect_faces
        self._live = engine.face_is_live
        self._embed = engine.embed_bgr

    def tearDown(self):
        engine.detect_faces = self._detect
        engine.face_is_live = self._live
        engine.embed_bgr = self._embed

    def frame(self):
        return np.zeros((80, 80, 3), dtype=np.uint8)

    def test_photo_is_not_a_match(self):
        engine.detect_faces = lambda model, frame: [(10, 10, 50, 60)]
        engine.face_is_live = lambda frame, box: (False, 0.91)
        called = {"embed": 0}

        def embed(crop):
            called["embed"] += 1
            return np.ones(4, dtype=np.float32)

        engine.embed_bgr = embed
        gallery = {"1": {"name": "Rathanak", "embeddings": [np.ones(4, dtype=np.float32)]}}

        faces = engine.recognize_frame(None, self.frame(), gallery)

        self.assertEqual(len(faces), 1)
        self.assertTrue(faces[0]["spoof"])
        self.assertFalse(faces[0]["matched"])
        self.assertIsNone(faces[0]["person_id"])
        self.assertEqual(called["embed"], 0)

    def test_live_face_can_match(self):
        vector = np.ones(4, dtype=np.float32)
        engine.detect_faces = lambda model, frame: [(10, 10, 50, 60)]
        engine.face_is_live = lambda frame, box: (True, 0.8)
        engine.embed_bgr = lambda crop: vector
        gallery = {"1": {"name": "Rathanak", "embeddings": [vector]}}

        faces = engine.recognize_frame(None, self.frame(), gallery)

        self.assertFalse(faces[0]["spoof"])
        self.assertTrue(faces[0]["matched"])
        self.assertEqual(faces[0]["person_id"], "1")
        self.assertEqual(faces[0]["name"], "Rathanak")


if __name__ == "__main__":
    unittest.main()
