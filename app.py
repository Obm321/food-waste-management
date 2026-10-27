import sqlite3
from pathlib import Path
import streamlit as st
import pandas as pd

DB_PATH = Path(__file__).with_name("food_waste.db")

st.set_page_config(page_title="Food Waste Management", page_icon="♻️", layout="centered")

def connect_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS food_waste (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            food_name TEXT NOT NULL,
            food_type TEXT NOT NULL,
            leftover_kg REAL NOT NULL CHECK (leftover_kg > 0),
            donation_kg REAL NOT NULL DEFAULT 0,
            compost_kg REAL NOT NULL DEFAULT 0,
            garbage_kg REAL NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    return conn

def fetch_records(conn):
    return pd.read_sql_query("""
        SELECT id, event_name, food_name, food_type, leftover_kg,
               donation_kg, compost_kg, garbage_kg
        FROM food_waste ORDER BY id DESC
    """, conn)

conn = connect_db()
st.title("♻️ Food Waste Management System")
st.caption("A simple food-waste tracking app for events.")

page = st.sidebar.radio("Menu", [
    "Food Prediction",
    "Record Leftover Food",
    "Donation / Compost / Garbage",
    "Records & Statistics"
])

if page == "Food Prediction":
    st.header("Food Requirement Prediction")
    st.write("Estimate food needs before an event.")
    with st.form("prediction_form"):
        people = st.number_input("Expected participants", min_value=1, step=1, value=100)
        kg_per_person = st.number_input("Estimated food per person (kg)", min_value=0.01, value=0.5, step=0.05)
        submitted = st.form_submit_button("Estimate food")
    if submitted:
        total = people * kg_per_person
        st.success(f"Estimated food required: {total:.2f} kg")
        st.caption("This is a basic estimate. Adjust it for the menu and previous event data.")

elif page == "Record Leftover Food":
    st.header("Record Leftover Food")
    with st.form("leftover_form", clear_on_submit=True):
        event_name = st.text_input("Event name")
        food_name = st.text_input("Food name")
        food_type = st.selectbox("Food type", ["Rice / grains", "Vegetables", "Fruit", "Bread / bakery", "Meat / fish", "Dairy", "Other"])
        leftover_kg = st.number_input("Leftover weight (kg)", min_value=0.01, value=1.0, step=0.5)
        submitted = st.form_submit_button("Save record")
    if submitted:
        if not event_name.strip() or not food_name.strip():
            st.error("Please enter both the event name and food name.")
        else:
            conn.execute("""
                INSERT INTO food_waste (event_name, food_name, food_type, leftover_kg)
                VALUES (?, ?, ?, ?)
            """, (event_name.strip(), food_name.strip(), food_type, float(leftover_kg)))
            conn.commit()
            st.success("Leftover food record saved.")

elif page == "Donation / Compost / Garbage":
    st.header("Record Food Disposal")
    df = fetch_records(conn)
    if df.empty:
        st.info("No food records yet. Add a leftover-food record first.")
    else:
        st.dataframe(df[["id", "event_name", "food_name", "leftover_kg", "donation_kg", "compost_kg", "garbage_kg"]], use_container_width=True, hide_index=True)
        options = {f"#{int(row.id)} — {row.event_name}: {row.food_name} ({row.leftover_kg:.2f} kg)": int(row.id)
                   for row in df.itertuples()}
        with st.form("disposal_form"):
            chosen = st.selectbox("Choose a food record", list(options.keys()))
            disposal = st.selectbox("Treatment", ["Donation", "Composting", "Ordinary garbage"])
            amount = st.number_input("Amount to process (kg)", min_value=0.01, value=0.5, step=0.5)
            submitted = st.form_submit_button("Save treatment")
        if submitted:
            record_id = options[chosen]
            row = conn.execute("""
                SELECT leftover_kg, donation_kg, compost_kg, garbage_kg
                FROM food_waste WHERE id = ?
            """, (record_id,)).fetchone()
            leftover, donated, compost, garbage = row
            remaining = leftover - donated - compost - garbage
            if amount > remaining + 1e-9:
                st.error(f"Amount is too high. Only {remaining:.2f} kg remains unprocessed.")
            else:
                column = {
                    "Donation": "donation_kg",
                    "Composting": "compost_kg",
                    "Ordinary garbage": "garbage_kg"
                }[disposal]
                conn.execute(f"UPDATE food_waste SET {column} = {column} + ? WHERE id = ?", (float(amount), record_id))
                conn.commit()
                if disposal == "Donation":
                    st.warning("Only record food for donation after confirming it is safe for human consumption. Animal-feed suitability must be confirmed by the receiving organization.")
                st.success(f"{amount:.2f} kg recorded as {disposal.lower()}.")

elif page == "Records & Statistics":
    st.header("Records & Statistics")
    df = fetch_records(conn)
    if df.empty:
        st.info("No records yet. Start by recording leftover food.")
    else:
        total = float(df["leftover_kg"].sum())
        donated = float(df["donation_kg"].sum())
        compost = float(df["compost_kg"].sum())
        garbage = float(df["garbage_kg"].sum())
        unprocessed = max(total - donated - compost - garbage, 0)
        c1, c2 = st.columns(2)
        c1.metric("Leftover recorded", f"{total:.2f} kg")
        c2.metric("Donated", f"{donated:.2f} kg")
        c3, c4 = st.columns(2)
        c3.metric("Composted", f"{compost:.2f} kg")
        c4.metric("Ordinary garbage", f"{garbage:.2f} kg")
        st.metric("Not yet processed", f"{unprocessed:.2f} kg")
        st.subheader("All records")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "Download records as CSV",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="food_waste_records.csv",
            mime="text/csv"
        )

conn.close()
