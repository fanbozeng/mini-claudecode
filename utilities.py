"""
Utilities module containing various helper functions.

This module provides a collection of utility functions for common tasks
such as string manipulation, mathematical calculations, and palindrome checking.
"""


def greet(name):
    """
    Generate a greeting message for the given name.

    Args:
        name (str): The name of the person to greet.

    Returns:
        str: A greeting message.

    Raises:
        TypeError: If name is not a string.

    Examples:
        >>> greet("Alice")
        'Hello, Alice!'
        >>> greet("")
        'Hello!'
    """
    if not isinstance(name, str):
        raise TypeError("Name must be a string")
    
    return f"Hello, {name}!" if name else "Hello!"


def calculate_sum(numbers):
    """
    Calculate the sum of a list of numbers.

    Args:
        numbers (list): A list of numeric values (int or float).

    Returns:
        float: The sum of all numbers in the list.

    Raises:
        TypeError: If numbers is not a list or contains non-numeric values.
        ValueError: If the list is empty.

    Examples:
        >>> calculate_sum([1, 2, 3, 4, 5])
        15
        >>> calculate_sum([1.5, 2.5, 3.0])
        7.0
        >>> calculate_sum([])
        Traceback (most recent call last):
        ValueError: Cannot calculate sum of empty list
    """
    if not isinstance(numbers, list):
        raise TypeError("Input must be a list")
    
    if not numbers:
        raise ValueError("Cannot calculate sum of empty list")
    
    try:
        return sum(numbers)
    except TypeError:
        raise TypeError("All elements in the list must be numeric")


def is_palindrome(text):
    """
    Check if a string is a palindrome (reads the same forwards and backwards).

    The function is case-insensitive and ignores spaces, punctuation, and special characters.

    Args:
        text (str): The string to check.

    Returns:
        bool: True if the string is a palindrome, False otherwise.

    Raises:
        TypeError: If text is not a string.

    Examples:
        >>> is_palindrome("racecar")
        True
        >>> is_palindrome("A man a plan a canal Panama")
        True
        >>> is_palindrome("hello")
        False
        >>> is_palindrome("")
        True
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    
    # Remove non-alphanumeric characters and convert to lowercase
    cleaned_text = ''.join(char.lower() for char in text if char.isalnum())
    
    # An empty string or single character is considered a palindrome
    return cleaned_text == cleaned_text[::-1]


# If the module is run directly, demonstrate the functions
if __name__ == "__main__":
    print("Demonstrating utility functions:")
    print(f"Greeting: {greet('World')}")
    print(f"Sum of [1, 2, 3, 4, 5]: {calculate_sum([1, 2, 3, 4, 5])}")
    print(f"Is 'racecar' a palindrome? {is_palindrome('racecar')}")
    print(f"Is 'hello' a palindrome? {is_palindrome('hello')}")