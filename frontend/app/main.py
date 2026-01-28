import streamlit as st

st.set_page_config(
    page_title="OBD2 Telemetry Dashboard",
    page_icon="🚗",
    layout="wide",
)

st.title("OBD2 Telemetry Dashboard")

st.markdown("""
Welcome to the OBD2 Telemetry Dashboard. This application allows you to:

- **Upload** CSV files from your OBD2 data logger
- **Browse** your recorded trips
- **Visualize** speed, throttle, and other sensor data
- **View** GPS routes on interactive maps
- **Compare** multiple trips side by side

Use the sidebar to navigate between pages.
""")

st.sidebar.success("Select a page above.")
