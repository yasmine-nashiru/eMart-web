# Marketplace App — Phase 8

Streamlit application for the E-Commerce Marketplace System, connecting to the
`MarketplaceDB` MariaDB database (Phases 3–7).

## Setup

1. Make sure the Phase 7 security script has been run against your database
   (it adds `Vendor.Password` and the `Staff` table this app depends on):
   ```
   mysql -u root -p MarketplaceDB < phase7_security.sql
   ```
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set your DB connection details as environment variables (defaults shown):
   ```
   export DB_HOST=localhost
   export DB_PORT=3306
   export DB_USER=mkt_app
   export DB_PASSWORD=ChangeMe_Strong!2
   export DB_NAME=MarketplaceDB
   ```
4. Create your first Admin login:
   ```
   python scripts/create_admin.py
   ```
5. Run the app:
   ```
   streamlit run app.py
   ```

## Roles

- **Customer** — browse catalog, place orders, view own orders/payments/shipments, leave reviews. Logs in with an existing `Customer` row's email + password.
- **Vendor** — manage own products, view own sales report. Logs in with a `Vendor` row's email + password (password added by the Phase 7 migration or by an Admin via the app).
- **Staff (ADMIN)** — full CRUD across categories, products, vendors, staff; manage orders/payments/shipments; moderate reviews; view all reports.
- **Staff (SUPPORT)** — read/update order-related statuses and view customers, without vendor/staff/category management rights.

## Structure

```
app.py           Main Streamlit app, page routing, all page functions
db.py            DB connection + query helpers
auth.py          Login/authentication for Customer/Vendor/Staff
validators.py    Reusable input validation
scripts/create_admin.py   One-off script to seed the first Admin account
requirements.txt
```

## Notes / known limitations

- Existing customers in the sample data already have bcrypt password hashes
  and can log in as-is. Existing vendors do **not** have a password until you
  run the Phase 7 migration and set one (via an Admin's "Manage Vendors" form,
  or a direct UPDATE with a bcrypt hash).
- The app connects with the single `mkt_app` DB account (Phase 7) and enforces
  role-based access in the application layer — this is standard practice for
  a web app with its own session-based authentication.
- No password-reset flow yet (documented as a Phase 9 future enhancement).
