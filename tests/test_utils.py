"""
Unit tests for mypackage.utils module.
"""

import unittest
from mypackage.utils import add_numbers, multiply_numbers, greet, is_even


class TestUtils(unittest.TestCase):
    
    def test_add_numbers_positive(self):
        """Test adding two positive numbers."""
        self.assertEqual(add_numbers(2, 3), 5)
        self.assertEqual(add_numbers(10, 20), 30)
    
    def test_add_numbers_negative(self):
        """Test adding numbers including negative values."""
        self.assertEqual(add_numbers(-5, 3), -2)
        self.assertEqual(add_numbers(-10, -20), -30)
    
    def test_add_numbers_floats(self):
        """Test adding floating point numbers."""
        self.assertAlmostEqual(add_numbers(2.5, 3.7), 6.2)
        self.assertAlmostEqual(add_numbers(0.1, 0.2), 0.3, places=6)
    
    def test_multiply_numbers_positive(self):
        """Test multiplying two positive numbers."""
        self.assertEqual(multiply_numbers(4, 5), 20)
        self.assertEqual(multiply_numbers(3, 7), 21)
    
    def test_multiply_numbers_with_zero(self):
        """Test multiplying by zero."""
        self.assertEqual(multiply_numbers(10, 0), 0)
        self.assertEqual(multiply_numbers(0, 100), 0)
    
    def test_multiply_numbers_negative(self):
        """Test multiplying numbers including negative values."""
        self.assertEqual(multiply_numbers(-5, 3), -15)
        self.assertEqual(multiply_numbers(-4, -6), 24)
    
    def test_greet(self):
        """Test the greet function."""
        self.assertEqual(greet("Alice"), "Hello, Alice!")
        self.assertEqual(greet("Bob"), "Hello, Bob!")
        self.assertEqual(greet(""), "Hello, !")
    
    def test_is_even_true(self):
        """Test checking if number is even (True cases)."""
        self.assertTrue(is_even(2))
        self.assertTrue(is_even(0))
        self.assertTrue(is_even(100))
        self.assertTrue(is_even(-4))
    
    def test_is_even_false(self):
        """Test checking if number is even (False cases)."""
        self.assertFalse(is_even(1))
        self.assertFalse(is_even(3))
        self.assertFalse(is_even(99))
        self.assertFalse(is_even(-7))


if __name__ == '__main__':
    unittest.main()