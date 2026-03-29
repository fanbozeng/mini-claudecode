"""
Utility functions for mypackage.
Enhanced with additional functionality and improved error handling.
"""

import re
from typing import List, Union, Optional


def add_numbers(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    Add two numbers together.
    
    Args:
        a (int/float): First number
        b (int/float): Second number
        
    Returns:
        int/float: Sum of the two numbers
        
    Raises:
        TypeError: If inputs are not numbers
    """
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("Both inputs must be numbers")
    return a + b


def multiply_numbers(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    Multiply two numbers together.
    
    Args:
        a (int/float): First number
        b (int/float): Second number
        
    Returns:
        int/float: Product of the two numbers
        
    Raises:
        TypeError: If inputs are not numbers
    """
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("Both inputs must be numbers")
    return a * b


def greet(name: str) -> str:
    """
    Return a greeting message.
    
    Args:
        name (str): Name to greet
        
    Returns:
        str: Greeting message
        
    Raises:
        TypeError: If name is not a string
    """
    if not isinstance(name, str):
        raise TypeError("Name must be a string")
    if not name.strip():
        raise ValueError("Name cannot be empty")
    return f"Hello, {name.strip()}!"


def is_even(number: int) -> bool:
    """
    Check if a number is even.
    
    Args:
        number (int): Number to check
        
    Returns:
        bool: True if even, False if odd
        
    Raises:
        TypeError: If input is not an integer
    """
    if not isinstance(number, int):
        raise TypeError("Input must be an integer")
    return number % 2 == 0


def reverse_string(s: str) -> str:
    """
    Reverse a string.
    
    Args:
        s (str): String to reverse
        
    Returns:
        str: Reversed string
    """
    return s[::-1]


def is_palindrome(s: str) -> bool:
    """
    Check if a string is a palindrome.
    
    Args:
        s (str): String to check
        
    Returns:
        bool: True if palindrome, False otherwise
    """
    s_clean = re.sub(r'[^a-zA-Z0-9]', '', s).lower()
    return s_clean == s_clean[::-1]


def find_max(numbers: List[Union[int, float]]) -> Union[int, float]:
    """
    Find the maximum number in a list.
    
    Args:
        numbers: List of numbers
        
    Returns:
        The maximum number
        
    Raises:
        ValueError: If the list is empty
    """
    if not numbers:
        raise ValueError("Cannot find maximum of empty list")
    return max(numbers)


def factorial(n: int) -> int:
    """
    Calculate the factorial of a number.
    
    Args:
        n (int): Number to calculate factorial for
        
    Returns:
        int: Factorial of n
        
    Raises:
        ValueError: If n is negative
        TypeError: If n is not an integer
    """
    if not isinstance(n, int):
        raise TypeError("Input must be an integer")
    if n < 0:
        raise ValueError("Factorial is not defined for negative numbers")
    if n == 0 or n == 1:
        return 1
    
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def validate_email(email: str) -> bool:
    """
    Validate an email address format.
    
    Args:
        email (str): Email address to validate
        
    Returns:
        bool: True if valid email format, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def count_words(text: str) -> int:
    """
    Count the number of words in a text.
    
    Args:
        text (str): Text to count words in
        
    Returns:
        int: Number of words
    """
    if not isinstance(text, str):
        return 0
    return len([word for word in text.split() if word.strip()])