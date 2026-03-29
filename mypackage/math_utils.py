"""
Mathematical utility functions for the project.
"""

import math
from typing import List, Union


def calculate_average(numbers: List[Union[int, float]]) -> float:
    """
    Calculate the average of a list of numbers.
    
    Args:
        numbers: List of numbers
        
    Returns:
        The average of the numbers
        
    Raises:
        ValueError: If the list is empty
    """
    if not numbers:
        raise ValueError("Cannot calculate average of empty list")
    return sum(numbers) / len(numbers)


def calculate_median(numbers: List[Union[int, float]]) -> float:
    """
    Calculate the median of a list of numbers.
    
    Args:
        numbers: List of numbers
        
    Returns:
        The median of the numbers
        
    Raises:
        ValueError: If the list is empty
    """
    if not numbers:
        raise ValueError("Cannot calculate median of empty list")
    
    sorted_numbers = sorted(numbers)
    n = len(sorted_numbers)
    
    if n % 2 == 0:
        return (sorted_numbers[n//2 - 1] + sorted_numbers[n//2]) / 2
    else:
        return sorted_numbers[n//2]


def calculate_standard_deviation(numbers: List[Union[int, float]]) -> float:
    """
    Calculate the standard deviation of a list of numbers.
    
    Args:
        numbers: List of numbers
        
    Returns:
        The standard deviation of the numbers
        
    Raises:
        ValueError: If the list is empty
    """
    if not numbers:
        raise ValueError("Cannot calculate standard deviation of empty list")
    
    mean = calculate_average(numbers)
    variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
    return math.sqrt(variance)


def is_prime(n: int) -> bool:
    """
    Check if a number is prime.
    
    Args:
        n: Number to check
        
    Returns:
        True if the number is prime, False otherwise
    """
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    
    for i in range(3, int(math.sqrt(n)) + 1, 2):
        if n % i == 0:
            return False
    return True


def fibonacci(n: int) -> int:
    """
    Calculate the nth Fibonacci number.
    
    Args:
        n: Position in the Fibonacci sequence
        
    Returns:
        The nth Fibonacci number
        
    Raises:
        ValueError: If n is negative
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n < 2:
        return n
    
    # Iterative approach
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a