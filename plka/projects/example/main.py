#!/usr/bin/env python3
"""
Example project for PLKA
This is a simple calculator application to demonstrate PLKA capabilities
"""

def add(a, b):
    """Add two numbers."""
    return a + b


def subtract(a, b):
    """Subtract b from a."""
    return a - b


def multiply(a, b):
    """Multiply two numbers."""
    return a * b


def divide(a, b):
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def main():
    """Main entry point."""
    print("Simple Calculator Example")
    print("Operations: add, subtract, multiply, divide")
    
    # Example usage
    result = add(5, 3)
    print(f"5 + 3 = {result}")


if __name__ == "__main__":
    main()
