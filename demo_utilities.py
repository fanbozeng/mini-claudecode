#!/usr/bin/env python3
"""
Demonstration script for the utilities module.

This script shows how to use the functions in the utilities module.
"""

from utilities import greet, calculate_sum, is_palindrome


def main():
    """Main function to demonstrate the utilities module."""
    print("=== Utilities Module Demo ===\n")
    
    # Demonstrate greet function
    print("1. Greet Function Demo:")
    print(f"   {greet('Alice')}")
    print(f"   {greet('Bob')}")
    print(f"   {greet('')}")
    print()
    
    # Demonstrate calculate_sum function
    print("2. Calculate Sum Function Demo:")
    numbers = [1, 2, 3, 4, 5]
    print(f"   Sum of {numbers}: {calculate_sum(numbers)}")
    
    float_numbers = [1.5, 2.5, 3.0]
    print(f"   Sum of {float_numbers}: {calculate_sum(float_numbers)}")
    
    mixed_numbers = [10, -5, 7.5, -2.5]
    print(f"   Sum of {mixed_numbers}: {calculate_sum(mixed_numbers)}")
    print()
    
    # Demonstrate is_palindrome function
    print("3. Is Palindrome Function Demo:")
    test_strings = [
        "racecar",
        "hello",
        "A man a plan a canal Panama",
        "Was it a cat I saw?",
        "python"
    ]
    
    for test_string in test_strings:
        result = is_palindrome(test_string)
        print(f"   '{test_string}' is palindrome: {result}")
    print()
    
    print("Demo completed! Check out test_utilities.py for comprehensive testing.")


if __name__ == "__main__":
    main()