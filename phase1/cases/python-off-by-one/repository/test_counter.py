import unittest

from counter import next_value


class CounterTest(unittest.TestCase):
    def test_next_value(self) -> None:
        self.assertEqual(next_value(4), 5)


if __name__ == "__main__":
    unittest.main()
