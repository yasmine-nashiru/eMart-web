"""Reusable input validation for forms across the app."""

import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^0\d{9}$")  # Ghanaian local format: 0XXXXXXXXX


def validate_email(value):
    if not value or not EMAIL_RE.match(value):
        return False, "Enter a valid email address."
    return True, ""


def validate_phone(value):
    if not value:
        return True, ""  # phone is optional in the schema
    if not PHONE_RE.match(value):
        return False, "Phone number should be 10 digits starting with 0 (e.g. 0244123456)."
    return True, ""


def validate_password(value):
    if not value or len(value) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        return False, "Password must contain at least one letter and one number."
    return True, ""


def validate_non_empty(value, field_name="Field"):
    if value is None or str(value).strip() == "":
        return False, f"{field_name} is required."
    return True, ""


def validate_positive_number(value, field_name="Value"):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return False, f"{field_name} must be a number."
    if n <= 0:
        return False, f"{field_name} must be greater than 0."
    return True, ""


def validate_rating(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return False, "Rating must be a whole number."
    if n < 1 or n > 5:
        return False, "Rating must be between 1 and 5."
    return True, ""
