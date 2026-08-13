"""
Database connection helpers for the eMart Streamlit app.

Reads connection settings from environment variables so credentials are
never hard-coded in source (see Phase 7 security notes):

    DB_HOST      default: localhost
    DB_PORT      default: 3306
    DB_USER      default: mkt_app        (the Phase 7 app_service_role account)
    DB_PASSWORD  default: ChangeMe_Strong!2
    DB_NAME      default: MarketplaceDB
"""

import os
import mysql.connector
from mysql.connector import Error
import pandas as pd
import streamlit as st

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "mkt_app"),
    "password": os.environ.get("DB_PASSWORD", "ChangeMe_Strong!2"),
    "database": os.environ.get("DB_NAME", "MarketplaceDB"),
}


@st.cache_resource(show_spinner=False)
def get_connection():
    """Cached connection so Streamlit doesn't reopen a connection on every rerun."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        st.error(f"Could not connect to the database: {e}")
        st.stop()


def run_query(sql, params=None, as_df=True):
    """SELECT helper. Returns a DataFrame by default, or a list of dict rows."""
    conn = get_connection()
    if not conn.is_connected():
        conn.reconnect()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params or ())
        rows = cursor.fetchall()
    finally:
        cursor.close()
    if as_df:
        return pd.DataFrame(rows)
    return rows


def run_action(sql, params=None):
    """INSERT/UPDATE/DELETE helper. Returns (success, message_or_lastrowid)."""
    conn = get_connection()
    if not conn.is_connected():
        conn.reconnect()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params or ())
        conn.commit()
        last_id = cursor.lastrowid
        return True, last_id
    except Error as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()


def run_transaction(fn):
    """
    Runs fn(cursor) inside a single atomic database transaction.
    fn should perform its work via cursor.execute(...) calls and may return
    a value (e.g. the new Order's ID). Commits only if fn completes without
    raising; rolls back the ENTIRE transaction on any error, so a failure
    partway through (e.g. after the Order row but before an OrderDetail row)
    never leaves a partial/inconsistent record in the database.
    Returns (success, result_or_error_message).
    """
    conn = get_connection()
    if not conn.is_connected():
        conn.reconnect()
    cursor = conn.cursor()
    try:
        conn.start_transaction()
        result = fn(cursor)
        conn.commit()
        return True, result
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
    """Call a Phase 6 stored procedure. Returns list of result sets as DataFrames."""
    conn = get_connection()
    if not conn.is_connected():
        conn.reconnect()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.callproc(name, params or ())
        results = []
        for result in cursor.stored_results():
            results.append(pd.DataFrame(result.fetchall()))
        conn.commit()
        return True, results
    except Error as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()