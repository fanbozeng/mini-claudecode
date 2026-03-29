"""
MyPackage - A simple Python package with utility functions.
"""

__version__ = "0.1.0"
__author__ = "Your Name"

from .utils import *

__all__ = ["add_numbers", "multiply_numbers", "greet"]

def get_version():
    """Return the package version."""
    return __version__