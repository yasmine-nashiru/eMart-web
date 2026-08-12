"""
Authentication for the three login-capable roles: Customer, Vendor, Staff.

Passwords are bcrypt hashes (matching the existing Customer.Password format
and the Phase 7 additions to Vendor/Staff). Never compares/stores plaintext.
"""

import bcrypt
from db import run_query


def _check_password(plain_password, stored_hash):
    if not stored_hash:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def hash_password(plain_password):
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def login_customer(email, password):
    df = run_query("SELECT * FROM Customer WHERE Email = %s", (email,))
    if df.empty:
        return None
    row = df.iloc[0]
    if _check_password(password, row["Password"]):
        return {
            "id": int(row["CustomerID"]),
            "name": f'{row["FirstName"]} {row["LastName"]}',
            "email": row["Email"],
            "role": "Customer",
        }
    return None


def login_vendor(email, password):
    df = run_query("SELECT * FROM Vendor WHERE Email = %s", (email,))
    if df.empty:
        return None
    row = df.iloc[0]
    if _check_password(password, row["Password"]):
        return {
            "id": int(row["VendorID"]),
            "name": row["BusinessName"],
            "email": row["Email"],
            "role": "Vendor",
        }
    return None


def login_staff(email, password):
    df = run_query("SELECT * FROM Staff WHERE Email = %s", (email,))
    if df.empty:
        return None
    row = df.iloc[0]
    if _check_password(password, row["Password"]):
        return {
            "id": int(row["StaffID"]),
            "name": f'{row["FirstName"]} {row["LastName"]}',
            "email": row["Email"],
            "role": row["Role"],  # 'ADMIN' or 'SUPPORT'
        }
    return None


def authenticate(login_as, email, password):
    """login_as is one of 'Customer', 'Vendor', 'Staff'."""
    if login_as == "Customer":
        return login_customer(email, password)
    if login_as == "Vendor":
        return login_vendor(email, password)
    if login_as == "Staff":
        return login_staff(email, password)
    return None
