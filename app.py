"""
eMart — Phase 8 Application
Streamlit + MariaDB (database: MarketplaceDB)

Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd

from db import run_query, run_action, run_transaction
from auth import authenticate, hash_password
from validators import (
    validate_email, validate_phone, validate_password,
    validate_non_empty, validate_positive_number, validate_rating,
)

st.set_page_config(page_title="eMart Admin", layout="wide")

# Custom styling on top of .streamlit/config.toml (which sets the base
# background/sidebar/text/primary-button colors). This covers what the
# theme config can't: hover states and small text highlights.
st.markdown(
    """
    <style>
    /* Primary + form + download buttons: sky blue, soft pink on hover */
    div.stButton > button,
    div.stFormSubmitButton > button,
    div.stDownloadButton > button {
        background-color: #38BDF8;
        color: #FFFFFF;
        border: 1px solid #38BDF8;
        border-radius: 6px;
        font-weight: 600;
        transition: background-color 0.15s ease, border-color 0.15s ease;
    }
    div.stButton > button:hover,
    div.stFormSubmitButton > button:hover,
    div.stDownloadButton > button:hover {
        background-color: #F9A8D4;
        border-color: #F9A8D4;
        color: #1B2A41;
    }
    /* Sidebar acts as the navbar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E5EEF7;
    }
    /* Small highlights: captions, metric labels/deltas */
    [data-testid="stCaptionContainer"],
    [data-testid="stMetricDelta"],
    small {
        color: #EC4899 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# Session state / auth
# ------------------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None


def logout():
    st.session_state.user = None
    st.rerun()


def login_page():
    st.title("🛒 eMart")
    st.subheader("Sign in")
    login_as = st.selectbox("Login as", ["Customer", "Vendor", "Staff"])
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Sign in", type="primary"):
        ok, msg = validate_email(email)
        if not ok:
            st.error(msg)
            return
        user = authenticate(login_as, email, password)
        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Invalid email or password.")
    with st.expander("Demo accounts"):
        st.write(
            "Use the accounts already in your `Customer` / `Vendor` / `Staff` "
            "tables. To create a Staff/Admin account, insert a row with a "
            "bcrypt-hashed password (see `scripts/create_admin.py`)."
        )

    if login_as == "Customer":
        with st.expander("New here? Create a customer account"):
            signup_customer()


def signup_customer():
    with st.form("signup_form"):
        col1, col2 = st.columns(2)
        first = col1.text_input("First name")
        last = col2.text_input("Last name")
        email = st.text_input("Email", key="signup_email")
        phone = st.text_input("Phone number (e.g. 0244123456)")
        pwd = st.text_input("Password", type="password", key="signup_pwd")
        pwd2 = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create Account")

    if not submitted:
        return

    checks = [
        validate_non_empty(first, "First name"),
        validate_non_empty(last, "Last name"),
        validate_email(email),
        validate_phone(phone),
        validate_password(pwd),
    ]
    if pwd != pwd2:
        checks.append((False, "Passwords do not match."))
    if not form_errors(*checks):
        return

    existing = run_query("SELECT CustomerID FROM Customer WHERE Email = %s", (email,))
    if not existing.empty:
        st.error("An account with this email already exists — try signing in instead.")
        return

    ok, res = run_action(
        "INSERT INTO Customer (FirstName, LastName, Email, PhoneNumber, Password, RegistrationDate) "
        "VALUES (%s, %s, %s, %s, %s, CURDATE())",
        (first, last, email, phone, hash_password(pwd)),
    )
    if ok:
        st.success("Account created! Select 'Customer' above and sign in with your new email and password.")
    else:
        st.error(f"Could not create account: {res}")


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------
def require_role(*allowed_roles):
    role = st.session_state.user["role"]
    if role not in allowed_roles:
        st.warning("You don't have access to this page.")
        st.stop()


def form_errors(*checks):
    """checks is a list of (ok, msg) tuples; shows all errors, returns True if all passed."""
    all_ok = True
    for ok, msg in checks:
        if not ok:
            st.error(msg)
            all_ok = False
    return all_ok


# ------------------------------------------------------------------
# CATALOG — search & filter (all roles)
# ------------------------------------------------------------------
def page_catalog():
    st.header("Product Catalog")
    categories = run_query("SELECT CategoryID, CategoryName FROM Category ORDER BY CategoryName")
    vendors = run_query("SELECT VendorID, BusinessName FROM Vendor ORDER BY BusinessName")

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        search = st.text_input("Search product name")
    with c2:
        cat_choice = st.selectbox("Category", ["All"] + categories["CategoryName"].tolist())
    with c3:
        max_price = st.number_input("Max price (GHS)", min_value=0.0, value=0.0, step=50.0)
    with c4:
        status = st.selectbox("Status", ["ACTIVE", "OUT_OF_STOCK", "DISCONTINUED", "All"])

    sql = """
        SELECT p.ProductID, p.ProductName, c.CategoryName, v.BusinessName AS Vendor,
               p.UnitPrice, p.Status
        FROM Product p
        JOIN Category c ON p.CategoryID = c.CategoryID
        JOIN Vendor v ON p.VendorID = v.VendorID
        WHERE 1=1
    """
    params = []
    if search:
        sql += " AND p.ProductName LIKE %s"
        params.append(f"%{search}%")
    if cat_choice != "All":
        sql += " AND c.CategoryName = %s"
        params.append(cat_choice)
    if max_price > 0:
        sql += " AND p.UnitPrice <= %s"
        params.append(max_price)
    if status != "All":
        sql += " AND p.Status = %s"
        params.append(status)
    sql += " ORDER BY p.ProductName"

    df = run_query(sql, tuple(params))
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"{len(df)} product(s) found")


# ------------------------------------------------------------------
# CUSTOMER — cart, orders, reviews
# ------------------------------------------------------------------
def page_my_profile():
    require_role("Customer")
    cust_id = st.session_state.user["id"]
    st.header("My Profile")
    row = run_query("SELECT * FROM Customer WHERE CustomerID = %s", (cust_id,)).iloc[0]

    with st.form("profile_form"):
        phone = st.text_input("Phone number", value=row.PhoneNumber or "")
        email = st.text_input("Email", value=row.Email)
        submitted = st.form_submit_button("Save Changes")

    if submitted:
        checks = [validate_email(email), validate_phone(phone)]
        if not form_errors(*checks):
            return
        if email != row.Email:
            dup = run_query("SELECT CustomerID FROM Customer WHERE Email=%s AND CustomerID<>%s", (email, cust_id))
            if not dup.empty:
                st.error("Another account already uses that email.")
                return
        ok, res = run_action(
            "UPDATE Customer SET PhoneNumber=%s, Email=%s WHERE CustomerID=%s",
            (phone, email, cust_id),
        )
        if ok:
            st.session_state.user["email"] = email
            st.success("Profile updated.")
        else:
            st.error(f"Could not update profile: {res}")


def page_my_cart():
    require_role("Customer")
    cust_id = st.session_state.user["id"]
    st.header("My Shopping Cart")

    cart = run_query("SELECT * FROM ShoppingCart WHERE CustomerID = %s", (cust_id,))
    if cart.empty:
        st.info("No cart on file yet.")
    else:
        st.dataframe(cart, use_container_width=True, hide_index=True)

    st.subheader("Place a new order")
    products = run_query(
        "SELECT ProductID, ProductName, UnitPrice FROM Product WHERE Status='ACTIVE' ORDER BY ProductName"
    )
    if products.empty:
        st.info("No active products available.")
        return

    with st.form("new_order_form"):
        chosen = st.multiselect(
            "Products", products["ProductID"],
            format_func=lambda pid: products.loc[products.ProductID == pid, "ProductName"].values[0],
        )
        qtys = {}
        for pid in chosen:
            name = products.loc[products.ProductID == pid, "ProductName"].values[0]
            qtys[pid] = st.number_input(f"Quantity — {name}", min_value=1, value=1, step=1, key=f"qty_{pid}")
        submitted = st.form_submit_button("Place Order")

    if submitted:
        if not chosen:
            st.error("Select at least one product.")
            return

        def place_order(cursor):
            cursor.execute(
                "INSERT INTO `Order` (CustomerID, OrderDate, OrderStatus, TotalAmount) "
                "VALUES (%s, NOW(), 'PENDING', 0)",
                (cust_id,),
            )
            order_id = cursor.lastrowid
            total = 0.0
            for pid in chosen:
                price = float(products.loc[products.ProductID == pid, "UnitPrice"].values[0])
                qty = qtys[pid]
                subtotal = price * qty
                total += subtotal
                cursor.execute(
                    "INSERT INTO OrderDetail (OrderID, ProductID, Quantity, UnitPrice, Subtotal) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (order_id, pid, qty, price, subtotal),
                )
            cursor.execute("UPDATE `Order` SET TotalAmount = %s WHERE OrderID = %s", (total, order_id))
            return order_id, total

        ok, result = run_transaction(place_order)
        if ok:
            order_id, total = result
            st.success(f"Order #{order_id} placed — total GHS {total:,.2f}")
            st.rerun()
        else:
            st.error(f"Order could not be placed — nothing was saved (transaction rolled back): {result}")


def page_my_orders():
    require_role("Customer")
    cust_id = st.session_state.user["id"]
    st.header("My Orders")
    orders = run_query(
        "SELECT OrderID, OrderDate, OrderStatus, TotalAmount FROM `Order` "
        "WHERE CustomerID = %s ORDER BY OrderDate DESC",
        (cust_id,),
    )
    st.dataframe(orders, use_container_width=True, hide_index=True)

    if orders.empty:
        return
    st.subheader("Order details")
    oid = st.selectbox("Select an order", orders["OrderID"])
    details = run_query(
        "SELECT od.ProductID, p.ProductName, od.Quantity, od.UnitPrice, od.Subtotal "
        "FROM OrderDetail od JOIN Product p ON od.ProductID = p.ProductID "
        "WHERE od.OrderID = %s",
        (oid,),
    )
    st.dataframe(details, use_container_width=True, hide_index=True)

    payment = run_query("SELECT * FROM Payment WHERE OrderID = %s", (oid,))
    shipment = run_query("SELECT * FROM Shipment WHERE OrderID = %s", (oid,))
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Payment**")
        st.dataframe(payment, hide_index=True)
    with col2:
        st.write("**Shipment**")
        st.dataframe(shipment, hide_index=True)


def page_my_reviews():
    require_role("Customer")
    cust_id = st.session_state.user["id"]
    st.header("My Reviews")

    my_payments = run_query(
        "SELECT pay.PaymentID, s.ShipmentID, o.OrderID "
        "FROM Payment pay "
        "JOIN `Order` o ON pay.OrderID = o.OrderID "
        "JOIN Shipment s ON s.OrderID = o.OrderID "
        "WHERE o.CustomerID = %s AND pay.PaymentStatus='COMPLETED'",
        (cust_id,),
    )
    if my_payments.empty:
        st.info("You don't have any completed, shipped orders to review yet.")
        return

    with st.form("review_form"):
        oid_choice = st.selectbox(
            "Order", my_payments["OrderID"],
        )
        rating = st.slider("Rating", 1, 5, 5)
        comment = st.text_area("Comment")
        submitted = st.form_submit_button("Submit Review")

    if submitted:
        checks = [validate_rating(rating), validate_non_empty(comment, "Comment")]
        if not form_errors(*checks):
            return
        row = my_payments[my_payments.OrderID == oid_choice].iloc[0]
        ok, res = run_action(
            "INSERT INTO Review (PaymentID, ShipmentID, Rating, Comment, ReviewDate) "
            "VALUES (%s, %s, %s, %s, CURDATE())",
            (int(row.PaymentID), int(row.ShipmentID), rating, comment),
        )
        if ok:
            st.success("Review submitted. Thank you!")
        else:
            st.error(f"Could not submit review: {res}")


# ------------------------------------------------------------------
# VENDOR — manage own products, view own sales
# ------------------------------------------------------------------
def page_vendor_products():
    require_role("Vendor")
    vendor_id = st.session_state.user["id"]
    st.header("My Products")

    products = run_query(
        "SELECT p.ProductID, p.ProductName, c.CategoryName, p.UnitPrice, p.Status "
        "FROM Product p JOIN Category c ON p.CategoryID = c.CategoryID "
        "WHERE p.VendorID = %s ORDER BY p.ProductName",
        (vendor_id,),
    )
    st.dataframe(products, use_container_width=True, hide_index=True)

    categories = run_query("SELECT CategoryID, CategoryName FROM Category ORDER BY CategoryName")

    st.subheader("Add a product")
    with st.form("add_product_form", clear_on_submit=True):
        name = st.text_input("Product name")
        desc = st.text_area("Description")
        cat = st.selectbox("Category", categories["CategoryID"],
                            format_func=lambda cid: categories.loc[categories.CategoryID == cid, "CategoryName"].values[0])
        price = st.number_input("Unit price (GHS)", min_value=0.0, step=10.0)
        image = st.text_input("Image path", value="/images/products/placeholder.jpg")
        submitted = st.form_submit_button("Add Product")

    if submitted:
        checks = [
            validate_non_empty(name, "Product name"),
            validate_positive_number(price, "Unit price"),
        ]
        if not form_errors(*checks):
            return
        ok, res = run_action(
            "INSERT INTO Product (VendorID, CategoryID, ProductName, Description, UnitPrice, ProductImage, Status) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE')",
            (vendor_id, int(cat), name, desc, price, image),
        )
        if ok:
            st.success(f"Product added (ID {res}).")
            st.rerun()
        else:
            st.error(f"Could not add product: {res}")

    if products.empty:
        return

    st.subheader("Update / remove a product")
    pid = st.selectbox("Select product", products["ProductID"],
                        format_func=lambda p: products.loc[products.ProductID == p, "ProductName"].values[0])
    current = products[products.ProductID == pid].iloc[0]
    with st.form("edit_product_form"):
        new_price = st.number_input("Unit price (GHS)", min_value=0.0, value=float(current.UnitPrice), step=10.0)
        new_status = st.selectbox("Status", ["ACTIVE", "OUT_OF_STOCK", "DISCONTINUED"],
                                   index=["ACTIVE", "OUT_OF_STOCK", "DISCONTINUED"].index(current.Status))
        col1, col2 = st.columns(2)
        update_clicked = col1.form_submit_button("Update")
        delete_clicked = col2.form_submit_button("Delete", type="secondary")

    if update_clicked:
        if not form_errors(validate_positive_number(new_price, "Unit price")):
            return
        ok, res = run_action(
            "UPDATE Product SET UnitPrice=%s, Status=%s WHERE ProductID=%s AND VendorID=%s",
            (new_price, new_status, int(pid), vendor_id),
        )
        st.success("Product updated.") if ok else st.error(res)
        st.rerun()

    if delete_clicked:
        ok, res = run_action("DELETE FROM Product WHERE ProductID=%s AND VendorID=%s", (int(pid), vendor_id))
        st.success("Product deleted.") if ok else st.error(f"Could not delete (likely referenced by existing orders): {res}")
        st.rerun()


def page_vendor_sales():
    require_role("Vendor")
    vendor_id = st.session_state.user["id"]
    st.header("My Sales")

    df = run_query(
        "SELECT o.OrderID, o.OrderDate, o.OrderStatus, p.ProductName, od.Quantity, od.Subtotal "
        "FROM OrderDetail od "
        "JOIN Product p ON od.ProductID = p.ProductID "
        "JOIN `Order` o ON od.OrderID = o.OrderID "
        "WHERE p.VendorID = %s ORDER BY o.OrderDate DESC",
        (vendor_id,),
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
    if not df.empty:
        st.metric("Total revenue (all-time)", f"GHS {df['Subtotal'].sum():,.2f}")
        st.bar_chart(df.groupby("ProductName")["Subtotal"].sum())


# ------------------------------------------------------------------
# ADMIN / SUPPORT — manage everything
# ------------------------------------------------------------------
def page_manage_categories():
    require_role("ADMIN")
    st.header("Manage Categories")
    df = run_query("SELECT * FROM Category ORDER BY CategoryName")
    st.dataframe(df, use_container_width=True, hide_index=True)

    with st.form("add_category", clear_on_submit=True):
        name = st.text_input("Category name")
        desc = st.text_input("Description")
        submitted = st.form_submit_button("Add Category")
    if submitted:
        if not form_errors(validate_non_empty(name, "Category name")):
            return
        ok, res = run_action("INSERT INTO Category (CategoryName, Description) VALUES (%s, %s)", (name, desc))
        st.success("Category added.") if ok else st.error(res)
        st.rerun()

    if df.empty:
        return
    cid = st.selectbox("Delete a category", df["CategoryID"],
                        format_func=lambda c: df.loc[df.CategoryID == c, "CategoryName"].values[0])
    if st.button("Delete selected category"):
        ok, res = run_action("DELETE FROM Category WHERE CategoryID=%s", (int(cid),))
        st.success("Deleted.") if ok else st.error(f"Could not delete (products reference it?): {res}")
        st.rerun()


def page_manage_products():
    require_role("ADMIN", "SUPPORT")
    st.header("Manage Products (all vendors)")
    df = run_query(
        "SELECT p.ProductID, p.ProductName, v.BusinessName AS Vendor, c.CategoryName, "
        "p.UnitPrice, p.Status "
        "FROM Product p JOIN Vendor v ON p.VendorID=v.VendorID "
        "JOIN Category c ON p.CategoryID=c.CategoryID ORDER BY p.ProductName"
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    if st.session_state.user["role"] != "ADMIN" or df.empty:
        return
    pid = st.selectbox("Select product to moderate", df["ProductID"],
                        format_func=lambda p: df.loc[df.ProductID == p, "ProductName"].values[0])
    new_status = st.selectbox("Set status", ["ACTIVE", "OUT_OF_STOCK", "DISCONTINUED"])
    if st.button("Update status"):
        ok, res = run_action("UPDATE Product SET Status=%s WHERE ProductID=%s", (new_status, int(pid)))
        st.success("Updated.") if ok else st.error(res)
        st.rerun()


def page_manage_vendors():
    require_role("ADMIN")
    st.header("Manage Vendors")
    df = run_query("SELECT VendorID, BusinessName, ContactName, Email, PhoneNumber, BusinessAddress FROM Vendor ORDER BY BusinessName")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Add a vendor")
    with st.form("add_vendor", clear_on_submit=True):
        biz = st.text_input("Business name")
        contact = st.text_input("Contact name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        addr = st.text_input("Business address")
        pwd = st.text_input("Initial password", type="password")
        submitted = st.form_submit_button("Add Vendor")
    if submitted:
        checks = [
            validate_non_empty(biz, "Business name"),
            validate_email(email),
            validate_phone(phone),
            validate_password(pwd),
        ]
        if not form_errors(*checks):
            return
        ok, res = run_action(
            "INSERT INTO Vendor (BusinessName, ContactName, Email, Password, PhoneNumber, BusinessAddress, RegistrationDate) "
            "VALUES (%s, %s, %s, %s, %s, %s, CURDATE())",
            (biz, contact, email, hash_password(pwd), phone, addr),
        )
        st.success("Vendor added.") if ok else st.error(res)
        st.rerun()


def page_manage_customers():
    require_role("ADMIN", "SUPPORT")
    st.header("Customers")
    search = st.text_input("Search by name or email")
    sql = "SELECT CustomerID, FirstName, LastName, Email, PhoneNumber, RegistrationDate FROM Customer WHERE 1=1"
    params = []
    if search:
        sql += " AND (FirstName LIKE %s OR LastName LIKE %s OR Email LIKE %s)"
        params += [f"%{search}%"] * 3
    sql += " ORDER BY RegistrationDate DESC"
    df = run_query(sql, tuple(params))
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_manage_staff():
    require_role("ADMIN")
    st.header("Staff Accounts")
    df = run_query("SELECT StaffID, FirstName, LastName, Email, Role, CreatedDate FROM Staff ORDER BY CreatedDate DESC")
    st.dataframe(df, use_container_width=True, hide_index=True)

    with st.form("add_staff", clear_on_submit=True):
        fn = st.text_input("First name")
        ln = st.text_input("Last name")
        email = st.text_input("Email")
        role = st.selectbox("Role", ["ADMIN", "SUPPORT"])
        pwd = st.text_input("Initial password", type="password")
        submitted = st.form_submit_button("Add Staff")
    if submitted:
        checks = [
            validate_non_empty(fn, "First name"), validate_non_empty(ln, "Last name"),
            validate_email(email), validate_password(pwd),
        ]
        if not form_errors(*checks):
            return
        ok, res = run_action(
            "INSERT INTO Staff (FirstName, LastName, Email, Password, Role) VALUES (%s,%s,%s,%s,%s)",
            (fn, ln, email, hash_password(pwd), role),
        )
        st.success("Staff account added.") if ok else st.error(res)
        st.rerun()


def page_orders_admin():
    require_role("ADMIN", "SUPPORT")
    st.header("All Orders")
    status_filter = st.selectbox("Filter by status", ["All", "PENDING", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"])
    sql = ("SELECT o.OrderID, cu.FirstName, cu.LastName, o.OrderDate, o.OrderStatus, o.TotalAmount "
           "FROM `Order` o JOIN Customer cu ON o.CustomerID = cu.CustomerID WHERE 1=1")
    params = []
    if status_filter != "All":
        sql += " AND o.OrderStatus = %s"
        params.append(status_filter)
    sql += " ORDER BY o.OrderDate DESC"
    df = run_query(sql, tuple(params))
    st.dataframe(df, use_container_width=True, hide_index=True)

    if df.empty:
        return
    oid = st.selectbox("Update order status", df["OrderID"])
    new_status = st.selectbox("New status", ["PENDING", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"])
    if st.button("Apply status change"):
        ok, res = run_action("UPDATE `Order` SET OrderStatus=%s WHERE OrderID=%s", (new_status, int(oid)))
        st.success("Order status updated.") if ok else st.error(res)
        st.rerun()


def page_payments_admin():
    require_role("ADMIN", "SUPPORT")
    st.header("Payments")
    df = run_query("SELECT * FROM Payment ORDER BY PaymentDate DESC")
    st.dataframe(df, use_container_width=True, hide_index=True)
    if df.empty:
        return
    pid = st.selectbox("Update payment status", df["PaymentID"])
    new_status = st.selectbox("New status", ["PENDING", "COMPLETED", "FAILED", "REFUNDED"])
    if st.button("Apply"):
        ok, res = run_action("UPDATE Payment SET PaymentStatus=%s WHERE PaymentID=%s", (new_status, int(pid)))
        st.success("Updated.") if ok else st.error(res)
        st.rerun()


def page_shipments_admin():
    require_role("ADMIN", "SUPPORT")
    st.header("Shipments")
    df = run_query("SELECT * FROM Shipment ORDER BY ShipmentID DESC")
    st.dataframe(df, use_container_width=True, hide_index=True)
    if df.empty:
        return
    sid = st.selectbox("Update shipment status", df["ShipmentID"])
    new_status = st.selectbox("New status", ["PREPARING", "IN_TRANSIT", "DELIVERED", "RETURNED"])
    if st.button("Apply"):
        ok, res = run_action("UPDATE Shipment SET ShipmentStatus=%s WHERE ShipmentID=%s", (new_status, int(sid)))
        st.success("Updated.") if ok else st.error(res)
        st.rerun()


def page_reviews_admin():
    require_role("ADMIN", "SUPPORT")
    st.header("Reviews (moderation)")
    df = run_query(
        "SELECT r.ReviewID, r.Rating, r.Comment, r.ReviewDate, "
        "cu.FirstName, cu.LastName, p.ProductName "
        "FROM Review r "
        "JOIN Payment pay ON r.PaymentID = pay.PaymentID "
        "JOIN `Order` o ON pay.OrderID = o.OrderID "
        "JOIN Customer cu ON o.CustomerID = cu.CustomerID "
        "JOIN OrderDetail od ON od.OrderID = o.OrderID "
        "JOIN Product p ON od.ProductID = p.ProductID "
        "ORDER BY r.ReviewDate DESC"
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
    if df.empty or st.session_state.user["role"] != "ADMIN":
        return
    rid = st.selectbox("Delete a review", df["ReviewID"])
    if st.button("Delete review"):
        ok, res = run_action("DELETE FROM Review WHERE ReviewID=%s", (int(rid),))
        st.success("Deleted.") if ok else st.error(res)
        st.rerun()


# ------------------------------------------------------------------
# REPORTS
# ------------------------------------------------------------------
def page_reports():
    require_role("ADMIN", "SUPPORT", "Vendor")
    st.header("Reports")
    role = st.session_state.user["role"]

    vendor_filter = ""
    params = ()
    if role == "Vendor":
        vendor_filter = "WHERE p.VendorID = %s"
        params = (st.session_state.user["id"],)

    st.subheader("Revenue by Category")
    df1 = run_query(
        f"SELECT c.CategoryName, SUM(od.Subtotal) AS Revenue "
        f"FROM OrderDetail od JOIN Product p ON od.ProductID = p.ProductID "
        f"JOIN Category c ON p.CategoryID = c.CategoryID {vendor_filter} "
        f"GROUP BY c.CategoryName ORDER BY Revenue DESC",
        params,
    )
    if not df1.empty:
        st.bar_chart(df1.set_index("CategoryName"))

    st.subheader("Top 5 Products by Revenue")
    df2 = run_query(
        f"SELECT p.ProductName, SUM(od.Subtotal) AS Revenue "
        f"FROM OrderDetail od JOIN Product p ON od.ProductID = p.ProductID "
        f"{vendor_filter} GROUP BY p.ProductName ORDER BY Revenue DESC LIMIT 5",
        params,
    )
    st.dataframe(df2, use_container_width=True, hide_index=True)

    if role in ("ADMIN", "SUPPORT"):
        st.subheader("Order Status Breakdown")
        df3 = run_query("SELECT OrderStatus, COUNT(*) AS Count FROM `Order` GROUP BY OrderStatus")
        st.bar_chart(df3.set_index("OrderStatus"))

        st.subheader("Monthly Revenue Trend")
        df4 = run_query(
            "SELECT DATE_FORMAT(OrderDate, '%Y-%m') AS Month, SUM(TotalAmount) AS Revenue "
            "FROM `Order` WHERE OrderStatus <> 'CANCELLED' GROUP BY Month ORDER BY Month"
        )
        if not df4.empty:
            st.line_chart(df4.set_index("Month"))


# ------------------------------------------------------------------
# Navigation
# ------------------------------------------------------------------
PAGES_BY_ROLE = {
    "Customer": {
        "Catalog": page_catalog,
        "My Cart / Place Order": page_my_cart,
        "My Orders": page_my_orders,
        "My Reviews": page_my_reviews,
        "My Profile": page_my_profile,
    },
    "Vendor": {
        "Catalog": page_catalog,
        "My Products": page_vendor_products,
        "My Sales & Reports": page_vendor_sales,
        "Full Reports": page_reports,
    },
    "ADMIN": {
        "Catalog": page_catalog,
        "Manage Categories": page_manage_categories,
        "Manage Products": page_manage_products,
        "Manage Vendors": page_manage_vendors,
        "Customers": page_manage_customers,
        "Staff": page_manage_staff,
        "Orders": page_orders_admin,
        "Payments": page_payments_admin,
        "Shipments": page_shipments_admin,
        "Reviews": page_reviews_admin,
        "Reports": page_reports,
    },
    "SUPPORT": {
        "Catalog": page_catalog,
        "Customers": page_manage_customers,
        "Orders": page_orders_admin,
        "Payments": page_payments_admin,
        "Shipments": page_shipments_admin,
        "Reviews": page_reviews_admin,
        "Reports": page_reports,
    },
}


def main():
    if not st.session_state.user:
        login_page()
        return

    user = st.session_state.user
    st.sidebar.title("🛒 eMart")
    st.sidebar.write(f"**{user['name']}**")
    st.sidebar.caption(f"Role: {user['role']}")
    if st.sidebar.button("Log out"):
        logout()

    pages = PAGES_BY_ROLE.get(user["role"], {"Catalog": page_catalog})
    choice = st.sidebar.radio("Navigate", list(pages.keys()))
    pages[choice]()


if __name__ == "__main__":
    main()