# app.py

import streamlit as st
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt
from io import StringIO, BytesIO

from parser import parse_csv, parse_pdf
from processor import clean_data, extract_pdf_table
from database import create_connection, create_table, insert_transaction, transaction_exists, get_transactions, update_transaction_category

# --- App Configuration and Styling ---
st.set_page_config(page_title="Personal Finance Tracker", layout="wide", page_icon="💰")

# Custom CSS 
st.markdown("""
    <style>
    /* Use Apple-like San Francisco font if available */
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
    h1 { color: #333333; text-align: center; margin-top: 1rem; }
    .stButton>button { border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Personal Finance Tracker")

# Initialize database
conn = create_connection()
create_table(conn)

# --- File Upload and Parsing ---
st.header("Upload M-Pesa Statement")
st.write("Upload your M-Pesa statement in CSV or PDF format to add transactions to your tracker.")
uploaded_file = st.file_uploader("Choose a CSV or PDF file", type=['csv', 'pdf'])
if uploaded_file:
    try:
        # Parse depending on file type
        if uploaded_file.name.lower().endswith('.csv'):
            raw_df = parse_csv(uploaded_file)
        else:
            raw_df = parse_pdf(uploaded_file)
        st.success("File parsed successfully!")
        
        # Clean and categorize
        clean_df = clean_data(raw_df)
        st.write("Parsed transactions preview:")
        st.dataframe(clean_df.head(10))
        
        # Insert into DB (skipping duplicates)
        new_count = 0
        for _, row in clean_df.iterrows():
            receipt_no = row.get('Receipt No', '') or row.get('Transaction ID', '') or str(row['time'])
            date = str(row['Date'])
            amount = row['Amount']
            if not transaction_exists(conn, receipt_no, date, amount):
                insert_transaction(conn, (receipt_no, date, row['Time'], row['Description'], amount, row['Category']))
                new_count += 1
        st.success(f"Added {new_count} new transactions to the database.")
    except Exception as e:
        st.error(f"Error parsing file: {e}")

# --- Transaction Search & Edit ---
st.header("View and Edit Transactions")

search_input = st.text_input("Search by description or transaction ID")
results = get_transactions(conn, search_input) if search_input else get_transactions(conn)
if results:
    df_results = pd.DataFrame(results, columns=['receipt_no', 'date', 'time', 'description', 'amount', 'category'])
    st.write(f"Found {len(df_results)} transactions.")
    st.dataframe(df_results)

    # Editing category
    st.subheader("Edit Transaction Category")
    receipt_no_to_edit = st.text_input("Enter Transaction ID to update")
    new_cat = st.text_input("New Category")
    if st.button("Update Category"):
        if receipt_no_to_edit and new_cat:
            update_transaction_category(conn, receipt_no_to_edit, new_cat)
            st.success(f"Updated category of {receipt_no_to_edit} to {new_cat}.")
        else:
            st.error("Please provide both Transaction ID and new category.")

# --- Charts and Downloads ---
st.header("Spending Trends & Reports")

# Fetch all data into DataFrame for charts
all_data = pd.DataFrame(get_transactions(conn), columns=['receipt_no','date','time','description','amount','category'])
if not all_data.empty:
    # Convert 'date' to datetime for grouping
    all_data['date'] = pd.to_datetime(all_data['date'])
    
    # Interactive Trend Chart (monthly spending)
    st.subheader("Monthly Spending Trend")
    monthly = all_data.set_index('date').resample('M')['amount'].sum().reset_index()
    chart = alt.Chart(monthly).mark_line(point=True).encode(
        x=alt.X('date:T', title='Month'),
        y=alt.Y('amount:Q', title='Net Amount'),
        tooltip=[alt.Tooltip('date:T', title='Month'), alt.Tooltip('amount:Q', title='Net Total')]
    ).properties(width=600, height=300)
    st.altair_chart(chart, use_container_width=True)

    # Interactive Category Breakdown (only expenses)
    st.subheader("Category Breakdown (Expenses)")
    exp_data = all_data[all_data['amount'] < 0]
    if not exp_data.empty:
        cat_sum = exp_data.groupby('category')['amount'].sum().reset_index()
        bar_chart = alt.Chart(cat_sum).mark_bar(color='#4c78a8').encode(
            x=alt.X('category:N', sort='-y', title='Category'),
            y=alt.Y('amount:Q', title='Total Spent'),
            tooltip=[alt.Tooltip('category:N', title='Category'), alt.Tooltip('amount:Q', title='Total')]
        ).properties(width=600, height=300)
        st.altair_chart(bar_chart, use_container_width=True)

    # Downloadable cleaned data CSV
    csv_buffer = StringIO()
    all_data.to_csv(csv_buffer, index=False)
    st.download_button("Download All Transactions CSV", csv_buffer.getvalue(), "transactions.csv", "text/csv")
    
    # Downloadable charts as PNG
    # Spending Trend PNG
    fig1, ax1 = plt.subplots()
    monthly_plot = monthly.copy()
    monthly_plot['Month'] = monthly_plot['date'].dt.strftime('%Y-%m')
    ax1.plot(monthly_plot['Month'], monthly_plot['amount'], marker='o')
    ax1.set_title("Monthly Spending Trend")
    ax1.set_xlabel("Month")
    ax1.set_ylabel("Net Amount")
    ax1.grid(True)
    buf1 = BytesIO()
    fig1.savefig(buf1, format="png")
    buf1.seek(0)
    st.download_button("Download Trend Chart (PNG)", buf1, "trend.png", "image/png")
    
    # Category Breakdown PNG
    if not exp_data.empty:
        fig2, ax2 = plt.subplots()
        categories = cat_sum['category']
        totals = -cat_sum['amount']  # make positives for pie
        ax2.pie(totals, labels=categories, autopct='%1.1f%%', startangle=90, colors=plt.cm.Paired.colors)
        ax2.set_title("Expenses by Category")
        buf2 = BytesIO()
        fig2.savefig(buf2, format="png")
        buf2.seek(0)
        st.download_button("Download Category Chart (PNG)", buf2, "categories.png", "image/png")
else:
    st.info("No transactions available to display charts.")
