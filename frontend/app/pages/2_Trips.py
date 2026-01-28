import streamlit as st
import pandas as pd
from datetime import datetime

from app.api_client import api_client

st.set_page_config(page_title="Trips - OBD2 Dashboard", page_icon="📋", layout="wide")

st.title("Trip Browser")

# Fetch trips
try:
    trips = api_client.list_trips()
except Exception as e:
    st.error(f"Error fetching trips: {str(e)}")
    trips = []

if not trips:
    st.info("No trips found. Upload a CSV file to get started.")
else:
    # Convert to DataFrame for display
    df = pd.DataFrame(trips)
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["duration_min"] = df["duration_seconds"] / 60

    st.subheader(f"Found {len(trips)} trip(s)")

    # Display trips as cards
    for trip in trips:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])

            with col1:
                st.markdown(f"**{trip['name']}**")
                start = datetime.fromisoformat(trip["start_time"].replace("Z", "+00:00"))
                st.caption(start.strftime("%Y-%m-%d %H:%M"))

            with col2:
                duration_min = trip["duration_seconds"] / 60
                st.metric("Duration", f"{duration_min:.1f} min")

            with col3:
                max_speed = trip.get("max_speed_mph")
                st.metric("Max Speed", f"{max_speed:.1f} mph" if max_speed else "N/A")

            with col4:
                avg_speed = trip.get("avg_speed_mph")
                st.metric("Avg Speed", f"{avg_speed:.1f} mph" if avg_speed else "N/A")

            with col5:
                if st.button("View Dashboard", key=f"view_{trip['id']}"):
                    st.switch_page("pages/3_Dashboard.py")

            st.divider()

    # Trip management section
    st.subheader("Trip Management")

    selected_trip_id = st.selectbox(
        "Select a trip to manage",
        options=[t["id"] for t in trips],
        format_func=lambda x: next((t["name"] for t in trips if t["id"] == x), x),
    )

    if selected_trip_id:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Delete Trip", type="secondary"):
                try:
                    api_client.delete_trip(selected_trip_id)
                    st.success("Trip deleted!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting trip: {str(e)}")

        with col2:
            st.session_state["selected_trip_id"] = selected_trip_id
            if st.button("Open in Dashboard", type="primary"):
                st.switch_page("pages/3_Dashboard.py")
