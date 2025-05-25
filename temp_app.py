# temp_app.py
import streamlit as st
from parser import parse_csv, parse_pdf

st.title("M-Pesa Statement Parser")

uploaded_file = st.file_uploader("Upload your M-Pesa statement", type=["csv", "pdf"])

if uploaded_file:
    try:
        if uploaded_file.type == "application/pdf":
            df = parse_pdf(uploaded_file)
            st.success("PDF parsed successfully!")
        elif uploaded_file.type == "text/csv":
            df = parse_csv(uploaded_file)
            st.success("CSV parsed successfully!")
        else:
            st.error("Unsupported file type.")
        
        st.dataframe(df)
    except Exception as e:
        st.error(f"Error parsing file: {e}")
        st.text("Please ensure the file is in the correct format.")
        st.text("For CSV files, ensure that the first row contains headers.")
        st.text("For PDF files, ensure that the file is not corrupted or password-protected.")
