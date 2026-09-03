import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
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
    page_title="Sales AI Copilot",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. SEMANTIC MODEL CONFIGURATION
# ==============================================================================
DATABASE = "CORTEX"
SCHEMA = "MART"
STAGE = "CORTEX_MODELS_STAGE"
FILE = "sales_intelligence_model.yaml"

# ==============================================================================
# 3. BULLETPROOF USER AUTHENTICATION
# ==============================================================================
USER_DATABASE = {
    "admin": {
        "password": "Copilot@2026",
        "name": "Admin User",
        "role": "ACCOUNTADMIN"
    },
    "analyst": {
        "password": "Copilot@2026",
        "name": "Sales Analyst",
        "role": "ANALYST"
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
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="background: linear-gradient(180deg, #ede9fe 0%, #f5f3ff 100%); 
                    border: 1px solid #ddd6fe; padding: 32px; border-radius: 16px; 
                    box-shadow: 0 4px 20px rgba(109, 40, 217, 0.1); text-align: center;">
            <h2 style="color: #4c1d95; margin-bottom: 4px;">⚡ Sales AI Copilot</h2>
            <p style="color: #6d28d9; font-size: 0.9rem; margin-bottom: 24px;">Please sign in to access enterprise sales intelligence</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            username_input = st.text_input("Username", placeholder="e.g. admin or analyst")
            password_input = st.text_input("Password", type="password", placeholder="••••••••")
            submit_button = st.form_submit_button("🔐 Sign In", use_container_width=True, type="primary")

            if submit_button:
                user_info = USER_DATABASE.get(username_input.strip().lower())
                if user_info and user_info["password"] == password_input:
                    st.session_state.authenticated = True
                    st.session_state.username = username_input.strip().lower()
                    st.session_state.display_name = user_info["name"]
                    st.session_state.role = user_info["role"]
                    st.rerun()
                else:
                    st.error("Invalid Username or Password. Please try again.")

if not st.session_state.authenticated:
    render_login_form()
    st.stop()

# ==============================================================================
# 4. SECURE SNOWFLAKE CONNECTION (From st.secrets)
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
# 5. SEMANTIC MODEL INGESTION (READ DIRECTLY FROM SNOWFLAKE STAGE)
# ==============================================================================
@st.cache_data(show_spinner=False)
def load_semantic_model_yaml() -> str:
    stage_path = f"@{DATABASE}.{SCHEMA}.{STAGE}/{FILE}"
    try:
        stream = session.file.get_stream(stage_path)
        return stream.read().decode("utf-8")
    except Exception as exc:
        return f"# Stage read error: {str(exc)}\nDatabase: {DATABASE}, Schema: {SCHEMA}"

SEMANTIC_YAML_TEXT = load_semantic_model_yaml()

# ==============================================================================
# 6. ENLARGED RECTANGULAR RED DILYTICS LOGO (NATIVE HTML/CSS)
# ==============================================================================
DILYTICS_LOGO_HTML = """
<div style="
    background-color: #D50000;
    border-radius: 14px;
    padding: 16px 20px;
    display: flex;
    justify-content: center;
    align-items: center;
    box-shadow: 0 6px 18px rgba(213, 0, 0, 0.28);
    margin: 6px auto 18px auto;
    width: 100%;
    max-width: 250px;
">
    <span style="
        color: #FFFFFF;
        font-family: 'Arial Black', Arial, Helvetica, sans-serif;
        font-size: 2rem;
        font-weight: 900;
        letter-spacing: 3px;
        text-align: center;
        line-height: 1;
    ">DILYTICS</span>
</div>
"""

# ==============================================================================
# 7. CSS STYLING
# ==============================================================================
st.markdown("""
<style>
    section[data-testid="stSidebar"] {
        background-color: #ede9fe !important;
        border-right: 1px solid #ddd6fe !important;
    }
    .datetime-pill {
        display: inline-block;
        background-color: #6d28d9;
        color: #f5f3ff;
        border: 1px solid #7c3aed;
        border-radius: 12px;
        padding: 4px 14px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-bottom: 6px;
    }
    .user-pill {
        display: inline-block;
        background-color: #ffffff;
        color: #4c1d95;
        border: 1px solid #ddd6fe;
        border-radius: 12px;
        padding: 4px 14px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .yaml-pill {
        display: inline-block;
        background-color: #047857;
        color: #ecfdf5;
        border: 1px solid #059669;
        border-radius: 12px;
        padding: 3px 12px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-bottom: 14px;
    }
    .chat-group-label {
        font-size: 0.7rem;
        font-weight: 700;
        color: #7c3aed;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 10px;
        margin-bottom: 4px;
    }
    div[data-testid="stButton"] > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease-in-out;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 8. DOCUMENT PARSERS & DOCUMENT QA
# ==============================================================================
def extract_df_from_xlsx(file_bytes: bytes) -> pd.DataFrame:
    try:
        return pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception:
        pass

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                ss_tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
                for si in ss_tree.iterfind('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                    t_nodes = si.iterfind('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                    shared_strings.append("".join([n.text or "" for n in t_nodes]))

            sheet_files = [n for n in z.namelist() if n.startswith('xl/worksheets/sheet')]
            if sheet_files:
                sheet_tree = ET.fromstring(z.read(sheet_files[0]))
                rows_data = []
                for row in sheet_tree.iterfind('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                    row_cells = []
                    for c in row.iterfind('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                        val_node = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                        cell_val = val_node.text if val_node is not None else ""
                        if c.attrib.get('t') == 's' and cell_val.isdigit():
                            idx = int(cell_val)
                            cell_val = shared_strings[idx] if idx < len(shared_strings) else cell_val
                        row_cells.append(cell_val)
                    if any(row_cells):
                        rows_data.append(row_cells)

                if rows_data:
                    headers = [h if str(h).strip() else f"Col_{i+1}" for i, h in enumerate(rows_data[0])]
                    df = pd.DataFrame(rows_data[1:], columns=headers)
                    for col in df.columns:
                        try:
                            df[col] = pd.to_numeric(df[col])
                        except (ValueError, TypeError):
                            pass
                    return df
    except Exception:
        pass

    for delimiter in [',', '\t', ';']:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), sep=delimiter, encoding='utf-8')
            if len(df.columns) > 1:
                return df
        except Exception:
            pass

    raise ValueError("Unable to parse Excel file. Please ensure it is saved as an .xlsx or .csv.")

def extract_text_from_pdf(file_bytes: bytes) -> str:
    if pypdf is None:
        return "PDF text extraction requires the pypdf library."
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text.strip()
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
            
            full_text = "".join(text_pieces)
            clean_text = re.sub(r'\n\s*\n+', '\n\n', full_text).strip()
            return clean_text
    except Exception as exc:
        return f"Error extracting Word document: {str(exc)}"

def generate_comprehensive_summary(text: str, filename: str) -> str:
    if not text.strip():
        return "The document contains no readable text."
    
    prompt = (
        f"You are a senior business intelligence analyst. Provide a comprehensive, detailed, "
        f"and structured summary of '{filename}'. Include key facts, figures, topics, and takeaways:\n\n{text[:15000]}"
    )
    for model in ['llama3.1-8b', 'mistral-7b', 'snowflake-arctic']:
        try:
            res = session.sql(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', ?) AS summary", params=[prompt]).collect()
            ans = res[0]["SUMMARY"]
            if ans and len(ans.strip()) > 50:
                return ans
        except Exception:
            continue

    paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 30]
    return "**Extractive Document Summary:**\n\n" + "\n\n".join([f"• {p}" for p in paragraphs[:6]])

def answer_from_document_context(question: str, doc_context: str, filename: str) -> str:
    prompt = (
        f"You are answering questions about '{filename}'. Answer using ONLY the provided text. "
        f"If the information is not in the text, reply strictly: 'There is no information regarding this in the uploaded document.'\n\n"
        f"DOCUMENT:\n{doc_context[:15000]}\n\n"
        f"QUESTION: {question}\n\nANSWER:"
    )
    for model in ['llama3.1-8b', 'mistral-7b', 'snowflake-arctic']:
        try:
            res = session.sql(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', ?) AS answer", params=[prompt]).collect()
            return res[0]["ANSWER"]
        except Exception:
            continue

    q_words = [w.lower() for w in re.findall(r'\w+', question) if len(w) > 3]
    matches = [line.strip() for line in doc_context.split('\n') if any(w in line.lower() for w in q_words) and len(line.strip()) > 20]
    if matches:
        return "**Found relevant information:**\n\n" + "\n\n".join([f"• {m}" for m in matches[:4]])
    return "There is no information regarding this in the uploaded document."

def analyze_tabular_data(df: pd.DataFrame, filename: str) -> Tuple[str, Optional[pd.DataFrame]]:
    num_rows, num_cols = df.shape
    missing_vals = df.isnull().sum().sum()
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    analysis = f"### 📊 Document Analysis: `{filename}`\n\n"
    analysis += f"**Dataset Overview:**\n"
    analysis += f"- **Dimensions:** {num_rows:,} rows × {num_cols} columns\n"
    analysis += f"- **Missing Values:** {missing_vals:,}\n"
    analysis += f"- **Numeric Fields ({len(numeric_cols)}):** {', '.join(numeric_cols) if numeric_cols else 'None'}\n"
    analysis += f"- **Categorical Fields ({len(categorical_cols)}):** {', '.join(categorical_cols) if categorical_cols else 'None'}\n\n"
    
    if numeric_cols:
        analysis += "**Summary Statistics:**\n"
        for col in numeric_cols[:4]:
            analysis += f"- **{col}**: Total = `{df[col].sum():,.2f}`, Avg = `{df[col].mean():,.2f}`, Min = `{df[col].min():,.2f}`, Max = `{df[col].max():,.2f}`\n"
            
    return analysis, df

def process_uploaded_document(uploaded_file) -> Tuple[str, Optional[pd.DataFrame], Optional[str]]:
    uploaded_file.seek(0)
    filename = uploaded_file.name
    file_bytes = uploaded_file.read()
    
    if not file_bytes:
        return f"File `{filename}` is empty or could not be read.", None, None

    fname_lower = filename.lower()
    
    if fname_lower.endswith(".csv"):
        try:
            df = pd.read_csv(io.BytesIO(file_bytes))
        except Exception:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding='latin1')
        summary, df_out = analyze_tabular_data(df, filename)
        return summary, df_out, df.to_string(max_rows=100)
        
    elif fname_lower.endswith((".xlsx", ".xls")):
        try:
            df = extract_df_from_xlsx(file_bytes)
            summary, df_out = analyze_tabular_data(df, filename)
            return summary, df_out, df.to_string(max_rows=100)
        except Exception as e:
            return f"Error analyzing Excel file `{filename}`: {str(e)}", None, None
        
    elif fname_lower.endswith(".pdf"):
        extracted = extract_text_from_pdf(file_bytes)
        if not extracted or not extracted.strip():
            return f"No readable text could be extracted from `{filename}`.", None, None
        summary = generate_comprehensive_summary(extracted, filename)
        explanation = (
            f"### 📄 Document Analysis: `{filename}`\n\n"
            f"- **File Type:** Adobe PDF Document\n"
            f"- **Word Count:** ~{len(extracted.split()):,} words\n\n"
            f"**Comprehensive Summary & Key Insights:**\n\n{summary}"
        )
        return explanation, None, extracted
        
    elif fname_lower.endswith((".docx", ".doc")):
        extracted = extract_text_from_docx(file_bytes)
        if not extracted or not extracted.strip():
            return f"No readable text could be extracted from `{filename}`.", None, None
        summary = generate_comprehensive_summary(extracted, filename)
        explanation = (
            f"### 📝 Word Document Analysis: `{filename}`\n\n"
            f"- **File Type:** Microsoft Word Document\n"
            f"- **Word Count:** ~{len(extracted.split()):,} words\n\n"
            f"**Comprehensive Summary & Key Insights:**\n\n{summary}"
        )
        return explanation, None, extracted
        
    return f"Unsupported file type for `{filename}`.", None, None

# ==============================================================================
# 9. DETERMINISTIC & SEMANTIC-GROUNDED SQL GENERATOR
# ==============================================================================
def generate_sql_from_prompt(prompt: str) -> Tuple[str, Optional[str]]:
    p = prompt.lower().strip()

    # 1. Greetings & Conversational
    if p in ["hi", "hello", "hey", "help", "who are you", "good morning", "good evening"]:
        return "Hello! I am your Sales AI Copilot. Ask any question about revenue, orders, customers, products, regions, or time trends!", None

    if any(greet in p for greet in ["how are you", "what's up", "whats up"]):
        return "I'm ready to help you analyze sales data! Ask any question about metrics, trends, or catalog performance.", None

    # 2. Metric Aggregation Resolution
    if any(k in p for k in ["average", "avg", "mean"]):
        agg_func = "AVG"
        alias = "AVG_SALES"
        metric_desc = "average order sales"
    elif any(k in p for k in ["count", "number of orders", "order volume", "how many orders", "order count"]):
        agg_func = "COUNT(DISTINCT"
        alias = "ORDER_COUNT"
        metric_desc = "total order count"
    elif any(k in p for k in ["min", "minimum", "lowest"]):
        agg_func = "MIN"
        alias = "MIN_SALES"
        metric_desc = "minimum sales amount"
    elif any(k in p for k in ["max", "maximum", "highest"]):
        agg_func = "MAX"
        alias = "MAX_SALES"
        metric_desc = "maximum sales amount"
    else:
        agg_func = "SUM"
        alias = "TOTAL_SALES"
        metric_desc = "total sales revenue"

    if agg_func == "COUNT(DISTINCT":
        metric_expr = "COUNT(DISTINCT f.order_id)"
        item_metric_expr = "COUNT(DISTINCT i.order_id)"
    else:
        metric_expr = f"ROUND({agg_func}(f.total_amount), 2)"
        item_metric_expr = f"ROUND({agg_func}(i.line_total), 2)"

    # 3. Dimension Resolution against Semantic Mart

    # Region
    if "region" in p and not any(k in p for k in ["rep", "sales rep"]):
        sql = f"""
SELECT 
    c.region,
    {metric_expr} AS {alias}
FROM CORTEX.MART.FACT_SALES f
JOIN CORTEX.MART.DIM_CUSTOMER c ON f.customer_id = c.customer_id
GROUP BY c.region
ORDER BY {alias} DESC
        """.strip()
        return f"Calculating {metric_desc} grouped by customer region.", sql

    # Year / Annual Trend
    if any(k in p for k in ["year", "yearly", "annual", "year wise", "year-wise"]):
        sql = f"""
SELECT 
    d.year,
    {metric_expr} AS {alias}
FROM CORTEX.MART.FACT_SALES f
JOIN CORTEX.MART.DIM_DATE d ON f.order_date = d.date_key
GROUP BY d.year
ORDER BY d.year ASC
        """.strip()
        return f"Aggregating {metric_desc} by calendar year.", sql

    # Month / Monthly Trend
    if any(k in p for k in ["month", "monthly"]):
        sql = f"""
SELECT 
    d.year,
    d.month,
    d.month_name,
    {metric_expr} AS {alias}
FROM CORTEX.MART.FACT_SALES f
JOIN CORTEX.MART.DIM_DATE d ON f.order_date = d.date_key
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month ASC
        """.strip()
        return f"Aggregating {metric_desc} across monthly periods.", sql

    # Customer Name / Top Customers
    if "customer" in p and not any(k in p for k in ["region", "industry", "type", "tier"]):
        sql = f"""
SELECT 
    c.customer_name,
    {metric_expr} AS {alias}
FROM CORTEX.MART.FACT_SALES f
JOIN CORTEX.MART.DIM_CUSTOMER c ON f.customer_id = c.customer_id
GROUP BY c.customer_name
ORDER BY {alias} DESC
LIMIT 15
        """.strip()
        return f"Calculating {metric_desc} by customer name.", sql

    # Product Name / Top Products
    if "product" in p and not any(k in p for k in ["category", "brand"]):
        sql = f"""
SELECT 
    p.product_name,
    {item_metric_expr} AS {alias}
FROM CORTEX.MART.FACT_SALES_ITEM i
JOIN CORTEX.MART.DIM_PRODUCT p ON i.product_id = p.product_id
GROUP BY p.product_name
ORDER BY {alias} DESC
LIMIT 10
        """.strip()
        return f"Ranking products by {metric_desc}.", sql

    # Category
    if any(k in p for k in ["category", "sub-category", "subcategory"]):
        sql = f"""
SELECT 
    p.category,
    SUM(i.quantity) AS UNITS_SOLD,
    {item_metric_expr} AS {alias}
FROM CORTEX.MART.FACT_SALES_ITEM i
JOIN CORTEX.MART.DIM_PRODUCT p ON i.product_id = p.product_id
GROUP BY p.category
ORDER BY {alias} DESC
        """.strip()
        return f"Evaluating {metric_desc} by product category.", sql

    # Brand
    if "brand" in p:
        sql = f"""
SELECT 
    p.brand,
    SUM(i.quantity) AS UNITS_SOLD,
    {item_metric_expr} AS {alias}
FROM CORTEX.MART.FACT_SALES_ITEM i
JOIN CORTEX.MART.DIM_PRODUCT p ON i.product_id = p.product_id
GROUP BY p.brand
ORDER BY {alias} DESC
        """.strip()
        return f"Evaluating {metric_desc} by brand.", sql

    # Channel
    if "channel" in p:
        sql = f"""
SELECT 
    f.order_channel,
    COUNT(DISTINCT f.order_id) AS ORDER_COUNT,
    {metric_expr} AS {alias}
FROM CORTEX.MART.FACT_SALES f
GROUP BY f.order_channel
ORDER BY {alias} DESC
        """.strip()
        return f"Analyzing {metric_desc} by sales channel.", sql

    # Sales Rep
    if any(k in p for k in ["rep", "salesperson", "representative"]):
        sql = f"""
SELECT 
    r.sales_rep_name,
    r.region AS REP_REGION,
    COUNT(DISTINCT f.order_id) AS ORDER_COUNT,
    {metric_expr} AS {alias}
FROM CORTEX.MART.FACT_SALES f
JOIN CORTEX.MART.DIM_SALES_REP r ON f.sales_rep_id = r.sales_rep_id
GROUP BY r.sales_rep_name, r.region
ORDER BY {alias} DESC
LIMIT 10
        """.strip()
        return f"Evaluating representative performance by {metric_desc}.", sql

    # Overall Metric (Single Total)
    if any(k in p for k in ["total sales", "total revenue", "overall sales", "average sales", "avg sales", "order count"]):
        sql = f"SELECT {metric_expr} AS {alias} FROM CORTEX.MART.FACT_SALES f"
        return f"Calculating overall {metric_desc}.", sql

    # 4. Snowflake Cortex LLM Fallback (Using Semantic YAML Context)
    schema_prompt = (
        f"You are a Snowflake SQL generator for a sales data mart in CORTEX.MART.\n"
        f"Semantic Model Overview:\n{SEMANTIC_YAML_TEXT[:6000]}\n\n"
        f"Generate ONLY valid, executable Snowflake SQL without markdown formatting or backticks for: {prompt}"
    )
    for model in ['llama3.1-8b', 'mistral-7b']:
        try:
            res = session.sql(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', ?) AS sql_out", params=[schema_prompt]).collect()
            raw_sql = res[0]["SQL_OUT"].strip()
            clean_sql = re.sub(r"^```(sql)?", "", raw_sql, flags=re.IGNORECASE).strip().rstrip("`").strip()
            if clean_sql.lower().startswith("select") or clean_sql.lower().startswith("with"):
                return f"Semantic SQL query generated for: **{prompt}**", clean_sql
        except Exception:
            continue

    return "", None

# ==============================================================================
# 10. CHART RENDERER
# ==============================================================================
def display_chart_tab(df: pd.DataFrame, key_prefix: str = ""):
    if len(df.columns) < 2:
        st.info("At least 2 columns are required to render visualization.")
        return
    all_cols = list(df.columns)
    col1, col2, col3 = st.columns(3)
    
    x_col = col1.selectbox("Dimension (X-axis)", all_cols, index=0, key=f"{key_prefix}_x")
    remaining = [c for c in all_cols if c != x_col]
    y_col = col2.selectbox("Metric (Y-axis)", remaining, index=0 if remaining else 0, key=f"{key_prefix}_y")
    chart_type = col3.selectbox("Chart Type", ["Bar Chart", "Line Chart", "Area Chart", "Scatter Plot"], key=f"{key_prefix}_t")
    
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
        st.error(f"Chart error: {exc}")

# ==============================================================================
# 11. ONBOARDING QUESTIONS SETUP
# ==============================================================================
SUGGESTED_QUESTIONS = [
    {"icon": "💰", "label": "Total Sales", "question": "What is the total sales revenue?",
     "detail": "Calculates gross sales revenue from fact tables defined in the semantic model."},
    {"icon": "👥", "label": "Sales by Customer", "question": "What are total sales by customer?",
     "detail": "Ranks customer accounts by sales revenue."},
    {"icon": "📦", "label": "Top Products", "question": "What are the top 10 products by sales?",
     "detail": "Ranks individual catalog products by line-item sales volume."},
    {"icon": "🌍", "label": "Avg Sales by Region", "question": "What is the average sales by region?",
     "detail": "Evaluates average order revenue across customer geographic regions."},
    {"icon": "📈", "label": "Yearly Sales Trend", "question": "Show year wise sales",
     "detail": "Evaluates annual sales totals across sequential calendar years."},
]

# ==============================================================================
# 12. SESSION STATE MANAGEMENT
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
        "doc_name": None
    }
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

current_id = st.session_state.current_session_id
active_session_data = st.session_state.chat_sessions[current_id]
messages = active_session_data["messages"]

logged_in_username = st.session_state.get("username", "admin")
logged_in_name = st.session_state.get("display_name", "Admin User")

# ==============================================================================
# 13. SIDEBAR
# ==============================================================================
with st.sidebar:
    st.markdown(DILYTICS_LOGO_HTML, unsafe_allow_html=True)

    st.markdown(
        f'<div style="text-align:center;">'
        f'<span class="datetime-pill">📅 {datetime.now().strftime("%b %d, %Y")}</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div style="text-align:center;">'
        f'<span class="user-pill">👤 {logged_in_username} · {logged_in_name}</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div style="text-align:center;">'
        f'<span class="yaml-pill">🔗 Model: {FILE}</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.display_name = None
        st.rerun()

    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        new_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.current_session_id = new_id
        st.session_state.chat_sessions[new_id] = {
            "title": f"Chat {len(st.session_state.chat_sessions) + 1}",
            "messages": [],
            "created_at": datetime.now(),
            "doc_context": None,
            "doc_name": None
        }
        st.rerun()

    st.markdown("---")
    
    st.markdown("##### 📁 Document Analysis")
    uploaded_doc = st.file_uploader(
        "Upload a document or report",
        type=["csv", "xlsx", "xls", "pdf", "docx"],
        key="doc_uploader",
        help="Upload CSV/Excel sheets or PDF/Word documents for automated extraction, summaries, and conversational Q&A."
    )
    if uploaded_doc is not None:
        if st.button("⚡ Analyze Document", use_container_width=True, type="secondary"):
            with st.spinner(f"Analyzing {uploaded_doc.name}..."):
                analysis_text, extracted_df, raw_context = process_uploaded_document(uploaded_doc)
                
                # Scoped to current conversation only
                st.session_state.chat_sessions[current_id]["doc_context"] = raw_context
                st.session_state.chat_sessions[current_id]["doc_name"] = uploaded_doc.name
                
                messages.append({
                    "role": "user",
                    "content": f"📎 Uploaded document for analysis: **{uploaded_doc.name}**"
                })
                messages.append({
                    "role": "assistant",
                    "content": analysis_text,
                    "sql": None,
                    "data": extracted_df
                })
                if len(messages) == 2:
                    st.session_state.chat_sessions[current_id]["title"] = f"Doc: {uploaded_doc.name[:15]}"
                st.rerun()

    st.markdown("---")
    search_term = st.text_input("🔍 Search chats", key="chat_search", placeholder="Search by title...")

    today = datetime.now().date()
    sessions_sorted = sorted(
        st.session_state.chat_sessions.items(),
        key=lambda kv: kv[1].get("created_at", datetime.now()),
        reverse=True
    )
    if search_term:
        sessions_sorted = [(sid, sd) for sid, sd in sessions_sorted if search_term.lower() in sd["title"].lower()]

    today_sessions = [(sid, sd) for sid, sd in sessions_sorted if sd.get("created_at", datetime.now()).date() == today]
    earlier_sessions = [(sid, sd) for sid, sd in sessions_sorted if sd.get("created_at", datetime.now()).date() != today]

    if today_sessions:
        st.markdown('<div class="chat-group-label">Today</div>', unsafe_allow_html=True)
        for s_id, s_data in today_sessions:
            is_active = (s_id == st.session_state.current_session_id)
            label = s_data["title"][:16] + "..." if len(s_data["title"]) > 16 else s_data["title"]
            if st.button(f"{'👉 ' if is_active else '🗨️ '}{label}", key=f"sess_{s_id}", use_container_width=True):
                st.session_state.current_session_id = s_id
                st.rerun()

    if earlier_sessions:
        st.markdown('<div class="chat-group-label">Earlier</div>', unsafe_allow_html=True)
        for s_id, s_data in earlier_sessions:
            is_active = (s_id == st.session_state.current_session_id)
            label = s_data["title"][:16] + "..." if len(s_data["title"]) > 16 else s_data["title"]
            if st.button(f"{'👉 ' if is_active else '🗨️ '}{label}", key=f"sess_{s_id}", use_container_width=True):
                st.session_state.current_session_id = s_id
                st.rerun()

    if not today_sessions and not earlier_sessions:
        st.caption("No chats match your search.")

    st.markdown("---")
    if st.button("🗑️ Clear History", use_container_width=True):
        st.session_state.chat_sessions = {}
        init_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.current_session_id = init_id
        st.session_state.chat_sessions[init_id] = {
            "title": "New Conversation",
            "messages": [],
            "created_at": datetime.now(),
            "doc_context": None,
            "doc_name": None
        }
        st.rerun()

# ==============================================================================
# 14. MAIN AREA
# ==============================================================================
st.title("💬 Sales AI Copilot")
st.caption(f"Semantic Intelligence grounded in `{FILE}` via Snowflake Cortex")

with st.expander("💡 What can I ask this assistant?", expanded=False):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        **🎯 Business Performance & Sales**
        * Track gross revenue, order volume, and average order values.
        * Analyze sales channels (*Web*, *Direct Sales*, *Partners*).
        * Compare quarterly and fiscal performance trends.

        **👥 Customers & Accounts**
        * Breakdown sales by customer industry vertical (*Tech*, *Finance*, *Healthcare*).
        * Segment revenue by account tier (*Enterprise* vs. *SMB*).
        * Explore regional geographic distribution.
        """)
    with col_b:
        st.markdown("""
        **📦 Products & Catalog**
        * Identify top-selling products by units and net revenue.
        * Compare category, sub-category, and brand margins.
        * Monitor volume throughput and average selling prices.

        **🏆 Sales Team & Territories**
        * Track revenue generated per Account Executive.
        * Compare territory quotas and managed order counts.
        * Evaluate rep performance across customer accounts.
        """)

st.markdown("##### 💡 Verified Onboarding Questions from Semantic Model:")
cols = st.columns(len(SUGGESTED_QUESTIONS))
for col, q in zip(cols, SUGGESTED_QUESTIONS):
    with col:
        with st.popover(f"{q['icon']} {q['label']}", use_container_width=True):
            st.markdown(f"**{q['question']}**")
            st.caption(q["detail"])
            if st.button("Ask this question", key=f"ask_{q['label']}", use_container_width=True, type="primary"):
                st.session_state.pending_question = q["question"]
                st.rerun()

st.divider()

for idx, msg in enumerate(messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sql"):
            with st.expander("Generated Semantic SQL", expanded=False):
                st.code(msg["sql"], language="sql")
        if msg.get("data") is not None and not msg["data"].empty:
            tab_data, tab_chart = st.tabs(["Data 📄", "Chart 📈"])
            with tab_data:
                st.dataframe(msg["data"], use_container_width=True)
            with tab_chart:
                display_chart_tab(msg["data"], key_prefix=f"hist_{current_id}_{idx}")

# Handle Chat Input
user_prompt = st.chat_input("Ask a question about sales, products, reps, dates, or channels...")
if st.session_state.pending_question:
    user_prompt = st.session_state.pending_question
    st.session_state.pending_question = None

if user_prompt:
    if len(messages) == 0:
        st.session_state.chat_sessions[current_id]["title"] = user_prompt[:25] + ("..." if len(user_prompt) > 25 else "")
    
    messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        doc_ctx = st.session_state.chat_sessions[current_id].get("doc_context")
        doc_fname = st.session_state.chat_sessions[current_id].get("doc_name")
        
        is_doc_query = doc_ctx is not None and any(k in user_prompt.lower() for k in ["document", "file", "uploaded", "docx", "pdf", "sheet", "summary"])
        
        if is_doc_query:
            with st.spinner(f"Analyzing `{doc_fname}`..."):
                answer = answer_from_document_context(user_prompt, doc_ctx, doc_fname)
                st.markdown(answer)
                messages.append({"role": "assistant", "content": answer, "sql": None, "data": None})
        else:
            with st.spinner("Analyzing question..."):
                explanation, sql_query = generate_sql_from_prompt(user_prompt)
                df = None
                
                if sql_query:
                    st.markdown(explanation)
                    with st.expander("Generated Semantic SQL", expanded=False):
                        st.code(sql_query, language="sql")
                    try:
                        df = session.sql(sql_query).to_pandas()
                        if df is not None and not df.empty:
                            tab_data, tab_chart = st.tabs(["Data 📄", "Chart 📈"])
                            with tab_data:
                                st.dataframe(df, use_container_width=True)
                            with tab_chart:
                                display_chart_tab(df, key_prefix=f"live_{current_id}")
                        else:
                            st.info("The query returned no data.")
                    except Exception as e:
                        st.error(f"SQL Execution Error: {str(e)}")
                elif explanation:
                    st.markdown(explanation)
                elif doc_ctx:
                    answer = answer_from_document_context(user_prompt, doc_ctx, doc_fname)
                    st.markdown(answer)
                    explanation = answer
                else:
                    fallback_text = (
                        "I could not formulate a semantic query for this question. "
                        "Please ask about sales revenue, averages, orders, products, customers, reps, or regions."
                    )
                    st.markdown(fallback_text)
                    explanation = fallback_text

                messages.append({
                    "role": "assistant",
                    "content": explanation,
                    "sql": sql_query,
                    "data": df
                })
        st.rerun()
