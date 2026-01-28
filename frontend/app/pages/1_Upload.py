import streamlit as st
from app.api_client import api_client

st.set_page_config(page_title="Upload - OBD2 Dashboard", page_icon="📤", layout="wide")

st.title("Upload CSV File")

st.markdown("""
Upload a CSV file from your OBD2 data logger. The file should contain:
- A header comment with `# StartTime = MM/DD/YYYY HH:MM:SS.xxxx AM/PM`
- Column headers including Time, Vehicle speed, GPS coordinates, and sensor data
""")

uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])

if uploaded_file is not None:
    col1, col2 = st.columns(2)

    with col1:
        name = st.text_input("Trip Name (optional)", placeholder="e.g., Morning Commute")

    with col2:
        description = st.text_area("Description (optional)", placeholder="Add notes about this trip...")

    if st.button("Upload", type="primary"):
        with st.spinner("Uploading and processing..."):
            try:
                result = api_client.upload_csv(
                    file=uploaded_file,
                    name=name if name else None,
                    description=description if description else None,
                )
                st.success(f"Trip uploaded successfully!")

                st.subheader("Trip Summary")
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("Duration", f"{result['duration_seconds'] / 60:.1f} min")

                with col2:
                    max_speed = result.get('max_speed_mph')
                    st.metric("Max Speed", f"{max_speed:.1f} mph" if max_speed else "N/A")

                with col3:
                    avg_speed = result.get('avg_speed_mph')
                    st.metric("Avg Speed", f"{avg_speed:.1f} mph" if avg_speed else "N/A")

                with col4:
                    st.metric("Data Points", f"{result.get('row_count', 0):,}")

                st.info(f"View your trip in the [Dashboard](/Dashboard?trip_id={result['id']})")

            except Exception as e:
                st.error(f"Error uploading file: {str(e)}")

# Show preview of file
if uploaded_file is not None:
    st.subheader("File Preview")
    uploaded_file.seek(0)
    content = uploaded_file.read().decode("utf-8-sig")
    lines = content.split("\n")[:20]
    st.code("\n".join(lines), language="csv")
    uploaded_file.seek(0)
