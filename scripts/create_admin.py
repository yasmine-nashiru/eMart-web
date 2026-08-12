"""
One-off helper to create the first Admin Staff account.
Run once from the project root: python scripts/create_admin.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import run_action  # noqa: E402
from auth import hash_password  # noqa: E402

if __name__ == "__main__":
    first = input("First name: ").strip()
    last = input("Last name: ").strip()
    email = input("Email: ").strip()
    password = input("Password (min 8 chars, letters+numbers): ").strip()

    hashed = hash_password(password)
    ok, res = run_action(
        "INSERT INTO Staff (FirstName, LastName, Email, Password, Role) VALUES (%s,%s,%s,%s,'ADMIN')",
        (first, last, email, hashed),
    )
    if ok:
        print(f"Admin account created (StaffID {res}). You can now log in via the app as Staff / {email}.")
    else:
        print(f"Failed: {res}")
