import difflib
import os
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
import yaml
from snowflake.snowpark import Session

try:
    import pypdf
except ImportError:
    pypdf = None

# =============================================================================
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
# 5. DYNAMIC NATURAL LANGUAGE SEMANTIC DATA MART ENGINE
# ==============================================================================
def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", str(text).lower()).strip()


# ------------------------------------------------------------------------------
# Semantic model loader / retrieval
# ------------------------------------------------------------------------------
# Known-safe physical mappings. The YAML remains the semantic source of truth,
# but these mappings prevent basic warehouse questions from failing if the
# YAML file is not found in the Streamlit deployment directory.
PHYSICAL_TABLE_FALLBACK = {
    "dim_customer": "CORTEX.MART.DIM_CUSTOMER",
    "dim_product": "CORTEX.MART.DIM_PRODUCT",
    "dim_sales_rep": "CORTEX.MART.DIM_SALES_REP",
    "dim_date": "CORTEX.MART.DIM_DATE",
    "fact_sales": "CORTEX.MART.FACT_SALES",
    "fact_sales_item": "CORTEX.MART.FACT_SALES_ITEM",
}

_yaml_candidates = [
    os.getenv("SEMANTIC_MODEL_PATH", ""),
    os.path.join(os.path.dirname(__file__), "sales_intelligence_model_enhanced.yaml"),
    os.path.join(os.getcwd(), "sales_intelligence_model_enhanced.yaml"),
]
SEMANTIC_MODEL_PATH = next((p for p in _yaml_candidates if p and os.path.exists(p)), _yaml_candidates[1])

@st.cache_data(show_spinner=False)
def load_semantic_model(path: str) -> Dict[str, Any]:
    """Load the YAML once and build a compact semantic catalog."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            model = yaml.safe_load(fh) or {}
    except Exception:
        model = {"name": "Sales Intelligence Model", "tables": [], "verified_queries": []}

    catalog = {
        "name": model.get("name", "Sales Intelligence Model"),
        "description": model.get("description", ""),
        "tables": [],
        "verified_queries": []
    }

    for table in model.get("tables", []) or []:
        t = {
            "name": table.get("name"),
            "description": table.get("description", ""),
            "base_table": table.get("base_table", {}),
            "dimensions": [],
            "measures": [],
            "time_dimensions": []
        }
        for group in ("dimensions", "measures", "time_dimensions"):
            for field in table.get(group, []) or []:
                t[group].append({
                    "name": field.get("name"),
                    "description": field.get("description", ""),
                    "synonyms": field.get("synonyms", []) or [],
                    "expr": field.get("expr"),
                    "data_type": field.get("data_type"),
                    "default_aggregation": field.get("default_aggregation")
                })
        catalog["tables"].append(t)

    for q in model.get("verified_queries", []) or []:
        if q.get("question") and q.get("sql"):
            catalog["verified_queries"].append({
                "name": q.get("name", ""),
                "question": q["question"],
                "sql": q["sql"]
            })
    return catalog


SEMANTIC_MODEL = load_semantic_model(SEMANTIC_MODEL_PATH)


def _semantic_text_for_table(table: Dict[str, Any]) -> str:
    parts = [table.get("name", ""), table.get("description", "")]
    for group in ("dimensions", "measures", "time_dimensions"):
        for f in table.get(group, []):
            parts.extend([f.get("name", ""), f.get("description", "")])
            parts.extend(f.get("synonyms", []) or [])
    return normalize_text(" ".join(parts))


def retrieve_verified_queries(question: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Retrieve close verified examples without requiring exact wording."""
    q = normalize_text(question)
    if not q:
        return []
    scored = []
    for item in SEMANTIC_MODEL.get("verified_queries", []):
        candidate = normalize_text(item["question"])
        seq = difflib.SequenceMatcher(None, q, candidate).ratio()
        q_tokens, c_tokens = set(q.split()), set(candidate.split())
        overlap = len(q_tokens & c_tokens) / max(1, len(q_tokens | c_tokens))
        score = 0.65 * seq + 0.35 * overlap
        scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored[:top_k] if score > 0.10]


def build_semantic_prompt() -> str:
    """Create a compact model-grounded catalog for Cortex rather than a hand-coded schema."""
    lines = [
        f"SEMANTIC MODEL: {SEMANTIC_MODEL.get('name')}",
        SEMANTIC_MODEL.get("description", ""),
        "TABLES AND BUSINESS MEANINGS:"
    ]
    for t in SEMANTIC_MODEL.get("tables", []):
        bt = t.get("base_table", {})
        physical = ".".join([x for x in [bt.get("database"), bt.get("schema"), bt.get("table")] if x])
        lines.append(f"- {t['name']} -> {physical}: {t.get('description','')}")
        for group in ("dimensions", "measures", "time_dimensions"):
            for f in t.get(group, []):
                syn = ", ".join(f.get("synonyms", []) or [])
                extra = f"; synonyms={syn}" if syn else ""
                agg = f"; default_aggregation={f.get('default_aggregation')}" if f.get("default_aggregation") else ""
                lines.append(f"  * {group[:-1]} {f['name']}: {f.get('description','')}{extra}{agg}")
    lines.extend([
        "IMPORTANT GRAIN RULES:",
        "- FACT_SALES is order/header grain. Use SUM(total_amount) for order-level sales, customer, region, channel, order and sales-rep metrics.",
        "- FACT_SALES_ITEM is line-item grain. Use SUM(line_total) for product, category, sub-category, brand, quantity and product-level metrics.",
        "- Never SUM FACT_SALES.total_amount after joining to FACT_SALES_ITEM unless the query first restores order grain; otherwise orders can be duplicated.",
        "- Use DIM_DATE for year, month, quarter and date-related grouping/filtering.",
        "- Use DIM_CUSTOMER for customer geography such as city, state, country, postal_code and region.",
        "- If the model does not contain a requested field, do not invent it. Explain that it is unavailable.",
        "- Return read-only SELECT/WITH SQL only. Never INSERT, UPDATE, DELETE, MERGE, DROP, ALTER, CREATE or TRUNCATE."
    ])
    return "\n".join(lines)


SEMANTIC_PROMPT = build_semantic_prompt()


def clean_generated_sql(raw_sql: str) -> str:
    sql = str(raw_sql or "").strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql).strip().rstrip(";").strip()
    # Remove common assistant prefixes while preserving SQL.
    sql = re.sub(r"^(?:SQL\s*:\s*)", "", sql, flags=re.IGNORECASE).strip()
    return sql


def validate_read_only_sql(sql: str) -> Tuple[bool, str]:
    """Basic safety/quality gate before SQL reaches Snowflake."""
    if not sql:
        return False, "Empty SQL was generated."
    normalized = re.sub(r"\s+", " ", sql.strip()).lower()
    if not re.match(r"^(select|with)\b", normalized):
        return False, "Only SELECT/WITH queries are allowed."
    forbidden = r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|call|copy|put|remove)\b"
    if re.search(forbidden, normalized):
        return False, "The generated SQL contains a non-read-only operation."
    # Allow the known warehouse tables even if YAML is temporarily unavailable.
    allowed_tables = {v.lower() for v in PHYSICAL_TABLE_FALLBACK.values()}
    for t in SEMANTIC_MODEL.get("tables", []):
        bt = t.get("base_table", {})
        if bt.get("database") and bt.get("schema") and bt.get("table"):
            allowed_tables.add(f"{bt['database']}.{bt['schema']}.{bt['table']}".lower())
    # Detect three-part physical references. CTE names are intentionally ignored.
    for db, schema, table in re.findall(r"\b([A-Za-z_][\w$]*)\.([A-Za-z_][\w$]*)\.([A-Za-z_][\w$]*)\b", sql):
        if f"{db}.{schema}.{table}".lower() not in allowed_tables:
            return False, f"SQL references a table outside the semantic model: {db}.{schema}.{table}"
    return True, ""


def _physical_table(name: str) -> str:
    """Resolve a semantic table using YAML first, then the safe fallback map."""
    key = normalize_text(name).replace(" ", "_")
    for t in SEMANTIC_MODEL.get("tables", []):
        if normalize_text(t.get("name", "")).replace(" ", "_") == key:
            bt = t.get("base_table", {})
            parts = [bt.get("database"), bt.get("schema"), bt.get("table")]
            physical = ".".join(str(x) for x in parts if x)
            if physical:
                return physical
    return PHYSICAL_TABLE_FALLBACK.get(key, name)


def _extract_year_from_question(question: str) -> Optional[int]:
    match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2})\b", question or "")
    return int(match.group(1)) if match else None


def _hard_reliable_sql(question: str) -> Optional[Tuple[str, str]]:
    """Reliable SQL for common intents; intentionally independent of Cortex."""
    q = normalize_text(question)
    fs = PHYSICAL_TABLE_FALLBACK["fact_sales"]
    fsi = PHYSICAL_TABLE_FALLBACK["fact_sales_item"]
    dc = PHYSICAL_TABLE_FALLBACK["dim_customer"]
    dp = PHYSICAL_TABLE_FALLBACK["dim_product"]
    dr = PHYSICAL_TABLE_FALLBACK["dim_sales_rep"]
    dd = PHYSICAL_TABLE_FALLBACK["dim_date"]
    year = _extract_year_from_question(question)

    sales = any(x in q for x in [
        "sales", "revenue", "sales amount", "sales value", "turnover",
        "selling amount", "sales revenue"
    ])
    total = any(x in q for x in [
        "total", "overall", "sum", "how much", "amount", "value"
    ])

    # 1. Total sales / revenue / sales amount.
    grouped = any(x in q for x in [
        "by customer", "by client", "by account", "by product", "by item",
        "by region", "by channel", "by month", "by year", "by category",
        "by brand", "by sales rep", "by representative"
    ])
    if sales and total and not grouped:
        join = f"\nJOIN {dd} ON {fs}.order_date = {dd}.date_key" if year else ""
        where = f"\nWHERE {dd}.year = {year}" if year else ""
        return (
            "Total sales amount (order-level grain).",
            f"SELECT ROUND(SUM({fs}.total_amount), 2) AS total_sales\nFROM {fs}{join}{where}"
        )

    # 2. Total sales by customer.
    if sales and any(x in q for x in ["by customer", "by client", "by account"]):
        join_date = f"\nJOIN {dd} ON {fs}.order_date = {dd}.date_key" if year else ""
        where = f"\nWHERE {dd}.year = {year}" if year else ""
        direction = "ASC" if any(x in q for x in ["lowest", "least", "bottom", "worst", "smallest"]) else "DESC"
        lm = re.search(r"\b(?:top|bottom)\s+(\d+)\b", q)
        limit = f"\nLIMIT {int(lm.group(1))}" if lm else ""
        return (
            "Sales by customer (order-level grain).",
            f"SELECT {dc}.customer_name, ROUND(SUM({fs}.total_amount), 2) AS total_sales\n"
            f"FROM {fs}\nJOIN {dc} ON {fs}.customer_id = {dc}.customer_id"
            f"{join_date}{where}\nGROUP BY {dc}.customer_name\n"
            f"ORDER BY total_sales {direction}{limit}"
        )

    # 3. Sales by region.
    if sales and "by region" in q:
        join_date = f"\nJOIN {dd} ON {fs}.order_date = {dd}.date_key" if year else ""
        where = f"\nWHERE {dd}.year = {year}" if year else ""
        return (
            "Sales by customer region.",
            f"SELECT {dc}.region, ROUND(SUM({fs}.total_amount), 2) AS total_sales\n"
            f"FROM {fs}\nJOIN {dc} ON {fs}.customer_id = {dc}.customer_id"
            f"{join_date}{where}\nGROUP BY {dc}.region\nORDER BY total_sales DESC"
        )

    # 4. Product/category/brand sales use line-item grain.
    if sales and "by product" in q:
        return (
            "Sales by product (line-item grain).",
            f"SELECT {dp}.product_name, ROUND(SUM({fsi}.line_total), 2) AS total_sales\n"
            f"FROM {fsi}\nJOIN {dp} ON {fsi}.product_id = {dp}.product_id\n"
            f"GROUP BY {dp}.product_name\nORDER BY total_sales DESC"
        )
    if sales and "by category" in q:
        return (
            "Sales by category (line-item grain).",
            f"SELECT {dp}.category, ROUND(SUM({fsi}.line_total), 2) AS total_sales\n"
            f"FROM {fsi}\nJOIN {dp} ON {fsi}.product_id = {dp}.product_id\n"
            f"GROUP BY {dp}.category\nORDER BY total_sales DESC"
        )
    if sales and "by brand" in q:
        return (
            "Sales by brand (line-item grain).",
            f"SELECT {dp}.brand, ROUND(SUM({fsi}.line_total), 2) AS total_sales\n"
            f"FROM {fsi}\nJOIN {dp} ON {fsi}.product_id = {dp}.product_id\n"
            f"GROUP BY {dp}.brand\nORDER BY total_sales DESC"
        )

    # 5. Orders.
    if any(x in q for x in ["how many orders", "number of orders", "order count", "count of orders"]):
        join = f"\nJOIN {dd} ON {fs}.order_date = {dd}.date_key" if year else ""
        where = f"\nWHERE {dd}.year = {year}" if year else ""
        return ("Order count.", f"SELECT COUNT({fs}.order_id) AS order_count\nFROM {fs}{join}{where}")

    # 6. Average order value.
    if any(x in q for x in ["average order value", "avg order value", "average order amount", "mean order value"]):
        join = f"\nJOIN {dd} ON {fs}.order_date = {dd}.date_key" if year else ""
        where = f"\nWHERE {dd}.year = {year}" if year else ""
        return ("Average order value.", f"SELECT ROUND(AVG({fs}.total_amount), 2) AS average_order_value\nFROM {fs}{join}{where}")

    # 7. Sales by channel / sales rep.
    if sales and "by channel" in q:
        return (
            "Sales by order channel.",
            f"SELECT {fs}.order_channel, ROUND(SUM({fs}.total_amount), 2) AS total_sales\n"
            f"FROM {fs}\nGROUP BY {fs}.order_channel\nORDER BY total_sales DESC"
        )
    if sales and any(x in q for x in ["by sales rep", "by sales representative", "by representative"]):
        return (
            "Sales by sales representative.",
            f"SELECT {dr}.sales_rep_name, ROUND(SUM({fs}.total_amount), 2) AS total_sales\n"
            f"FROM {fs}\nJOIN {dr} ON {fs}.sales_rep_id = {dr}.sales_rep_id\n"
            f"GROUP BY {dr}.sales_rep_name\nORDER BY total_sales DESC"
        )

    return None


def generate_sql_for_database(prompt: str, conversation_context: str = "") -> Tuple[str, Optional[str]]:
    """Semantic-model-grounded SQL generation.

    Deterministic keyword branches are intentionally removed. The YAML model,
    retrieved verified examples and conversation context are supplied to Cortex.
    """
    norm_p = normalize_text(prompt)

    # IMPORTANT: restore the reliable behavior for common questions before
    # invoking Cortex. The previous revision removed this layer, which caused
    # even canonical questions such as "What is the total sales amount?" to
    # fall through to the generic semantic/LLM path.
    reliable = _hard_reliable_sql(prompt)
    if reliable:
        ok, _ = validate_read_only_sql(reliable[1])
        if ok:
            return reliable

    if norm_p in {"hi", "hello", "hey", "help", "who are you", "good morning", "good evening"}:
        return "Hello! I am your Sales Intelligence Assistant. Ask me about sales, customers, products, regions, representatives, channels, or time trends.", None

    # Surface known unavailable dimensions explicitly rather than hallucinating them.
    requested_fields = [f["name"] for t in SEMANTIC_MODEL.get("tables", []) for g in ("dimensions", "measures", "time_dimensions") for f in t.get(g, [])]
    if "county" in norm_p and "county" not in [normalize_text(x) for x in requested_fields]:
        return "⚠️ The semantic model does not contain a county dimension. Available customer geography includes city, state, country, postal code and region.", None

    examples = retrieve_verified_queries(prompt, top_k=5)
    examples_text = "\n\n".join(
        f"VERIFIED EXAMPLE {i+1}: {e['question']}\nSQL:\n{e['sql']}"
        for i, e in enumerate(examples)
    ) or "No closely matching verified example was found."

    prompt_text = f"""You are the SQL reasoning layer for a Snowflake Sales Intelligence application.
Use the semantic model below as the source of truth. Interpret the user's business intent, not exact keywords.
Paraphrases such as 'how much did we make', 'revenue', 'sales amount', 'best performing', 'worst performing', 'by month',
'for 2000', 'during 2025', 'how many orders', 'which customer bought the most', etc. should map to the appropriate semantic concepts.

{SEMANTIC_PROMPT}

RETRIEVED VERIFIED EXAMPLES:
{examples_text}

RECENT CONVERSATION CONTEXT:
{conversation_context[-5000:] if conversation_context else 'None'}

USER QUESTION:
{prompt}

Rules:
1. Produce ONLY executable Snowflake SQL, with no markdown or explanation.
2. Use physical tables/columns from the semantic model's base_table and expr definitions.
3. Preserve the correct grain: order-level metrics use FACT_SALES; product-level metrics use FACT_SALES_ITEM.
4. Apply all explicit filters (year, month, customer, product, category, region, channel, status, etc.).
5. For rankings, honor top/bottom/least/most and explicit N; do not invent N when the user gives one.
6. For aggregations, distinguish SUM, AVG, COUNT, MIN and MAX according to intent.
7. For year/month/quarter questions use DIM_DATE rather than guessing date functions from raw dates.
8. If the request is not answerable from the model, return exactly: CANNOT_ANSWER_FROM_MODEL
"""

    for model in ["llama3.1-8b", "mistral-7b"]:
        try:
            res = session.sql(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS sql_out",
                params=[model, prompt_text]
            ).collect()
            raw = res[0]["SQL_OUT"]
            if str(raw).strip() == "CANNOT_ANSWER_FROM_MODEL":
                return "I could not answer that from the current Sales semantic model. Please try a question about sales, customers, products, representatives, regions, channels, or dates.", None
            sql = clean_generated_sql(raw)
            ok, reason = validate_read_only_sql(sql)
            if ok:
                return f"Interpreting your question using the Sales semantic model: **{prompt}**", sql
        except Exception:
            continue

    # Final fallback: reuse the closest verified query only when the similarity
    # is strong enough. This preserves the original application's useful
    # behavior instead of returning a dead end after a Cortex failure.
    matches = retrieve_verified_queries(prompt, top_k=3)
    if matches:
        qn = normalize_text(prompt)
        scored = []
        for item in matches:
            cn = normalize_text(item["question"])
            seq = difflib.SequenceMatcher(None, qn, cn).ratio()
            qt, ct = set(qn.split()), set(cn.split())
            overlap = len(qt & ct) / max(1, len(qt | ct))
            scored.append((0.60 * seq + 0.40 * overlap, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored and scored[0][0] >= 0.52:
            raw_verified = scored[0][1]["sql"]
            # Convert logical __table placeholders used by the YAML examples.
            for key, physical in PHYSICAL_TABLE_FALLBACK.items():
                raw_verified = re.sub(rf"\\b__{re.escape(key)}\\b", physical, raw_verified, flags=re.IGNORECASE)
            raw_verified = clean_generated_sql(raw_verified)
            ok, _ = validate_read_only_sql(raw_verified)
            if ok:
                return (
                    f"Using the closest verified semantic pattern for: **{prompt}**",
                    raw_verified,
                )

    return "I could not formulate a safe query for this question from the current semantic model. Please try a sales, revenue, order, customer, product, region, channel, representative, or date question.", None

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

def _normalized_column_map(df: pd.DataFrame) -> Dict[str, str]:
    mapping = {}
    for col in df.columns:
        n = normalize_text(str(col)).replace(" ", "_")
        mapping[n] = col
        mapping[n.replace("_", "")] = col
    return mapping


def _find_semantic_column(question: str, columns: List[str]) -> Optional[str]:
    """Map natural-language column references to the real dataframe column."""
    q = normalize_text(question)
    best = (0.0, None)
    for col in columns:
        c = normalize_text(str(col))
        score = difflib.SequenceMatcher(None, q, c).ratio()
        tokens = set(q.split()) & set(c.split())
        if tokens:
            score += min(0.30, 0.10 * len(tokens))
        if c and c in q:
            score += 0.45
        if score > best[0]:
            best = (score, col)
    return best[1] if best[0] >= 0.55 else None


def _document_dataframe_answer(question: str, df: pd.DataFrame, filename: str) -> Optional[str]:
    """Answer common spreadsheet questions deterministically on the full dataframe."""
    if df is None or df.empty:
        return None
    q = normalize_text(question)
    cols = list(df.columns)
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if not numeric_cols:
        return None

    # Find a metric column using column semantics, not a 150-row preview.
    metric_candidates = []
    for col in numeric_cols:
        c = normalize_text(str(col))
        score = 0
        if any(k in c for k in ["sales", "sale", "revenue", "amount", "total", "value", "price"]):
            score += 0.5
        if any(k in q for k in ["sales", "revenue", "amount", "total", "value", "price"]):
            score += 0.2
        score += difflib.SequenceMatcher(None, q, c).ratio() * 0.3
        metric_candidates.append((score, col))
    metric_col = sorted(metric_candidates, reverse=True)[0][1]

    is_avg = any(k in q.split() for k in ["average", "avg", "mean"])
    is_count = any(k in q for k in ["count", "how many", "number of records", "number of rows"])
    is_min = any(k in q for k in ["minimum", "min", "lowest", "least", "smallest"])
    is_max = any(k in q for k in ["maximum", "max", "highest", "most", "largest", "best"])

    # Try explicit year filtering against a year/date column.
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", q)
    working = df.copy()
    if year_match:
        year = int(year_match.group(1))
        year_cols = [c for c in cols if "year" in normalize_text(str(c))]
        date_cols = [c for c in cols if "date" in normalize_text(str(c))]
        if year_cols:
            vals = pd.to_numeric(working[year_cols[0]], errors="coerce")
            working = working[vals == year]
        elif date_cols:
            dates = pd.to_datetime(working[date_cols[0]], errors="coerce")
            working = working[dates.dt.year == year]

    if working.empty:
        return f"In **`{filename}`**, no records matched the requested filter."

    if is_count:
        return f"In **`{filename}`**, the matching record count is **{len(working):,}**."
    if is_avg:
        val = pd.to_numeric(working[metric_col], errors="coerce").mean()
        return f"In **`{filename}`**, the average **{metric_col}** is **{val:,.2f}**."
    if is_min:
        val = pd.to_numeric(working[metric_col], errors="coerce").min()
        return f"In **`{filename}`**, the minimum **{metric_col}** is **{val:,.2f}**."
    if is_max:
        val = pd.to_numeric(working[metric_col], errors="coerce").max()
        return f"In **`{filename}`**, the maximum **{metric_col}** is **{val:,.2f}**."

    # Group-by questions such as "sales by region/category/month".
    group_terms = ["region", "category", "subcategory", "sub category", "brand", "customer", "product", "state", "city", "month", "year", "quarter"]
    for term in group_terms:
        if term in q:
            candidates = [c for c in cols if term.replace(" ", "") in normalize_text(str(c)).replace(" ", "")]
            if candidates:
                gcol = candidates[0]
                temp = working.copy()
                temp[metric_col] = pd.to_numeric(temp[metric_col], errors="coerce")
                result = temp.groupby(gcol, dropna=False)[metric_col].sum().reset_index().sort_values(metric_col, ascending=False)
                result = result.head(10)
                return f"Here are the top results by **{gcol}** from `{filename}`:\n\n" + result.to_markdown(index=False)

    total = pd.to_numeric(working[metric_col], errors="coerce").sum()
    return f"In **`{filename}`**, the total **{metric_col}** for the matching records is **{total:,.2f}**."


def answer_user_question_on_document(question: str, doc_context: str, filename: str, df: Optional[pd.DataFrame] = None) -> str:
    """Hybrid document QA: deterministic full-data spreadsheet answers + retrieved text QA."""
    if df is not None:
        deterministic = _document_dataframe_answer(question, df, filename)
        if deterministic:
            return deterministic

    # Keep the most relevant text instead of blindly truncating at 10k chars.
    text = str(doc_context or "")
    if not text:
        return f"The uploaded document (`{filename}`) contains no readable text."

    q_terms = [t for t in re.findall(r"[a-zA-Z0-9]+", question.lower()) if len(t) > 2]
    paragraphs = re.split(r"\n\s*\n|(?<=\.)\s+(?=[A-Z])", text)
    scored = []
    qset = set(q_terms)
    for para in paragraphs:
        pset = set(re.findall(r"[a-zA-Z0-9]+", para.lower()))
        overlap = len(qset & pset)
        if overlap:
            scored.append((overlap / max(1, len(qset)), para))
    scored.sort(key=lambda x: x[0], reverse=True)
    chunks = [p for _, p in scored[:8]]
    if not chunks:
        chunks = paragraphs[:6]
    context = "\n\n".join(chunks)[:16000]

    prompt = f"""Answer the user's question using ONLY the supplied document excerpts.
If the excerpts do not contain the answer, say that the document does not contain enough information.
Do not invent facts, calculations, names, dates or values.

DOCUMENT: {filename}
EXCERPTS:
{context}

QUESTION: {question}"""
    for model in ["llama3.1-8b", "mistral-7b"]:
        try:
            res = session.sql(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS answer",
                params=[model, prompt]
            ).collect()
            ans = str(res[0]["ANSWER"] or "").strip()
            if ans:
                return ans
        except Exception:
            continue
    return f"The uploaded document (`{filename}`) does not contain enough information to answer this query."

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
        context_str = f"File: {filename}\nTotal Rows: {len(clean_df)}\nColumns: {', '.join(map(str, clean_df.columns))}\n\nSAMPLE RECORDS:\n"
        context_str += clean_df.head(50).to_string(index=False)
        
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

if "selected_source_mode" not in st.session_state:
    st.session_state.selected_source_mode = "❄️ Snowflake Data Mart"

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
        st.session_state.selected_source_mode = "❄️ Snowflake Data Mart"
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
                    st.session_state.selected_source_mode = f"📄 Document: {uploaded_doc.name[:18]}..."
                    
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
            st.session_state.selected_source_mode = "❄️ Snowflake Data Mart"
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
            st.session_state.selected_source_mode = "❄️ Snowflake Data Mart"
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

# Interactive Source Toggle with Session Persistence
has_active_doc = active_session_data.get("doc_name") is not None
active_file_name = active_session_data.get("doc_name", "")
doc_choice_label = f"📄 Document: {active_file_name[:20]}..." if has_active_doc else "📄 Document (Upload in sidebar)"

available_modes = ["❄️ Snowflake Data Mart", doc_choice_label]

if st.session_state.selected_source_mode not in available_modes:
    st.session_state.selected_source_mode = available_modes[0]

mode_col, _ = st.columns([3.5, 2.5])
with mode_col:
    def on_source_change():
        st.session_state.selected_source_mode = st.session_state.source_mode_radio

    query_target = st.radio(
        "Select target data source",
        options=available_modes,
        index=available_modes.index(st.session_state.selected_source_mode),
        horizontal=True,
        label_visibility="collapsed",
        key="source_mode_radio",
        on_change=on_source_change
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

        # Branch 1: User explicitly routed to Document
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
                recent_context = "\n".join([f"{m.get('role','')}: {m.get('content','')}" for m in messages[-8:]])
                explanation, sql_query = generate_sql_for_database(user_prompt, recent_context)
                
                st.markdown(f'<span class="source-badge badge-snowflake">📌 Source: {source_label}</span>', unsafe_allow_html=True)
                if sql_query:
                    st.markdown(explanation)
                    response_text = explanation
                    with st.expander("Generated SQL Query", expanded=False):
                        st.code(sql_query, language="sql")
                    try:
                        is_safe, validation_error = validate_read_only_sql(sql_query)
                        if not is_safe:
                            st.error(f"SQL validation blocked this query: {validation_error}")
                            response_text = "The generated query was blocked by the SQL safety validator."
                        else:
                            df_result = session.sql(sql_query).to_pandas()
                            if df_result is not None and not df_result.empty:
                                first_val = df_result.iloc[0, -1] if len(df_result.columns) > 0 else None
                                if pd.isnull(first_val) or (isinstance(first_val, (int, float)) and first_val == 0 and len(df_result) == 1):
                                    st.info("The query executed, but no matching records were found in the Snowflake Data Mart.")
                                else:
                                    tab_data, tab_chart = st.tabs(["Data Table 📄", "Visualization 📈"])
                                    with tab_data:
                                        st.dataframe(df_result, use_container_width=True)
                                    with tab_chart:
                                        display_chart_tab(df_result, key_prefix=f"live_{current_id}")
                            else:
                                st.info("No matching records were found in the Snowflake Data Mart.")
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
