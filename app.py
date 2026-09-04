import difflib
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from snowflake.snowpark import Session

try:
    import pypdf
except ImportError:
    pypdf = None

# ==============================================================================
# 1. PAGE CONFIGURATION
# ==============================================================================
st.set_page_config(
    page_title="Sales Copilot",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. BULLETPROOF AUTHENTICATION
# ==============================================================================
USER_DATABASE = {
    "admin": {
        "password": "Copilot@2026",
        "name": "Admin User",
        "role": "Account Administrator"
    },
    "analyst": {
        "password": "Copilot@2026",
        "name": "Sales Analyst",
        "role": "Commercial Analyst"
    }
}

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None
if "display_name" not in st.session_state:
    st.session_state.display_name = None
if "role" not in st.session_state:
    st.session_state.role = None

def render_login_form():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 20px; 
                    padding: 40px; box-shadow: 0 4px 25px rgba(0,0,0,0.04); text-align: center;">
            <div style="font-size: 2.2rem; margin-bottom: 8px;">✨</div>
            <h2 style="color: #111827; font-weight: 600; margin-bottom: 6px; letter-spacing: -0.5px;">Welcome back</h2>
            <p style="color: #6b7280; font-size: 0.95rem; margin-bottom: 30px;">Sign in to your Sales AI Copilot workspace</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            username_input = st.text_input("Username", placeholder="e.g. admin or analyst")
            password_input = st.text_input("Password", type="password", placeholder="••••••••")
            submit_button = st.form_submit_button("Continue", use_container_width=True, type="primary")

            if submit_button:
                user_info = USER_DATABASE.get(username_input.strip().lower())
                if user_info and user_info["password"] == password_input:
                    st.session_state.authenticated = True
                    st.session_state.username = username_input.strip().lower()
                    st.session_state.display_name = user_info["name"]
                    st.session_state.role = user_info["role"]
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please try again.")

if not st.session_state.authenticated:
    render_login_form()
    st.stop()

# ==============================================================================
# 3. SECURE SNOWFLAKE CONNECTION
# ==============================================================================
@st.cache_resource
def get_snowflake_session():
    connection_parameters = {
        "account": st.secrets["snowflake"]["account"],
        "user": st.secrets["snowflake"]["user"],
        "password": st.secrets["snowflake"]["password"],
        "role": st.secrets["snowflake"]["role"],
        "warehouse": st.secrets["snowflake"]["warehouse"],
        "database": st.secrets["snowflake"]["database"],
        "schema": st.secrets["snowflake"]["schema"]
    }
    return Session.builder.configs(connection_parameters).create()

session = get_snowflake_session()

# ==============================================================================
# 4. GOOGLE GEMINI-STYLE MINIMALIST CSS
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600&family=Roboto:wght@300;400;500&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Google Sans', 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #1f2937;
    }

    section[data-testid="stSidebar"] {
        background-color: #f8fafd !important;
        border-right: 1px solid #e5e7eb !important;
    }
    
    .gemini-header-title {
        font-size: 1.65rem;
        font-weight: 500;
        color: #111827;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 2px;
    }
    .gemini-header-sub {
        font-size: 0.88rem;
        color: #6b7280;
        margin-bottom: 18px;
    }
    
    div[data-testid="stSidebar"] div[data-testid="stButton"] > button {
        border-radius: 24px;
        font-weight: 500;
        font-size: 0.88rem;
        border: 1px solid #e5e7eb;
        background-color: #ffffff;
        color: #374151;
        transition: all 0.15s ease-in-out;
        padding: 8px 16px;
    }
    div[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
        background-color: #f3f4f6;
        border-color: #d1d5db;
        color: #111827;
    }
    
    div[data-testid="stSidebar"] .new-chat-btn button {
        background-color: #eef2ff !important;
        border: 1px solid #c7d2fe !important;
        color: #4338ca !important;
        font-weight: 600 !important;
    }

    div[data-testid="stChatMessage"] {
        background-color: transparent !important;
        padding: 14px 0px;
    }
    div[data-testid="stChatMessageContent"] {
        font-size: 0.96rem;
        line-height: 1.6;
        color: #1f2937;
    }

    .source-badge {
        display: inline-block;
        font-size: 0.73rem;
        font-weight: 600;
        padding: 2px 10px;
        border-radius: 12px;
        margin-bottom: 8px;
    }
    .badge-snowflake {
        background-color: #e0f2fe;
        color: #0369a1;
        border: 1px solid #bae6fd;
    }
    .badge-doc {
        background-color: #fef3c7;
        color: #b45309;
        border: 1px solid #fde68a;
    }

    .user-footer-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 12px 14px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-top: 24px;
    }
    .brand-dilytics {
        display: inline-block;
        background-color: #D50000;
        color: #ffffff;
        font-weight: 800;
        font-size: 0.68rem;
        letter-spacing: 1.2px;
        padding: 3px 8px;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 5. VERIFIED QUERIES & DATA MART ENGINE
# ==============================================================================
RAW_VERIFIED_QUERIES = [
    {"question": "What is the total sales amount?", "sql": "SELECT SUM(total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES"},
    {"question": "What are the total sales by customer?", "sql": "SELECT c.customer_name, SUM(f.total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES f JOIN CORTEX.MART.DIM_CUSTOMER c ON f.customer_id = c.customer_id GROUP BY c.customer_name ORDER BY total_sales DESC"},
    {"question": "What are the top products by sales?", "sql": "SELECT p.product_name, SUM(i.line_total) AS total_sales FROM CORTEX.MART.FACT_SALES_ITEM i JOIN CORTEX.MART.DIM_PRODUCT p ON i.product_id = p.product_id GROUP BY p.product_name ORDER BY total_sales DESC LIMIT 10"},
    {"question": "What are total sales by customer region?", "sql": "SELECT c.region, SUM(f.total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES f JOIN CORTEX.MART.DIM_CUSTOMER c ON f.customer_id = c.customer_id GROUP BY c.region ORDER BY total_sales DESC"},
    {"question": "What is the average sales by region?", "sql": "SELECT c.region, ROUND(AVG(f.total_amount), 2) AS average_sales FROM CORTEX.MART.FACT_SALES f JOIN CORTEX.MART.DIM_CUSTOMER c ON f.customer_id = c.customer_id GROUP BY c.region ORDER BY average_sales DESC"},
    {"question": "What are total sales by month?", "sql": "SELECT d.year, d.month, d.month_name, SUM(f.total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES f JOIN CORTEX.MART.DIM_DATE d ON f.order_date = d.date_key GROUP BY d.year, d.month, d.month_name ORDER BY d.year, d.month"},
    {"question": "What were the total sales in 2000?", "sql": "SELECT d.year, SUM(s.total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES s JOIN CORTEX.MART.DIM_DATE d ON s.order_date = d.date_key WHERE d.year = 2000 GROUP BY d.year"},
    {"question": "What is total sales by year?", "sql": "SELECT d.year, SUM(f.total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES f JOIN CORTEX.MART.DIM_DATE d ON f.order_date = d.date_key GROUP BY d.year ORDER BY d.year ASC"},
    {"question": "What is total sales by order channel?", "sql": "SELECT order_channel, SUM(total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES GROUP BY order_channel ORDER BY total_sales DESC"},
    {"question": "What is the average order value?", "sql": "SELECT ROUND(AVG(total_amount), 2) AS average_order_value FROM CORTEX.MART.FACT_SALES"},
    {"question": "How many sales orders are there?", "sql": "SELECT COUNT(order_id) AS total_orders FROM CORTEX.MART.FACT_SALES"},
    {"question": "What are total sales by sales representative?", "sql": "SELECT r.sales_rep_name, SUM(f.total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES f JOIN CORTEX.MART.DIM_SALES_REP r ON f.sales_rep_id = r.sales_rep_id GROUP BY r.sales_rep_name ORDER BY total_sales DESC LIMIT 10"},
    {"question": "What is total sales by product category?", "sql": "SELECT p.category, SUM(i.line_total) AS total_sales FROM CORTEX.MART.FACT_SALES_ITEM i JOIN CORTEX.MART.DIM_PRODUCT p ON i.product_id = p.product_id GROUP BY p.category ORDER BY total_sales DESC"},
    {"question": "What is total sales by brand?", "sql": "SELECT p.brand, SUM(i.line_total) AS total_sales FROM CORTEX.MART.FACT_SALES_ITEM i JOIN CORTEX.MART.DIM_PRODUCT p ON i.product_id = p.product_id GROUP BY p.brand ORDER BY total_sales DESC"},
    {"question": "Who are the top 10 customers by sales?", "sql": "SELECT c.customer_name, SUM(f.total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES f JOIN CORTEX.MART.DIM_CUSTOMER c ON f.customer_id = c.customer_id GROUP BY c.customer_name ORDER BY total_sales DESC LIMIT 10"}
]

def normalize_text(text: str) -> str:
    return re.sub(r'[^\w\s]', '', text.lower()).strip()

PROCESSED_VERIFIED = []
for vq in RAW_VERIFIED_QUERIES:
    PROCESSED_VERIFIED.append({
        "question": vq["question"],
        "norm_q": normalize_text(vq["question"]),
        "sql": vq["sql"].strip()
    })

def generate_sql_for_database(prompt: str) -> Tuple[str, Optional[str]]:
    p = prompt.lower().strip()
    norm_p = normalize_text(prompt)

    if norm_p in ["hi", "hello", "hey", "help", "who are you", "good morning", "good evening"]:
        return "Hello! I am your Sales Intelligence Assistant. Ask any question about enterprise revenue, customers, products, or time trends.", None

    year_match = re.search(r'\b(19\d\d|20\d\d)\b', p)
    target_year = year_match.group(1) if year_match else None

    is_avg = any(k in p for k in ["average", "avg", "mean"])
    is_count = any(k in p for k in ["count", "number of orders", "order volume", "how many orders", "order count"])
    
    if is_avg:
        metric_agg = "ROUND(AVG(s.total_amount), 2)"
        item_agg = "ROUND(AVG(si.line_total), 2)"
        alias = "average_sales"
    elif is_count:
        metric_agg = "COUNT(s.order_id)"
        item_agg = "COUNT(si.order_item_id)"
        alias = "order_count"
    else:
        metric_agg = "SUM(s.total_amount)"
        item_agg = "SUM(si.line_total)"
        alias = "total_sales"

    if target_year:
        if "region" in p:
            return f"Sales by region for {target_year}:", f"""
SELECT c.region, {metric_agg} AS {alias}
FROM CORTEX.MART.FACT_SALES s
JOIN CORTEX.MART.DIM_CUSTOMER c ON s.customer_id = c.customer_id
JOIN CORTEX.MART.DIM_DATE d ON s.order_date = d.date_key
WHERE d.year = {target_year}
GROUP BY c.region
ORDER BY {alias} DESC
            """.strip()

        if any(k in p for k in ["category", "categories"]):
            return f"Sales by category for {target_year}:", f"""
SELECT p.category, {item_agg} AS {alias}
FROM CORTEX.MART.FACT_SALES_ITEM si
JOIN CORTEX.MART.DIM_PRODUCT p ON si.product_id = p.product_id
JOIN CORTEX.MART.FACT_SALES s ON si.order_id = s.order_id
JOIN CORTEX.MART.DIM_DATE d ON s.order_date = d.date_key
WHERE d.year = {target_year}
GROUP BY p.category
ORDER BY {alias} DESC
            """.strip()

        if any(k in p for k in ["month", "monthly"]):
            return f"Monthly sales for {target_year}:", f"""
SELECT d.month, d.month_name, {metric_agg} AS {alias}
FROM CORTEX.MART.FACT_SALES s
JOIN CORTEX.MART.DIM_DATE d ON s.order_date = d.date_key
WHERE d.year = {target_year}
GROUP BY d.month, d.month_name
ORDER BY d.month ASC
            """.strip()

        return f"Total sales for year {target_year}:", f"""
SELECT d.year, {metric_agg} AS {alias}
FROM CORTEX.MART.FACT_SALES s
JOIN CORTEX.MART.DIM_DATE d ON s.order_date = d.date_key
WHERE d.year = {target_year}
GROUP BY d.year
        """.strip()

    for vq in PROCESSED_VERIFIED:
        if norm_p == vq["norm_q"]:
            return f"Analysis for: **{vq['question']}**", vq["sql"]

    if "total sales" in norm_p and not any(k in norm_p for k in ["region", "customer", "month", "product"]):
        return "Total gross sales across all transactions:", "SELECT SUM(total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES"
    if "sales by customer" in norm_p:
        return "Sales grouped by customer:", "SELECT c.customer_name, SUM(f.total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES f JOIN CORTEX.MART.DIM_CUSTOMER c ON f.customer_id = c.customer_id GROUP BY c.customer_name ORDER BY total_sales DESC LIMIT 20"
    if "sales by region" in norm_p or "by customer region" in norm_p:
        return "Sales grouped by customer region:", "SELECT c.region, SUM(f.total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES f JOIN CORTEX.MART.DIM_CUSTOMER c ON f.customer_id = c.customer_id GROUP BY c.region ORDER BY total_sales DESC"
    if "top product" in norm_p or "products by sales" in norm_p:
        return "Top products by sales revenue:", "SELECT p.product_name, SUM(i.line_total) AS total_sales FROM CORTEX.MART.FACT_SALES_ITEM i JOIN CORTEX.MART.DIM_PRODUCT p ON i.product_id = p.product_id GROUP BY p.product_name ORDER BY total_sales DESC LIMIT 10"
    if any(k in norm_p for k in ["year wise", "yearly", "by year", "annual"]):
        return "Sales trend by year:", "SELECT d.year, SUM(f.total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES f JOIN CORTEX.MART.DIM_DATE d ON f.order_date = d.date_key GROUP BY d.year ORDER BY d.year ASC"

    cortex_instruction = f"""
You are a Snowflake SQL generator for CORTEX.MART.
Tables:
- FACT_SALES s (order_id, customer_id, sales_rep_id, order_status, order_channel, order_date, total_amount)
- FACT_SALES_ITEM si (order_item_id, order_id, product_id, quantity, unit_price, line_total)
- DIM_CUSTOMER c (customer_id, customer_name, customer_type, industry, region)
- DIM_PRODUCT p (product_id, product_name, category, sub_category, brand)
- DIM_SALES_REP r (sales_rep_id, sales_rep_name, region)
- DIM_DATE d (date_key, year, month, month_name, quarter, fiscal_year)

Joins:
- s.customer_id = c.customer_id
- s.order_date = d.date_key
- si.order_id = s.order_id
- si.product_id = p.product_id
- s.sales_rep_id = r.sales_rep_id

Rules:
Return ONLY the executable Snowflake SQL query without markdown formatting or backticks.

Question: {prompt}
SQL:
"""
    for model in ['llama3.1-8b', 'mistral-7b']:
        try:
            res = session.sql(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', ?) AS sql_out", params=[cortex_instruction]).collect()
            raw_sql = res[0]["SQL_OUT"].strip()
            clean_sql = re.sub(r"^```(sql)?", "", raw_sql, flags=re.IGNORECASE).strip().rstrip("`").strip()
            if clean_sql.lower().startswith("select") or clean_sql.lower().startswith("with"):
                return f"Analysis query for: **{prompt}**", clean_sql
        except Exception:
            continue

    return "I could not formulate a query for this question. Please ask about sales revenue, averages, products, customers, or reps.", None

# ==============================================================================
# 6. ENHANCED DOCUMENT INTELLIGENCE & ACCURATE TABULAR QA
# ==============================================================================
def extract_df_from_xlsx(file_bytes: bytes) -> pd.DataFrame:
    try:
        return pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception:
        pass
    for delimiter in [',', '\t', ';']:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), sep=delimiter, encoding='utf-8')
            if len(df.columns) > 1:
                return df
        except Exception:
            pass
    raise ValueError("Could not parse file as tabular spreadsheet.")

def extract_text_from_pdf(file_bytes: bytes) -> str:
    if pypdf is None:
        return "PDF text extraction requires the pypdf library."
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        return "".join([page.extract_text() or "" for page in reader.pages]).strip()
    except Exception as exc:
        return f"Error extracting PDF: {str(exc)}"

def extract_text_from_docx(file_bytes: bytes) -> str:
    if not file_bytes:
        return ""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            xml_content = z.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            text_pieces = []
            for node in tree.iter():
                if node.tag.split('}')[-1] == 't' and node.text:
                    text_pieces.append(node.text)
                elif node.tag.split('}')[-1] in ('p', 'tr'):
                    text_pieces.append("\n")
            return re.sub(r'\n\s*\n+', '\n\n', "".join(text_pieces)).strip()
    except Exception as exc:
        return f"Error extracting Word document: {str(exc)}"

def answer_user_question_on_document(question: str, doc_context: str, filename: str, df: Optional[pd.DataFrame] = None) -> Optional[str]:
    q_lower = question.lower().strip()

    # Priority 1: Direct High-Accuracy Pandas Tabular Filtering & Aggregation
    if df is not None and not df.empty:
        stop_words = {
            "what", "is", "the", "are", "sales", "for", "total", "average", "avg", 
            "count", "show", "give", "list", "of", "in", "by", "all", "me", "find",
            "county", "state", "city", "value"
        }
        words = [w for w in re.findall(r'\b[a-zA-Z0-9_]+\b', q_lower) if len(w) > 2 and w not in stop_words]
        
        mask = pd.Series(False, index=df.index)
        for col in df.columns:
            for word in words:
                mask = mask | df[col].astype(str).str.lower().str.contains(r'\b' + re.escape(word) + r'\b', na=False)
        
        matched_df = df[mask]
        
        if not matched_df.empty:
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            sales_cols = [c for c in numeric_cols if any(k in c.lower() for k in ["sale", "amount", "revenue", "total", "val"])]
            target_metric_col = sales_cols[0] if sales_cols else (numeric_cols[0] if numeric_cols else None)

            if target_metric_col:
                total_val = matched_df[target_metric_col].sum()
                avg_val = matched_df[target_metric_col].mean()
                count_val = len(matched_df)
                matched_entity = ' '.join(words).title() if words else "the requested entity"

                if any(k in q_lower for k in ["average", "avg", "mean"]):
                    return f"In **`{filename}`**, the average **{target_metric_col}** for **{matched_entity}** is **{avg_val:,.2f}** ({count_val} matching records found)."
                else:
                    return f"In **`{filename}`**, the total **{target_metric_col}** for **{matched_entity}** is **{total_val:,.2f}** ({count_val} matching records found)."
            else:
                preview = matched_df.dropna(how='all', axis=1).head(10)
                return f"Found **{len(matched_df)}** matching records in **`{filename}`**:\n\n" + preview.to_markdown(index=False)

    # Priority 2: Generative Cortex QA with Document Context
    prompt = f"""
You are an expert data and business analyst answering questions regarding the file '{filename}'.

DATA CONTENT:
{doc_context[:10000]}

USER QUESTION:
{question}

INSTRUCTIONS:
1. Provide a direct, concise, and factual answer using only the figures, facts, and records from the data above.
2. If the user asks for a specific metric (such as county sales, employee name, or list), provide that exact value.
3. If this question cannot be answered from the document above, reply:
   'The uploaded document does not contain information regarding this query.'

ANSWER:
"""
    for model in ['llama3.1-8b', 'mistral-7b']:
        try:
            res = session.sql(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', ?) AS answer", params=[prompt]).collect()
            ans = res[0]["ANSWER"].strip()
            if ans and len(ans) > 2:
                return ans
        except Exception:
            continue

    return f"The uploaded document (`{filename}`) does not contain information to answer this query."

def process_uploaded_document(uploaded_file) -> Tuple[str, Optional[pd.DataFrame], Optional[str]]:
    uploaded_file.seek(0)
    filename = uploaded_file.name
    file_bytes = uploaded_file.read()
    if not file_bytes:
        return f"The uploaded file `{filename}` is empty.", None, None

    fname_lower = filename.lower()
    if fname_lower.endswith((".csv", ".xlsx", ".xls")):
        if fname_lower.endswith(".csv"):
            try:
                df = pd.read_csv(io.BytesIO(file_bytes))
            except Exception:
                df = pd.read_csv(io.BytesIO(file_bytes), encoding='latin1')
        else:
            df = extract_df_from_xlsx(file_bytes)
            
        clean_df = df.dropna(how='all')
        context_str = f"File: {filename}\nTotal Rows: {len(clean_df)}\nColumns: {', '.join(clean_df.columns)}\n\nDATA PREVIEW AND RECORDS:\n"
        context_str += clean_df.to_string(max_rows=150)
        
        summary = (
            f"Successfully processed **`{filename}`** with **{len(clean_df):,} rows** and **{len(clean_df.columns)} columns**.\n\n"
            f"**Columns:** {', '.join([f'`{col}`' for col in clean_df.columns])}\n\n"
            f"You can now ask questions about the records, values, or metrics in this file."
        )
        return summary, clean_df, context_str
        
    elif fname_lower.endswith(".pdf"):
        txt = extract_text_from_pdf(file_bytes)
        summary = f"Uploaded PDF **`{filename}`** (~{len(txt.split()):,} words). Ready for your questions."
        return summary, None, txt
        
    elif fname_lower.endswith((".docx", ".doc")):
        txt = extract_text_from_docx(file_bytes)
        summary = f"Uploaded Word Document **`{filename}`** (~{len(txt.split()):,} words). Ready for your questions."
        return summary, None, txt
        
    return f"Unsupported format for `{filename}`.", None, None

# ==============================================================================
# 7. CHART RENDERER
# ==============================================================================
def display_chart_tab(df: pd.DataFrame, key_prefix: str = ""):
    if len(df.columns) < 2:
        st.info("At least 2 columns are required to generate visualization.")
        return
    all_cols = list(df.columns)
    col1, col2, col3 = st.columns(3)
    x_col = col1.selectbox("Dimension", all_cols, index=0, key=f"{key_prefix}_x")
    remaining = [c for c in all_cols if c != x_col]
    y_col = col2.selectbox("Metric", remaining, index=0 if remaining else 0, key=f"{key_prefix}_y")
    chart_type = col3.selectbox("Type", ["Bar Chart", "Line Chart", "Area Chart", "Scatter Plot"], key=f"{key_prefix}_t")
    
    chart_df = df.copy()
    if any(k in x_col.lower() for k in ["year", "quarter", "month", "day", "date"]):
        chart_df[x_col] = chart_df[x_col].apply(lambda x: str(int(x)) if pd.notnull(x) and isinstance(x, (int, float)) else str(x))
        
    try:
        if chart_type == "Bar Chart":
            st.bar_chart(chart_df.set_index(x_col)[y_col])
        elif chart_type == "Line Chart":
            st.line_chart(chart_df.set_index(x_col)[y_col])
        elif chart_type == "Area Chart":
            st.area_chart(chart_df.set_index(x_col)[y_col])
        elif chart_type == "Scatter Plot":
            st.scatter_chart(chart_df, x=x_col, y=y_col)
    except Exception as exc:
        st.error(f"Chart render error: {exc}")

# ==============================================================================
# 8. SESSION STATE SETUP
# ==============================================================================
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {}
if "current_session_id" not in st.session_state:
    init_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.current_session_id = init_id
    st.session_state.chat_sessions[init_id] = {
        "title": "New Conversation",
        "messages": [],
        "created_at": datetime.now(),
        "doc_context": None,
        "doc_name": None,
        "doc_df": None
    }
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

current_id = st.session_state.current_session_id
active_session_data = st.session_state.chat_sessions[current_id]
messages = active_session_data["messages"]

logged_in_username = st.session_state.get("username", "admin")
logged_in_name = st.session_state.get("display_name", "Admin User")
logged_in_role = st.session_state.get("role", "Administrator")

# ==============================================================================
# 9. GEMINI-STYLE SIDEBAR
# ==============================================================================
with st.sidebar:
    st.markdown('<div class="new-chat-btn">', unsafe_allow_html=True)
    if st.button("＋  New chat", use_container_width=True):
        new_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.current_session_id = new_id
        st.session_state.chat_sessions[new_id] = {
            "title": f"Chat {len(st.session_state.chat_sessions) + 1}",
            "messages": [],
            "created_at": datetime.now(),
            "doc_context": None,
            "doc_name": None,
            "doc_df": None
        }
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("📎  Upload document", expanded=active_session_data.get("doc_name") is None):
        uploaded_doc = st.file_uploader(
            "Spreadsheet or file",
            type=["csv", "xlsx", "xls", "pdf", "docx"],
            key="doc_uploader",
            label_visibility="collapsed"
        )
        if uploaded_doc is not None:
            if st.button("Analyze & Load to Chat", use_container_width=True, type="secondary"):
                with st.spinner("Processing file..."):
                    summary_text, extracted_df, full_context = process_uploaded_document(uploaded_doc)
                    
                    st.session_state.chat_sessions[current_id]["doc_context"] = full_context
                    st.session_state.chat_sessions[current_id]["doc_name"] = uploaded_doc.name
                    st.session_state.chat_sessions[current_id]["doc_df"] = extracted_df
                    
                    messages.append({
                        "role": "user",
                        "content": f"📎 Uploaded **{uploaded_doc.name}** for analysis."
                    })
                    messages.append({
                        "role": "assistant",
                        "content": summary_text,
                        "source": f"File: {uploaded_doc.name}",
                        "sql": None,
                        "data": extracted_df
                    })
                    if len(messages) == 2:
                        st.session_state.chat_sessions[current_id]["title"] = f"Doc: {uploaded_doc.name[:16]}"
                    st.rerun()

    if active_session_data.get("doc_name"):
        st.caption(f"Active file: **{active_session_data['doc_name']}**")

    st.markdown("<hr style='margin: 16px 0; border: 0; border-top: 1px solid #e5e7eb;'>", unsafe_allow_html=True)
    
    st.markdown("<div style='font-size: 0.76rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;'>Recent</div>", unsafe_allow_html=True)
    
    sessions_sorted = sorted(
        st.session_state.chat_sessions.items(),
        key=lambda kv: kv[1].get("created_at", datetime.now()),
        reverse=True
    )
    for s_id, s_data in sessions_sorted:
        is_active = (s_id == st.session_state.current_session_id)
        title_text = s_data["title"][:22] + "..." if len(s_data["title"]) > 22 else s_data["title"]
        icon = "💬" if not is_active else "👉"
        if st.button(f"{icon}  {title_text}", key=f"hist_{s_id}", use_container_width=True):
            st.session_state.current_session_id = s_id
            st.rerun()

    if len(st.session_state.chat_sessions) > 1:
        if st.button("Clear all chats", use_container_width=True):
            st.session_state.chat_sessions = {}
            init_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.session_state.current_session_id = init_id
            st.session_state.chat_sessions[init_id] = {
                "title": "New Conversation",
                "messages": [],
                "created_at": datetime.now(),
                "doc_context": None,
                "doc_name": None,
                "doc_df": None
            }
            st.rerun()

    st.markdown("<div style='margin-top: 50px;'></div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="user-footer-card">
        <div>
            <div style="font-weight: 600; font-size: 0.88rem; color: #111827;">{logged_in_name}</div>
            <div style="font-size: 0.75rem; color: #6b7280;">@{logged_in_username} · {logged_in_role}</div>
        </div>
        <span class="brand-dilytics">DILYTICS</span>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Log out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.display_name = None
        st.rerun()

# ==============================================================================
# 10. MAIN CHAT WORKSPACE
# ==============================================================================
st.markdown('<div class="gemini-header-title">✨ Sales Copilot</div>', unsafe_allow_html=True)
st.markdown('<div class="gemini-header-sub">Ask questions in natural language across your data mart and uploaded files</div>', unsafe_allow_html=True)

onboarding_pills = [
    ("Total Sales", "What is the total sales amount?"),
    ("Sales by Customer", "What are the total sales by customer?"),
    ("Top Products", "What are the top products by sales?"),
    ("Sales by Region", "What are total sales by customer region?"),
    ("Sales in 2000", "What were the total sales in 2000?")
]
pill_cols = st.columns(len(onboarding_pills))
for col, (label, question) in zip(pill_cols, onboarding_pills):
    with col:
        if st.button(label, key=f"pill_{label}", use_container_width=True):
            st.session_state.pending_question = question
            st.rerun()

st.markdown("<hr style='margin: 12px 0 20px 0; border: 0; border-top: 1px solid #f3f4f6;'>", unsafe_allow_html=True)

# Render Chat History
for idx, msg in enumerate(messages):
    with st.chat_message(msg["role"]):
        if msg.get("source"):
            source_class = "badge-snowflake" if "Snowflake" in msg["source"] else "badge-doc"
            st.markdown(f'<span class="source-badge {source_class}">📌 Source: {msg["source"]}</span>', unsafe_allow_html=True)
            
        st.markdown(msg["content"])
        if msg.get("sql"):
            with st.expander("Generated SQL Query", expanded=False):
                st.code(msg["sql"], language="sql")
        if msg.get("data") is not None and not msg["data"].empty:
            tab_data, tab_chart = st.tabs(["Data Table 📄", "Visualization 📈"])
            with tab_data:
                st.dataframe(msg["data"], use_container_width=True)
            with tab_chart:
                display_chart_tab(msg["data"], key_prefix=f"hist_{current_id}_{idx}")

# Interactive Source Toggle
has_active_doc = active_session_data.get("doc_name") is not None
active_file_name = active_session_data.get("doc_name", "")
doc_choice_label = f"📄 Document: {active_file_name[:20]}..." if has_active_doc else "📄 Document (Upload in sidebar)"

mode_col, _ = st.columns([3, 3])
with mode_col:
    query_target = st.radio(
        "Select target data source",
        options=["❄️ Snowflake Data Mart", doc_choice_label],
        index=1 if has_active_doc else 0,
        horizontal=True,
        label_visibility="collapsed"
    )

user_prompt = st.chat_input("Ask a question about sales, products, trends, or your uploaded file...")
if st.session_state.pending_question:
    user_prompt = st.session_state.pending_question
    st.session_state.pending_question = None

if user_prompt:
    if len(messages) == 0:
        st.session_state.chat_sessions[current_id]["title"] = user_prompt[:26] + ("..." if len(user_prompt) > 26 else "")
    
    messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        doc_ctx = st.session_state.chat_sessions[current_id].get("doc_context")
        doc_fname = st.session_state.chat_sessions[current_id].get("doc_name")
        doc_df = st.session_state.chat_sessions[current_id].get("doc_df")
        
        response_text = ""
        sql_query = None
        df_result = None
        source_label = ""

        # Branch 1: User explicitly routed to the Document
        if "📄 Document" in query_target:
            if not has_active_doc:
                response_text = "No document is currently active in this conversation. Please upload a spreadsheet or file in the sidebar, or switch the toggle to **❄️ Snowflake Data Mart**."
                st.warning(response_text)
                source_label = "Document Query (No file attached)"
            else:
                source_label = f"File: {doc_fname}"
                with st.spinner(f"Analyzing `{doc_fname}`..."):
                    response_text = answer_user_question_on_document(user_prompt, doc_ctx, doc_fname, df=doc_df)
                    st.markdown(f'<span class="source-badge badge-doc">📌 Source: {source_label}</span>', unsafe_allow_html=True)
                    st.markdown(response_text)

        # Branch 2: User explicitly routed to Snowflake Data Mart
        else:
            source_label = "Snowflake Data Mart (CORTEX.MART)"
            with st.spinner("Analyzing Snowflake Data Mart..."):
                explanation, sql_query = generate_sql_for_database(user_prompt)
                
                st.markdown(f'<span class="source-badge badge-snowflake">📌 Source: {source_label}</span>', unsafe_allow_html=True)
                if sql_query:
                    st.markdown(explanation)
                    response_text = explanation
                    with st.expander("Generated SQL Query", expanded=False):
                        st.code(sql_query, language="sql")
                    try:
                        df_result = session.sql(sql_query).to_pandas()
                        if df_result is not None and not df_result.empty:
                            tab_data, tab_chart = st.tabs(["Data Table 📄", "Visualization 📈"])
                            with tab_data:
                                st.dataframe(df_result, use_container_width=True)
                            with tab_chart:
                                display_chart_tab(df_result, key_prefix=f"live_{current_id}")
                        else:
                            st.info("The query executed successfully but returned no records.")
                    except Exception as e:
                        st.error(f"Query execution error: {str(e)}")
                else:
                    response_text = explanation
                    st.markdown(response_text)

        messages.append({
            "role": "assistant",
            "content": response_text,
            "source": source_label,
            "sql": sql_query,
            "data": df_result
        })
    st.rerun()
