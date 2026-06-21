from __future__ import annotations

import unittest

from app import response_for_path


class ResponseForPathTests(unittest.TestCase):
    def test_home(self) -> None:
        status, payload = response_for_path("/")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"message": "tiny app"})

    def test_health(self) -> None:
        status, payload = response_for_path("/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"status": "ok"})

    def test_not_found(self) -> None:
        status, payload = response_for_path("/missing")
        self.assertEqual(status, 404)
        self.assertEqual(payload, {"error": "not found"})


if __name__ == "__main__":
    unittest.main()
