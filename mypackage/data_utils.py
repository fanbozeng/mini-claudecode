"""
Data processing utility functions for the project.
"""

import json
import csv
from typing import List, Dict, Any, Union
from collections import Counter


def read_json_file(file_path: str) -> Dict[str, Any]:
    """
    Read data from a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Data from the JSON file
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)


def write_json_file(data: Dict[str, Any], file_path: str) -> None:
    """
    Write data to a JSON file.
    
    Args:
        data: Data to write
        file_path: Path to the output JSON file
    """
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def read_csv_file(file_path: str) -> List[Dict[str, str]]:
    """
    Read data from a CSV file.
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        List of dictionaries, where each dictionary represents a row
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        return list(reader)


def write_csv_file(data: List[Dict[str, Any]], file_path: str, fieldnames: List[str] = None) -> None:
    """
    Write data to a CSV file.
    
    Args:
        data: List of dictionaries to write
        file_path: Path to the output CSV file
        fieldnames: Column names (if None, uses keys from first dictionary)
    """
    if not data:
        return
    
    if fieldnames is None:
        fieldnames = list(data[0].keys())
    
    with open(file_path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


def analyze_data_frequency(data_list: List[Any]) -> Dict[Any, int]:
    """
    Analyze the frequency of items in a list.
    
    Args:
        data_list: List of items to analyze
        
    Returns:
        Dictionary with items as keys and their frequencies as values
    """
    return dict(Counter(data_list))


def filter_data(data_list: List[Dict[str, Any]], condition: str, value: Any) -> List[Dict[str, Any]]:
    """
    Filter a list of dictionaries based on a condition.
    
    Args:
        data_list: List of dictionaries to filter
        condition: Key to filter by
        value: Value to match
        
    Returns:
        Filtered list of dictionaries
    """
    return [item for item in data_list if item.get(condition) == value]


def sort_data(data_list: List[Dict[str, Any]], key: str, reverse: bool = False) -> List[Dict[str, Any]]:
    """
    Sort a list of dictionaries by a specific key.
    
    Args:
        data_list: List of dictionaries to sort
        key: Key to sort by
        reverse: Whether to sort in reverse order
        
    Returns:
        Sorted list of dictionaries
        
    Raises:
        KeyError: If the key doesn't exist in all dictionaries
    """
    return sorted(data_list, key=lambda x: x[key], reverse=reverse)