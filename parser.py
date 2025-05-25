# parser.py

import pandas as pd
import pdfplumber

def parse_csv(file):

    file.seek(0)  
    df = pd.read_csv(file)
    df.columns = [col.strip() for col in df.columns]
    
    return df

def parse_pdf(file):

    pdf = pdfplumber.open(file) if not hasattr(file, 'read') else pdfplumber.open(file)
    dfs = []
    with pdf: 
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                page_df = pd.DataFrame(table[1:], columns=table[0])
                page_df.columns = page_df.columns.str.strip().str.replace('\n', '', regex=False)
                dfs.append(page_df)
                
    if not dfs:
        raise ValueError("No tables found in PDF.")
    
    full_df = pd.concat(dfs, ignore_index=True)

    full_df.columns = [col.strip() for col in full_df.columns]
    return full_df

