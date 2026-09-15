import unittest

from pricing import discounted_price


class PricingTest(unittest.TestCase):
    def test_percentage_discount(self) -> None:
        self.assertEqual(discounted_price(50, 20), 40)


if __name__ == "__main__":
    unittest.main()
