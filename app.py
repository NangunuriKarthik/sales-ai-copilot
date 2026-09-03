import base64
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
    page_title="Sales AI Copilot",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. BULLETPROOF NATIVE USER AUTHENTICATION
# ==============================================================================
# User Accounts (Username: {Password, Display Name, Role})
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

# Check if authenticated
if not st.session_state.authenticated:
    render_login_form()
    st.stop()

# ==============================================================================
# 3. SECURE SNOWFLAKE CONNECTION (From st.secrets)
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
# 4. ENLARGED RECTANGULAR RED DILYTICS LOGO
# ==============================================================================
DILYTICS_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 220" width="100%" height="100%">
  <rect width="600" height="220" fill="#D50000" rx="18"/>
  <text x="50%" y="56%" dominant-baseline="middle" text-anchor="middle" 
        font-family="Arial, Helvetica, sans-serif" font-weight="900" font-size="94" 
        fill="#FFFFFF" letter-spacing="4">DILYTICS</text>
</svg>
"""
DILYTICS_LOGO_B64 = base64.b64encode(DILYTICS_SVG.encode("utf-8")).decode("utf-8")

# ==============================================================================
# 5. CSS STYLING
# ==============================================================================
st.markdown("""
<style>
    section[data-testid="stSidebar"] {
        background-color: #ede9fe !important;
        border-right: 1px solid #ddd6fe !important;
    }
    .logo-container {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-top: 6px;
        margin-bottom: 18px;
        width: 100%;
    }
    .logo-container img {
        width: 100%;
        max-width: 250px;
        height: auto;
        border-radius: 12px;
        box-shadow: 0 6px 18px rgba(213, 0, 0, 0.28);
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
# 6. DOCUMENT PARSERS & CORTEX LLM INTEGRATION
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

    for delimiter in [',', '\t', ';', '|']:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), sep=delimiter, encoding='utf-8')
            if len(df.columns) > 1:
                return df
        except Exception:
            pass

    for delimiter in [',', '\t', ';']:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), sep=delimiter, encoding='latin1')
            if len(df.columns) > 1:
                return df
        except Exception:
            pass

    try:
        dfs = pd.read_html(io.BytesIO(file_bytes))
        if dfs:
            return dfs[0]
    except Exception:
        pass

    raise ValueError("Unable to parse Excel file format. Please upload as standard .xlsx or .csv.")

def extract_text_from_pdf(file_bytes: bytes) -> str:
    if pypdf is None:
        return "PDF text extraction requires the `pypdf` package."
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text.strip()
    except Exception as exc:
        return f"Error extracting PDF text: {str(exc)}"

def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            xml_content = z.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            paragraphs = []
            for p in tree.iterfind('.//w:p', namespaces):
                texts = [node.text for node in p.iterfind('.//w:t', namespaces) if node.text]
                if texts:
                    paragraphs.append("".join(texts))
            return "\n\n".join(paragraphs).strip()
    except Exception as exc:
        return f"Error extracting Word document: {str(exc)}"

def fallback_extractive_summary(text: str, filename: str) -> str:
    paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 30]
    key_points = paragraphs[:6] if len(paragraphs) >= 6 else paragraphs
    
    summary = f"**Summary of `{filename}`:**\n\n"
    for pt in key_points:
        clean_pt = re.sub(r'\s+', ' ', pt)
        summary += f"• {clean_pt}\n\n"
    return summary

def generate_comprehensive_summary(text: str, filename: str) -> str:
    if not text.strip():
        return "The document contains no readable text."
    
    prompt = (
        f"You are an expert data and business document analyst. Provide a comprehensive, detailed, "
        f"and structured summary of the document titled '{filename}'. "
        f"Include core themes, key statistics, operational facts, and structural sections. Do not truncate.\n\n"
        f"DOCUMENT CONTENT:\n{text[:15000]}"
    )
    
    for model in ['llama3.1-8b', 'mistral-7b', 'snowflake-arctic']:
        try:
            query = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', ?) AS summary"
            res = session.sql(query, params=[prompt]).collect()
            ans = res[0]["SUMMARY"]
            if ans and len(ans.strip()) > 50:
                return ans
        except Exception:
            continue
            
    return fallback_extractive_summary(text, filename)

def answer_from_document_context(question: str, doc_context: str, filename: str) -> str:
    prompt = (
        f"You are analyzing the document '{filename}'. Answer the user's question using ONLY the provided text. "
        f"If the information is not contained in the document, reply strictly with: "
        f"'There is no information regarding this in the uploaded document.'\n\n"
        f"DOCUMENT TEXT:\n{doc_context[:15000]}\n\n"
        f"QUESTION: {question}\n\n"
        f"ANSWER:"
    )
    for model in ['llama3.1-8b', 'mistral-7b', 'snowflake-arctic']:
        try:
            query = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', ?) AS answer"
            res = session.sql(query, params=[prompt]).collect()
            return res[0]["ANSWER"]
        except Exception:
            continue

    q_words = [w.lower() for w in re.findall(r'\w+', question) if len(w) > 3]
    matches = []
    for line in doc_context.split('\n'):
        if any(w in line.lower() for w in q_words) and len(line.strip()) > 20:
            matches.append(line.strip())
            if len(matches) >= 4:
                break
    if matches:
        return "**Found relevant information in document:**\n\n" + "\n\n".join([f"• {m}" for m in matches])
    return "There is no information regarding this in the uploaded document."

def analyze_tabular_data(df: pd.DataFrame, filename: str) -> Tuple[str, Optional[pd.DataFrame]]:
    num_rows, num_cols = df.shape
    missing_vals = df.isnull().sum().sum()
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    analysis = f"### 📊 Document Analysis: `{filename}`\n\n"
    analysis += f"**Dataset Overview:**\n"
    analysis += f"- **Dimensions:** {num_rows:,} rows × {num_cols} columns\n"
    analysis += f"- **Missing Data Points:** {missing_vals:,} empty cells\n"
    analysis += f"- **Numeric Fields ({len(numeric_cols)}):** {', '.join(numeric_cols) if numeric_cols else 'None'}\n"
    analysis += f"- **Categorical Fields ({len(categorical_cols)}):** {', '.join(categorical_cols) if categorical_cols else 'None'}\n\n"
    
    if numeric_cols:
        analysis += "**Key Statistical Highlights:**\n"
        for col in numeric_cols[:4]:
            analysis += f"- **{col}**: Total = `{df[col].sum():,.2f}`, Avg = `{df[col].mean():,.2f}`, Min = `{df[col].min():,.2f}`, Max = `{df[col].max():,.2f}`\n"
    
    analysis += "\n*Explore the full dataset and interactive visualizations in the tabs below.*"
    return analysis, df

def process_uploaded_document(uploaded_file) -> Tuple[str, Optional[pd.DataFrame], Optional[str]]:
    filename = uploaded_file.name
    file_bytes = uploaded_file.read()
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
        summary = generate_comprehensive_summary(extracted, filename)
        explanation = (
            f"### 📝 Word Document Analysis: `{filename}`\n\n"
            f"- **File Type:** Microsoft Word Document\n"
            f"- **Word Count:** ~{len(extracted.split()):,} words\n\n"
            f"**Comprehensive Summary & Key Insights:**\n\n{summary}"
        )
        return explanation, None, extracted
        
    else:
        return f"Unsupported file type for `{filename}`. Please upload CSV, Excel, PDF, or Word documents.", None, None

# ==============================================================================
# 7. RULE-BASED SQL GENERATOR (MART / YAML SEMANTIC SCHEMA)
# ==============================================================================
def generate_sql_from_prompt(prompt: str) -> Tuple[str, Optional[str]]:
    p = prompt.lower().strip()

    if any(greet in p for greet in ["how are you", "how's it going", "what's up", "whats up"]):
        return "I'm doing well, thank you! I am ready to help you analyze sales revenue, customers, products, reps, and order trends. What business metric would you like to explore?", None
    
    if p in ["hi", "hello", "hey", "help", "good morning", "good evening", "good afternoon"]:
        return "Hello! I am your Sales Intelligence Assistant powered by your semantic data model. Ask any question about sales, products, reps, channels, or regions!", None

    if any(k in p for k in ["total sales", "total revenue", "revenue"]):
        return "Calculating total gross sales across all transactions.", "SELECT SUM(total_amount) AS total_sales FROM CORTEX.MART.FACT_SALES"

    if "by customer" in p or "sales by customer" in p:
        return "Aggregating total sales amount grouped by customer name.", """
            SELECT
              c.customer_name,
              SUM(f.total_amount) AS total_sales
            FROM CORTEX.MART.FACT_SALES f
            JOIN CORTEX.MART.DIM_CUSTOMER c ON f.customer_id = c.customer_id
            GROUP BY c.customer_name
            ORDER BY total_sales DESC
        """.strip()

    if "top product" in p or "top 10 product" in p or "products by sales" in p or "top products" in p:
        return "Ranking top product catalog items by line-item revenue.", """
            SELECT
              p.product_name,
              SUM(i.line_total) AS total_sales
            FROM CORTEX.MART.FACT_SALES_ITEM i
            JOIN CORTEX.MART.DIM_PRODUCT p ON i.product_id = p.product_id
            GROUP BY p.product_name
            ORDER BY total_sales DESC
            LIMIT 10
        """.strip()

    if "by customer region" in p or "by region" in p or "sales by region" in p:
        return "Summarizing total sales revenue by customer sales region.", """
            SELECT
              c.region,
              SUM(f.total_amount) AS total_sales
            FROM CORTEX.MART.FACT_SALES f
            JOIN CORTEX.MART.DIM_CUSTOMER c ON f.customer_id = c.customer_id
            GROUP BY c.region
            ORDER BY total_sales DESC
        """.strip()

    if "month" in p or "monthly sales" in p or "monthly trend" in p:
        return "Aggregating monthly sales volume and revenue.", """
            SELECT
              d.year,
              d.month,
              d.month_name,
              SUM(f.total_amount) AS total_sales
            FROM CORTEX.MART.FACT_SALES f
            JOIN CORTEX.MART.DIM_DATE d ON f.order_date = d.date_key
            GROUP BY d.year, d.month, d.month_name
            ORDER BY d.year, d.month
        """.strip()

    if "channel" in p:
        return "Evaluating gross sales and percentage distribution by sales channel.", """
            WITH channel_sales AS (
              SELECT order_channel, SUM(total_amount) AS total_sales
              FROM CORTEX.MART.FACT_SALES
              GROUP BY order_channel
            )
            SELECT 
              order_channel, 
              total_sales,
              ROUND(100 * total_sales / SUM(total_sales) OVER (), 2) AS sales_percentage
            FROM channel_sales
            ORDER BY total_sales DESC
        """.strip()

    if "category" in p or "sub_category" in p or "subcategory" in p:
        return "Evaluating revenue contribution by product category.", """
            SELECT 
              p.category, 
              SUM(i.quantity) AS units_sold,
              SUM(i.line_total) AS total_sales
            FROM CORTEX.MART.FACT_SALES_ITEM i
            JOIN CORTEX.MART.DIM_PRODUCT p ON i.product_id = p.product_id
            GROUP BY p.category
            ORDER BY total_sales DESC
        """.strip()

    if "rep" in p or "salesperson" in p or "representative" in p:
        return "Summarizing order volume and total revenue managed by sales reps.", """
            SELECT 
              r.sales_rep_name, 
              r.region AS rep_region,
              COUNT(f.order_id) AS order_count,
              SUM(f.total_amount) AS total_sales
            FROM CORTEX.MART.FACT_SALES f
            JOIN CORTEX.MART.DIM_SALES_REP r ON f.sales_rep_id = r.sales_rep_id
            GROUP BY r.sales_rep_name, r.region
            ORDER BY total_sales DESC
            LIMIT 10
        """.strip()

    if any(k in p for k in ["industry", "customer type", "tier", "enterprise"]):
        return "Analyzing customer sales across industry verticals and customer tiers.", """
            SELECT 
              c.customer_type, 
              c.industry, 
              COUNT(DISTINCT f.order_id) AS order_count,
              SUM(f.total_amount) AS total_sales
            FROM CORTEX.MART.FACT_SALES f
            JOIN CORTEX.MART.DIM_CUSTOMER c ON f.customer_id = c.customer_id
            GROUP BY c.customer_type, c.industry
            ORDER BY total_sales DESC
        """.strip()

    if "brand" in p:
        return "Analyzing unit volume and line revenue by brand.", """
            SELECT 
              p.brand, 
              SUM(i.quantity) AS units_sold,
              SUM(i.line_total) AS total_sales
            FROM CORTEX.MART.FACT_SALES_ITEM i
            JOIN CORTEX.MART.DIM_PRODUCT p ON i.product_id = p.product_id
            GROUP BY p.brand
            ORDER BY total_sales DESC
        """.strip()

    if any(k in p for k in ["fiscal", "fy", "fq"]):
        return "Tracking sales performance across fiscal periods.", """
            SELECT 
              d.fiscal_year, 
              d.fiscal_quarter, 
              SUM(f.total_amount) AS total_sales
            FROM CORTEX.MART.FACT_SALES f
            JOIN CORTEX.MART.DIM_DATE d ON f.order_date = d.date_key
            GROUP BY d.fiscal_year, d.fiscal_quarter
            ORDER BY d.fiscal_year, d.fiscal_quarter
        """.strip()

    domain_keywords = [
        "sales", "order", "revenue", "product", "customer", "rep", "date", 
        "month", "year", "brand", "item", "discount", "tax", "shipping", 
        "category", "price", "unit", "channel", "account", "industry", "region"
    ]
    if any(word in p for word in domain_keywords):
        return "Displaying recent transactions with customer and representative context:", """
            SELECT 
                f.order_id,
                f.order_date,
                c.customer_name,
                r.sales_rep_name,
                f.order_status,
                f.order_channel,
                f.total_amount
            FROM CORTEX.MART.FACT_SALES f
            LEFT JOIN CORTEX.MART.DIM_CUSTOMER c ON f.customer_id = c.customer_id
            LEFT JOIN CORTEX.MART.DIM_SALES_REP r ON f.sales_rep_id = r.sales_rep_id
            ORDER BY f.order_date DESC
            LIMIT 20
        """.strip()

    return "", None

# ==============================================================================
# 8. CHART RENDERER
# ==============================================================================
def display_chart_tab(df: pd.DataFrame, key_prefix: str = ""):
    if len(df.columns) < 2:
        st.info("Need at least 2 columns to render a chart.")
        return
    all_cols = list(df.columns)
    col1, col2, col3 = st.columns(3)
    
    x_key = f"{key_prefix}_x" if key_prefix else "x_axis"
    y_key = f"{key_prefix}_y" if key_prefix else "y_axis"
    t_key = f"{key_prefix}_type" if key_prefix else "chart_type"
    
    x_col = col1.selectbox("Dimension (X-axis)", all_cols, index=0, key=x_key)
    remaining_cols = [c for c in all_cols if c != x_col]
    y_col = col2.selectbox("Metric (Y-axis)", remaining_cols, index=0 if remaining_cols else 0, key=y_key)
    chart_type = col3.selectbox("Chart Type", ["Bar Chart", "Line Chart", "Area Chart", "Scatter Plot"], key=t_key)
    
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
        st.error(f"Chart creation error: {exc}")

# ==============================================================================
# 9. ONBOARDING QUESTIONS SETUP
# ==============================================================================
SUGGESTED_QUESTIONS = [
    {"icon": "💰", "label": "Total Sales", "question": "What is the total sales amount?",
     "detail": "Returns the gross sales revenue across all completed and logged transactions."},
    {"icon": "👥", "label": "Sales by Customer", "question": "What are total sales by customer?",
     "detail": "Aggregates revenue per customer account to highlight high-value partnerships."},
    {"icon": "📦", "label": "Top Products", "question": "What are the top products by sales?",
     "detail": "Ranks individual catalog products by line-item sales volume and revenue."},
    {"icon": "🌍", "label": "Sales by Region", "question": "What are total sales by customer region?",
     "detail": "Summarizes commercial sales distributed across customer geographic territories."},
    {"icon": "📈", "label": "Monthly Sales", "question": "Show monthly sales trend",
     "detail": "Evaluates order volume and revenue generation across sequential calendar months."},
]

# ==============================================================================
# 10. SESSION STATE MANAGEMENT
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

# User Display Profile
logged_in_username = st.session_state.get("username", "admin")
logged_in_name = st.session_state.get("display_name", "Admin User")

# ==============================================================================
# 11. SIDEBAR
# ==============================================================================
with st.sidebar:
    st.markdown(
        f'''
        <div class="logo-container">
            <img src="data:image/svg+xml;base64,{DILYTICS_LOGO_B64}" alt="DILYTICS">
        </div>
        ''',
        unsafe_allow_html=True
    )

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
# 12. MAIN AREA
# ==============================================================================
st.title("💬 Sales AI Copilot")
st.caption("Ask questions in natural language to explore revenue metrics, customer segments, and sales performance.")

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
    st.info("💡 **Pro-Tip:** Type naturally (e.g., *'Who are our top 5 customers by revenue?'*) or click any quick-prompt button above.")

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
            with st.expander("Generated SQL", expanded=False):
                st.code(msg["sql"], language="sql")
        if msg.get("data") is not None and not msg["data"].empty:
            tab_data, tab_chart = st.tabs(["Data 📄", "Chart 📈"])
            with tab_data:
                st.dataframe(msg["data"], use_container_width=True)
            with tab_chart:
                display_chart_tab(msg["data"], key_prefix=f"hist_{current_id}_{idx}")

# Handle Chat Input
user_prompt = st.chat_input("Ask a question about sales, products, reps, or your uploaded document...")
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
        
        explanation, sql_query = generate_sql_from_prompt(user_prompt)
        df = None
        
        if sql_query:
            st.markdown(explanation)
            with st.expander("Generated SQL", expanded=False):
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
                
        elif doc_ctx:
            with st.spinner(f"Searching in `{doc_fname}`..."):
                answer = answer_from_document_context(user_prompt, doc_ctx, doc_fname)
                st.markdown(answer)
                explanation = answer
                
        else:
            fallback_text = (
                "I am specialized strictly as a **Sales Domain Intelligence Copilot** for commercial revenue analytics, "
                "or I can answer questions about documents uploaded in this chat session.\n\n"
                "Please ask a sales/catalog query, use the quick buttons above, or upload a document in the sidebar!"
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
