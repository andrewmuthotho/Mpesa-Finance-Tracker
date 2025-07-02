# app.py

import streamlit as st
import pandas as pd
import altair as alt
import json
import os
import matplotlib.pyplot as plt
from io import StringIO, BytesIO

from parser import parse_csv, parse_pdf
from processor import clean_data
from database import (
    create_connection, create_table, insert_transaction, 
    transaction_exists, get_transactions, update_transaction_category,
    get_all_categories, add_category_mapping, get_category_mappings
)

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

# --- Transaction Search & Edit ---
st.subheader("Add Category")

# Search transactions
category_file = "categories.json"

if "categories" not in st.session_state:
    st.session_state.categories = {
        "Uncategorized": []
    }

if os.path.exists(category_file):
    with open(category_file, "r") as f:
        st.session_state.categories = json.load(f)

def save_categories():
    with open(category_file, "w") as f:
        json.dump(st.session_state.categories, f, indent=2)

def categorize_transactions(df):
    df["Category"] = "Uncategorized"

    for category, keywords in st.session_state.categories.items():
        if category == "Uncategorized" or not keywords:
            continue

        lowered_keywords = [keyword.lower().strip() for keyword in keywords]

        for idx, row in df.iterrows():
            details = row["Description"].lower().strip()
            if details in lowered_keywords:
                df.at[idx, "Category"] = category
        
    return df

def add_keyword_to_category(category, keyword):
    """
    Add a keyword to a category for automatic categorization.
    """
    if category not in st.session_state.categories:
        st.session_state.categories[category] = []
    
    if keyword not in st.session_state.categories[category]:
        st.session_state.categories[category].append(keyword)
        save_categories()

# Editing category
new_category = st.text_input("New Category Name")
add_button = st.button("Add Category")

if add_button and new_category:
    if new_category not in st.session_state.categories:
        st.session_state.categories[new_category] = []
        save_categories()      
        st.rerun()

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
        st.session_state.clean_df = clean_df.copy()  

        st.subheader("Categorized Transactions")
        edited_df = st.data_editor(
            st.session_state.clean_df[["Date", "Time", "Description", "Amount", "Category"]],
            column_config={
                'Date': st.column_config.TextColumn("Date"),
                'Time': st.column_config.TextColumn("Time"),
                'Description': st.column_config.TextColumn("Description"),
                'Amount': st.column_config.NumberColumn("Amount", format="%.2f Ksh"),
                'Category': st.column_config.SelectboxColumn(
                    "Category",
                    options=list(st.session_state.categories.keys())
                )
            },
            hide_index=True,
            use_container_width=True,
            key="category_editor"
        ) 
        
        save_button = st.button("Save Changes", type ="primary")
        if save_button:
            for idx, row in edited_df.iterrows():
                new_category = row["Category"] 
                if new_category == st.session_state.clean_df.at[idx, "Category"]:
                    continue 

                details = row["Description"]
                st.session_state.clean_df.at[idx, "Category"] = new_category
                add_keyword_to_category(new_category, details) 

        # Insert into DB (skipping duplicates)
        new_count = 0
        for _, row in edited_df.iterrows():
            receipt_no = row.get('Receipt No', '') or row.get('Transaction ID', '') or f"TXN_{row.name}_{row['Date']}"
            date = str(row['Date'])
            amount = row['Amount']
            if not transaction_exists(conn, receipt_no, date, amount):
                insert_transaction(conn, (receipt_no, date, row['Time'], row['Description'], amount, row['Category']))
                new_count += 1
        st.success(f"Added {new_count} new transactions to the database.")
    except Exception as e:
        st.error(f"Error parsing file: {e}")

# --- All Transactions Tab ---
st.header("All Transactions Tab")

# Fetch all transactions from database
all_transactions = get_transactions(conn)
if all_transactions:
    # Convert to DataFrame
    df_all = pd.DataFrame(all_transactions, columns=['receipt_no', 'date', 'time', 'description', 'amount', 'category'])
    
    # Convert date to datetime for analysis and display only date part
    df_all['date'] = pd.to_datetime(df_all['date'], errors='coerce').dt.date
    
    # Editable table for category update
    st.subheader("Edit Categories for Existing Transactions")
    edited_db_df = st.data_editor(
        df_all[['receipt_no', 'date', 'time', 'description', 'amount', 'category']],
        column_config={
            'category': st.column_config.SelectboxColumn(
                "Category",
                options=list(st.session_state.categories.keys())
            )
        },
        hide_index=True,
        use_container_width=True,
        height=250,
        key="db_category_editor"
    )
    
    # Save button for DB category edits
    save_db_button = st.button("Save Category Changes to Database", type="primary", key="save_db_btn")
    if save_db_button:
        for idx, row in edited_db_df.iterrows():
            receipt_no = row['receipt_no']
            new_category = row['category']
            if new_category != df_all.at[idx, 'category']:
                update_transaction_category(conn, receipt_no, new_category)
                # Add the description as a keyword to the category
                description = row['description']
                add_keyword_to_category(new_category, description)
                # Auto-categorize other transactions in the database with the same description
                for j, other_row in df_all.iterrows():
                    if j != idx and other_row['description'] == description and other_row['category'] != new_category:
                        update_transaction_category(conn, other_row['receipt_no'], new_category)
        st.success("Categories updated in the database.")
        st.rerun()

    # Display all transactions with scrolling (smaller height)
    st.write(f"Total transactions in database: {len(df_all)}")
    # st.dataframe(df_all, use_container_width=True, height=250)  # Removed as per user request
    
    # --- Summary Tab: Filter by Category and Date ---
    st.subheader("Summary: Filter by Category and Date")
    with st.expander("Show Category & Date Filter"):
        all_categories = sorted(df_all['category'].unique())
        selected_categories = st.multiselect("Select categories to view spending:", all_categories, default=all_categories)
        min_date = df_all['date'].min()
        max_date = df_all['date'].max()
        date_range = st.date_input("Select date range:", [min_date, max_date], min_value=min_date, max_value=max_date)
    
    # Filter data
    filtered = df_all[(df_all['category'].isin(selected_categories)) &
                      (df_all['date'] >= date_range[0]) &
                      (df_all['date'] <= date_range[1]) &
                      (df_all['amount'] < 0)]
    filtered['amount'] = filtered['amount'].abs()
    st.write(f"Total spent in selected categories and date range: KSH {filtered['amount'].sum():,.2f}")
    st.dataframe(filtered[['date', 'description', 'amount', 'category']], use_container_width=True, height=250)
else:
    st.info("No transactions found in database. Upload a statement to get started.")

# --- Charts and Downloads ---
st.header("Spending Trends & Reports")

# Fetch all data into DataFrame for charts
all_data = pd.DataFrame(get_transactions(conn), columns=['receipt_no','date','time','description','amount','category'])
if not all_data.empty:
    # Convert 'date' to datetime for grouping
    all_data['date'] = pd.to_datetime(all_data['date'])
    
    # --- Interactive Pie Chart: Spending by Category (Expenses Only) ---
    st.subheader("Spending by Category (Interactive Pie Chart)")
    exp_data = all_data[all_data['amount'] < 0].copy()
    exp_data['amount'] = exp_data['amount'].abs()
    if not exp_data.empty:
        cat_sum = exp_data.groupby('category')['amount'].sum().reset_index()
        cat_sum = cat_sum[cat_sum['amount'] > 0]
        pie_chart = alt.Chart(cat_sum).mark_arc(innerRadius=50).encode(
            theta=alt.Theta(field="amount", type="quantitative"),
            color=alt.Color(field="category", type="nominal"),
            tooltip=[alt.Tooltip('category:N', title='Category'), alt.Tooltip('amount:Q', title='Total Spent')]
        ).properties(width=500, height=400, title='Expenses by Category')
        st.altair_chart(pie_chart, use_container_width=True)
    else:
        st.info("No expenses available for pie chart.")

    # Downloadable cleaned data CSV
    csv_buffer = StringIO()
    all_data.to_csv(csv_buffer, index=False)
    st.download_button("Download All Transactions CSV", csv_buffer.getvalue(), "transactions.csv", "text/csv")
    
    # Downloadable charts as PNG
    # Spending Trend PNG
    fig1, ax1 = plt.subplots()
    monthly = all_data.set_index('date').resample('M')['amount'].sum().reset_index()
    monthly['Month'] = monthly['date'].dt.strftime('%Y-%m')
    ax1.plot(monthly['Month'], monthly['amount'], marker='o')
    ax1.set_title("Monthly Spending Trend")
    ax1.set_xlabel("Month")
    ax1.set_ylabel("Net Amount")
    ax1.grid(True)
    buf1 = BytesIO()
    fig1.savefig(buf1, format="png")
    buf1.seek(0)
    st.download_button("Download Trend Chart (PNG)", buf1, "trend.png", "image/png")
else:
    st.info("No transactions available to display charts.")
