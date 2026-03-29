"""
Test module for the utilities module.

This module contains unit tests for all functions in the utilities module.
"""

import unittest
from utilities import greet, calculate_sum, is_palindrome


class TestUtilities(unittest.TestCase):
    """Test cases for the utilities module."""
    
    def setUp(self):
        """Set up test fixtures that are reused across multiple test methods."""
        pass
    
    # Tests for greet() function
    def test_greet_normal_name(self):
        """Test greeting a normal name."""
        self.assertEqual(greet("Alice"), "Hello, Alice!")
    
    def test_greet_empty_string(self):
        """Test greeting with empty string."""
        self.assertEqual(greet(""), "Hello!")
    
    def test_greet_single_character(self):
        """Test greeting a single character."""
        self.assertEqual(greet("B"), "Hello, B!")
    
    def test_greet_with_spaces(self):
        """Test greeting a name with spaces."""
        self.assertEqual(greet("John Doe"), "Hello, John Doe!")
    
    def test_greet_type_error(self):
        """Test that greet raises TypeError for non-string input."""
        with self.assertRaises(TypeError):
            greet(123)
        with self.assertRaises(TypeError):
            greet(None)
        with self.assertRaises(TypeError):
            greet(["Alice"])
    
    # Tests for calculate_sum() function
    def test_calculate_sum_integers(self):
        """Test sum calculation with integers."""
        self.assertEqual(calculate_sum([1, 2, 3, 4, 5]), 15)
    
    def test_calculate_sum_floats(self):
        """Test sum calculation with floats."""
        self.assertAlmostEqual(calculate_sum([1.5, 2.5, 3.0]), 7.0)
    
    def test_calculate_sum_mixed_numbers(self):
        """Test sum calculation with mixed integer and float numbers."""
        self.assertAlmostEqual(calculate_sum([1, 2.5, 3, 4.5]), 11.0)
    
    def test_calculate_sum_single_element(self):
        """Test sum calculation with a single element list."""
        self.assertEqual(calculate_sum([42]), 42)
    
    def test_calculate_sum_negative_numbers(self):
        """Test sum calculation with negative numbers."""
        self.assertEqual(calculate_sum([-1, -2, -3]), -6)
    
    def test_calculate_sum_mixed_positive_negative(self):
        """Test sum calculation with mixed positive and negative numbers."""
        self.assertEqual(calculate_sum([-5, 10, -3, 8]), 10)
    
    def test_calculate_sum_type_error_not_list(self):
        """Test that calculate_sum raises TypeError for non-list input."""
        with self.assertRaises(TypeError):
            calculate_sum("not a list")
        with self.assertRaises(TypeError):
            calculate_sum((1, 2, 3))
        with self.assertRaises(TypeError):
            calculate_sum(123)
    
    def test_calculate_sum_type_error_non_numeric(self):
        """Test that calculate_sum raises TypeError for list with non-numeric elements."""
        with self.assertRaises(TypeError):
            calculate_sum([1, 2, "three", 4])
        with self.assertRaises(TypeError):
            calculate_sum([1, 2.5, None, 4])
    
    def test_calculate_sum_empty_list(self):
        """Test that calculate_sum raises ValueError for empty list."""
        with self.assertRaises(ValueError):
            calculate_sum([])
    
    # Tests for is_palindrome() function
    def test_is_palindrome_simple_palindrome(self):
        """Test simple palindrome detection."""
        self.assertTrue(is_palindrome("racecar"))
        self.assertTrue(is_palindrome("level"))
        self.assertTrue(is_palindrome("noon"))
    
    def test_is_palindrome_not_palindrome(self):
        """Test non-palindrome detection."""
        self.assertFalse(is_palindrome("hello"))
        self.assertFalse(is_palindrome("python"))
        self.assertFalse(is_palindrome("algorithm"))
    
    def test_is_palindrome_case_insensitive(self):
        """Test that palindrome detection is case-insensitive."""
        self.assertTrue(is_palindrome("RaceCar"))
        self.assertTrue(is_palindrome("LEVEl"))
    
    def test_is_palindrome_with_spaces(self):
        """Test palindrome detection with spaces."""
        self.assertTrue(is_palindrome("a man a plan a canal panama"))
        self.assertTrue(is_palindrome("was it a cat I saw"))
    
    def test_is_palindrome_with_punctuation(self):
        """Test palindrome detection with punctuation."""
        self.assertTrue(is_palindrome("A man, a plan, a canal: Panama!"))
        self.assertTrue(is_palindrome("Madam, I'm Adam"))
    
    def test_is_palindrome_empty_string(self):
        """Test that empty string is considered a palindrome."""
        self.assertTrue(is_palindrome(""))
    
    def test_is_palindrome_single_character(self):
        """Test that single character is considered a palindrome."""
        self.assertTrue(is_palindrome("a"))
        self.assertTrue(is_palindrome("Z"))
        self.assertTrue(is_palindrome("5"))
    
    def test_is_palindrome_numbers_only(self):
        """Test palindrome detection with numbers only."""
        self.assertTrue(is_palindrome("12321"))
        self.assertTrue(is_palindrome("9009"))
        self.assertFalse(is_palindrome("12345"))
    
    def test_is_palindrome_alphanumeric(self):
        """Test palindrome detection with alphanumeric characters."""
        self.assertTrue(is_palindrome("a1b2b1a"))
        self.assertFalse(is_palindrome("abc123"))
    
    def test_is_palindrome_type_error(self):
        """Test that is_palindrome raises TypeError for non-string input."""
        with self.assertRaises(TypeError):
            is_palindrome(123)
        with self.assertRaises(TypeError):
            is_palindrome(None)
        with self.assertRaises(TypeError):
            is_palindrome(["racecar"])


class TestUtilitiesEdgeCases(unittest.TestCase):
    """Additional test cases for edge cases and boundary conditions."""
    
    def test_greet_unicode(self):
        """Test greeting with unicode characters."""
        self.assertEqual(greet("José"), "Hello, José!")
        self.assertEqual(greet("中文字符"), "Hello, 中文字符!")
    
    def test_calculate_sum_large_numbers(self):
        """Test sum calculation with large numbers."""
        self.assertEqual(calculate_sum([1000000, 2000000, 3000000]), 6000000)
    
    def test_calculate_sum_very_small_numbers(self):
        """Test sum calculation with very small numbers."""
        self.assertAlmostEqual(calculate_sum([0.001, 0.002, 0.003]), 0.006, places=6)
    
    def test_is_palindrome_unicode(self):
        """Test palindrome detection with unicode characters."""
        # Note: Unicode palindromes are tricky due to normalization
        # This test focuses on basic unicode support
        self.assertTrue(is_palindrome("ñ"))
        self.assertTrue(is_palindrome("ü"))


if __name__ == "__main__":
    # Run the tests
    unittest.main(verbosity=2)