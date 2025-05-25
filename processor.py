import pandas as pd
import pdfplumber

def clean_data(df):
    if 'Completion Time' in df.columns:
        dt = df['Completion Time'].astype(str).str.split(' ', n=1, expand=True)
        df['Date'] = pd.to_datetime(dt[0], dayfirst=True , errors='coerce').dt.strftime('%d/%m/%Y')
        df['Time'] = pd.to_datetime(dt[1], errors='coerce').dt.strftime('%H:%M')
        df = df.drop(columns=['Completion Time'])
    
    if 'Details' in df.columns:
        df = df.rename(columns={'Details': 'Description'})
    
    df = df[~df['Description'].str.contains('OverDraft of Credit Party', na=False)]
    
    for col in ['Paid in', 'Withdrawn']:
        if col in df.columns:
            df[col] = df[col].replace('', '0')
            df[col] = df[col].astype(str).str.replace(',', '', regex=False)
            df[col] = df[col].astype(float)
    
    df['Amount'] = 0.0
    if 'Paid in' in df.columns:
        df.loc[df['Paid in'] > 0, 'Amount'] = df['Paid in']
    if 'Withdrawn' in df.columns:
        df.loc[df['Withdrawn'] > 0, 'Amount'] = -df['Withdrawn']
    
    for col in ['Paid in', 'Withdrawn', 'Transaction Status', 'Balance']:
        if col in df.columns:
            df = df.drop(columns=col)
    
    df['Category'] = ''
    return df
