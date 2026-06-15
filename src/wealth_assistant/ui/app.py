"""Streamlit UI: login, link accounts, consolidated portfolio (T038, US1).

Consumes the REST API only — never touches the DB or analytics layer directly.
"""
from __future__ import annotations

import httpx
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(page_title="Wealth AIssistant", layout="wide")

if "token" not in st.session_state:
    st.session_state.token = None


def _headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def auth_page() -> None:
    st.title("Wealth AIssistant")
    tab_login, tab_register = st.tabs(["Log in", "Register"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Log in"):
            r = httpx.post(f"{API}/auth/login", json={"email": email, "password": password})
            if r.status_code == 200:
                st.session_state.token = r.json()["token"]
                st.rerun()
            else:
                st.error(r.json().get("message", "Login failed"))

    with tab_register:
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password (min 12 chars)", type="password", key="reg_pw")
        currency = st.selectbox("Reporting currency", ["USD", "EUR", "GBP"])
        if st.button("Register"):
            r = httpx.post(
                f"{API}/auth/register",
                json={"email": email, "password": password, "reporting_currency": currency},
            )
            if r.status_code == 201:
                st.session_state.token = r.json()["token"]
                st.rerun()
            else:
                st.error(r.json().get("message", "Registration failed"))


def portfolio_page() -> None:
    st.title("Portfolio")
    if st.button("Log out"):
        st.session_state.token = None
        st.rerun()

    with st.expander("Link a new account"):
        pub_token = st.text_input("Public token from provider")
        if st.button("Link account") and pub_token:
            r = httpx.post(f"{API}/connections", json={"public_token": pub_token}, headers=_headers())
            if r.status_code == 201:
                st.success(f"Linked: {r.json()['institution_name']}")
                st.rerun()
            else:
                st.error(r.json().get("message", "Linking failed"))

    conns_r = httpx.get(f"{API}/connections", headers=_headers())
    if conns_r.status_code == 200:
        for c in conns_r.json():
            c1, c2, c3 = st.columns([4, 2, 2])
            c1.write(f"**{c['institution_name']}** ({c['provider']})")
            c2.write(c["status"])
            with c3:
                if st.button("Refresh", key=f"ref_{c['id']}"):
                    httpx.post(f"{API}/connections/{c['id']}/refresh", headers=_headers())
                    st.rerun()
                if st.button("Unlink", key=f"unl_{c['id']}"):
                    httpx.delete(f"{API}/connections/{c['id']}", headers=_headers())
                    st.rerun()

    port_r = httpx.get(f"{API}/portfolio", headers=_headers())
    if port_r.status_code != 200:
        st.error("Could not load portfolio.")
        return

    port = port_r.json()
    tv = port["total_value"]
    st.subheader(f"Total: {tv['amount']} {tv['currency']}" + (" ⚠️ stale" if port["stale"] else ""))

    if not port["holdings"]:
        st.info("No holdings yet. Link an account to get started.")
        return

    import pandas as pd
    rows = [
        {
            "Symbol": h["symbol"] or "—",
            "Name": h["name"],
            "Class": h["asset_class"],
            "Qty": h["quantity"],
            "Value": h["value"]["amount"] if h["price_available"] else "N/A",
            "Accounts": ", ".join(h["accounts"]),
        }
        for h in port["holdings"]
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.divider()
    _allocation_view()
    st.divider()
    _performance_view()
    st.divider()
    _risk_view()


def _allocation_view() -> None:
    by = st.selectbox("Allocation by", ["asset_class", "sector", "account"], key="alloc_by")
    r = httpx.get(f"{API}/portfolio/allocation?by={by}", headers=_headers())
    if r.status_code != 200:
        st.error("Could not load allocation.")
        return
    import pandas as pd
    data = r.json()
    rows = [{"Label": s["label"], "Weight %": s["weight_pct"], "Value": s["value"]["amount"]} for s in data["slices"]]
    st.subheader(f"Allocation by {by.replace('_', ' ')}")
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


def _performance_view() -> None:
    period = st.selectbox("Performance period", ["1M", "3M", "6M", "1Y", "YTD", "ALL"], key="perf_period")
    r = httpx.get(f"{API}/portfolio/performance?period={period}", headers=_headers())
    if r.status_code != 200:
        st.error("Could not load performance.")
        return
    data = r.json()
    st.subheader(f"Performance ({period})")
    if data.get("insufficient_history"):
        st.info("Insufficient history for this period. Link accounts and wait for snapshots to accrue.")
        return
    col1, col2, col3 = st.columns(3)
    col1.metric("Return", f"{data['return_pct']}%")
    col2.metric("Gain / Loss", f"{data['gain_loss']['amount']} {data['gain_loss']['currency']}")
    col3.metric("End Value", f"{data['end_value']['amount']} {data['end_value']['currency']}")


def _risk_view() -> None:
    r = httpx.get(f"{API}/portfolio/risk", headers=_headers())
    if r.status_code != 200:
        st.error("Could not load risk data.")
        return
    data = r.json()
    st.subheader("Risk & Diversification")
    st.caption(data["diversification_summary"])
    col1, col2, col3 = st.columns(3)
    col1.metric("HHI", data["hhi"], help="Herfindahl-Hirschman Index (0–10000; lower = more diversified)")
    if data.get("insufficient_history"):
        col2.info("Insufficient history for volatility.")
    else:
        col2.metric("Annualized Volatility", f"{data['volatility_pct']}%" if data["volatility_pct"] else "—")
    col3.metric("Asset Classes", data["asset_class_count"])
    if data["concentration_flags"]:
        st.warning("Concentrated positions (≥20%):")
        import pandas as pd
        rows = [{"Symbol": f["symbol"] or "—", "Weight %": f["weight_pct"]} for f in data["concentration_flags"]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)


if st.session_state.token is None:
    auth_page()
else:
    portfolio_page()
