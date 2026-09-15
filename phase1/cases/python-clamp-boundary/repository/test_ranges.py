import unittest

from ranges import clamp


class ClampTest(unittest.TestCase):
    def test_below_minimum(self) -> None:
        self.assertEqual(clamp(-4, 0, 10), 0)

    def test_inside_range(self) -> None:
        self.assertEqual(clamp(4, 0, 10), 4)

    def test_above_maximum(self) -> None:
        self.assertEqual(clamp(14, 0, 10), 10)


if __name__ == "__main__":
    unittest.main()
