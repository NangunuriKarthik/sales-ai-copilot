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
    return re.sub(r'[^\w\s]', '', text.lower()).strip()

SEMANTIC_CATALOG = 'MODEL: Sales Intelligence Model\nDESCRIPTION: Semantic model for Sales Intelligence in CORTEX.MART. Use this model to answer business questions about sales, revenue, orders, customers, products, sales representatives, channels, regions, and calendar or fiscal time periods. User wording may be informal or use common business terms; map those terms to the closest semantic field or measure defined below rather than treating wording as an exact-match requirement.\n\nTABLES AND SEMANTIC FIELDS:\n\nTABLE dim_customer -> CORTEX.MART.DIM_CUSTOMER\nDESCRIPTION: Customer master data used to analyze who buys, where customers are located, customer segments, industries, and customer status.\n  customer_id: Unique identifier for a customer. Use for customer-level joins and filtering. | expr=customer_id | synonyms=customer number, customer identifier\n  customer_name: Business name or name of the customer. Use when the user asks about customers, clients, or accounts by name. | expr=customer_name | synonyms=customer, client, account name, client name\n  customer_type: Customer classification or segment, such as enterprise. Use for customer-segment analysis. | expr=customer_type | synonyms=customer segment, account type, client type\n  industry: Industry or business sector associated with the customer. | expr=industry | synonyms=customer industry, industry sector, business sector\n  email: Customer email address. Use only when the user explicitly asks for contact information. | expr=email | synonyms=customer email, contact email\n  phone: Customer phone number. Use only when the user explicitly asks for contact information. | expr=phone | synonyms=customer phone, contact number\n  address_line1: Primary street address for the customer. | expr=address_line1 | synonyms=customer address, street address\n  city: City associated with the customer. | expr=city | synonyms=customer city\n  state: State associated with the customer. | expr=state | synonyms=customer state\n  country: Country associated with the customer. | expr=country | synonyms=customer country\n  postal_code: Postal or ZIP code associated with the customer. | expr=postal_code | synonyms=ZIP code, postal code\n  region: Geographic region associated with the customer. | expr=region | synonyms=customer region, customer territory, geographic customer region\n  status: Current customer or account status, such as Active or inactive. | expr=status | synonyms=customer status, account status\n  signup_date: Date when the customer signed up or registered. | expr=signup_date | synonyms=customer signup date, registration date\n\nTABLE dim_product -> CORTEX.MART.DIM_PRODUCT\nDESCRIPTION: Product master data used to analyze products, SKUs, categories, sub-categories, brands, prices, and product status.\n  product_id: Unique identifier for a product. | expr=product_id | synonyms=product identifier, product number\n  product_name: Name of the product or item sold. | expr=product_name | synonyms=product, item, item name\n  product_sku: Stock keeping unit or product code. | expr=product_sku | synonyms=SKU, stock keeping unit, product code\n  category: Product category or product group. | expr=category | synonyms=product category, product group\n  sub_category: Product sub-category or product sub-group. | expr=sub_category | synonyms=product subcategory, product sub-group\n  brand: Brand associated with the product. | expr=brand | synonyms=product brand, brand name\n  status: Current product or item status. | expr=status | synonyms=product status, item status\n  unit_cost: Cost of one unit of the product. Use for cost analysis, not sales or revenue. | expr=unit_cost | aggregation=avg | synonyms=cost per unit, product cost\n  unit_price: Standard selling price for one unit of the product. Use for product price/list-price questions. | expr=unit_price | aggregation=avg | synonyms=standard selling price, list price, product price\n  created_at: Date when the product record was created. | expr=created_at\n  updated_at: Date when the product record was last updated. | expr=updated_at\n\nTABLE dim_sales_rep -> CORTEX.MART.DIM_SALES_REP\nDESCRIPTION: Sales representative master data used to analyze seller performance, seller regions, managers, and active or inactive representatives.\n  sales_rep_id: Unique identifier for the sales representative. | expr=sales_rep_id | synonyms=sales representative identifier, sales rep number\n  sales_rep_name: Name of the sales representative, salesperson, seller, or account executive. | expr=sales_rep_name | synonyms=sales representative, sales rep, salesperson, seller\n  email: Sales representative email address. | expr=email | synonyms=sales rep email, representative email\n  region: Geographic region assigned to the sales representative. | expr=region | synonyms=sales representative region, rep territory\n  manager_id: Identifier of the manager associated with the sales representative. | expr=manager_id | synonyms=sales rep manager, manager identifier\n  status: Current status of the sales representative. | expr=status | synonyms=sales representative status, rep status\n  hire_date: Date the sales representative was hired. | expr=hire_date | synonyms=sales rep hire date, employment start date\n  created_at: Date when the sales representative record was created. | expr=created_at\n  updated_at: Date when the sales representative record was last updated. | expr=updated_at\n\nTABLE dim_date -> CORTEX.MART.DIM_DATE\nDESCRIPTION: Calendar and fiscal date attributes used to analyze sales and orders by day, week, month, quarter, year, and fiscal period.\n  year: Calendar year used to group or filter sales and orders. | expr=year | synonyms=calendar year, sales year\n  quarter: Calendar quarter used to group or filter sales. | expr=quarter | synonyms=calendar quarter, sales quarter\n  month: Calendar month number used for chronological monthly analysis. | expr=month | synonyms=calendar month, sales month\n  month_name: Calendar month name used for readable monthly reporting. | expr=month_name | synonyms=month name\n  day: Day of the month. | expr=day | synonyms=day of month\n  day_of_week: Name of the weekday. | expr=day_of_week | synonyms=weekday, day name\n  is_weekend: Indicates whether the date is a weekend or weekday. | expr=is_weekend | synonyms=weekend, weekday vs weekend\n  fiscal_year: Fiscal year associated with the date. | expr=fiscal_year | synonyms=financial year, FY\n  fiscal_quarter: Fiscal quarter associated with the date. | expr=fiscal_quarter | synonyms=financial quarter, FQ\n  week_of_year: Calendar week number within the year. | expr=week_of_year | synonyms=week number, calendar week\n  date_key: Calendar date used for time-based sales and order analysis. | expr=date_key | synonyms=calendar date, date\n\nTABLE fact_sales -> CORTEX.MART.FACT_SALES\nDESCRIPTION: Sales order header data where each row represents one sales order. Use this table for order-level sales, revenue, discounts, tax, shipping, status, channel, currency, customer, representative, and order-date analysis.\n  order_id: Unique identifier for a sales order. | expr=order_id | synonyms=sales order number, order identifier\n  customer_id: Identifier of the customer who placed the order. | expr=customer_id | synonyms=order customer identifier\n  sales_rep_id: Identifier of the sales representative associated with the order. | expr=sales_rep_id | synonyms=order sales rep identifier\n  order_status: Current status of the sales order. | expr=order_status | synonyms=sales order status, transaction status\n  order_channel: Channel or source through which the sales order was placed. | expr=order_channel | synonyms=sales channel, channel, order source\n  currency: Currency used for the sales order. | expr=currency | synonyms=order currency, currency code\n  order_count: Count of sales orders. Use when the user asks how many orders, order volume, or number of transactions. | expr=COUNT(order_id) | synonyms=number of orders, order volume, transaction count\n  total_amount: Order-level sales value. Use for total sales, revenue, sales amount, sales dollars, or order value when analyzing sales orders. | expr=total_amount | aggregation=sum | synonyms=sales, revenue, total sales, sales amount, sales value, sales dollars, order value\n  total_discount: Total discount amount applied to sales orders. | expr=total_discount | aggregation=sum | synonyms=discount amount, total discounts, discount value\n  total_tax: Total tax amount associated with sales orders. | expr=total_tax | aggregation=sum | synonyms=sales tax, tax amount\n  shipping_cost: Total shipping or freight cost associated with sales orders. | expr=shipping_cost | aggregation=sum | synonyms=shipping, freight cost, delivery cost\n  order_date: Date when the sales order was placed. Use for sales-period filtering and calendar time analysis. | expr=order_date | synonyms=sales date, transaction date, purchase date\n  created_at: Timestamp when the sales order record was created. | expr=created_at | synonyms=order creation timestamp\n  updated_at: Timestamp when the sales order record was last updated. | expr=updated_at | synonyms=order update timestamp\n\nTABLE fact_sales_item -> CORTEX.MART.FACT_SALES_ITEM\nDESCRIPTION: Sales order line-item data where each row represents one product line within an order. Use this table for product-level sales, units sold, line revenue, selling price, and discounts.\n  order_item_id: Unique identifier for a sales order line item. | expr=order_item_id | synonyms=order line identifier, line item identifier\n  order_id: Identifier of the sales order containing the line item. | expr=order_id | synonyms=line order identifier\n  product_id: Identifier of the product sold on the line item. | expr=product_id | synonyms=line product identifier\n  quantity: Number of product units sold. Use for unit volume or quantity sold questions. | expr=quantity | aggregation=sum | synonyms=units sold, quantity sold, sales volume\n  unit_price: Selling price per unit recorded on a sales order line. | expr=unit_price | aggregation=avg | synonyms=line selling price, realized unit price\n  discount_amount: Discount amount applied to an individual sales order line. | expr=discount_amount | aggregation=sum | synonyms=line discount, line discount amount, discount applied to line\n  line_total: Sales value of a sales order line after applicable discounts. Use for product, category, sub-category, or brand-level sales analysis. | expr=line_total | aggregation=sum | synonyms=line sales, line revenue, product sales, line value\n  created_at: Timestamp when the sales line item record was created. | expr=created_at | synonyms=line item creation timestamp\n\nRELATIONSHIPS:\n{\'name\': \'sales_to_customer\', \'left_table\': \'fact_sales\', \'right_table\': \'dim_customer\', \'relationship_columns\': [{\'left_column\': \'customer_id\', \'right_column\': \'customer_id\'}], \'join_type\': \'left_outer\', \'relationship_type\': \'many_to_one\'}\n{\'name\': \'sales_to_sales_rep\', \'left_table\': \'fact_sales\', \'right_table\': \'dim_sales_rep\', \'relationship_columns\': [{\'left_column\': \'sales_rep_id\', \'right_column\': \'sales_rep_id\'}], \'join_type\': \'left_outer\', \'relationship_type\': \'many_to_one\'}\n{\'name\': \'sales_to_date\', \'left_table\': \'fact_sales\', \'right_table\': \'dim_date\', \'relationship_columns\': [{\'left_column\': \'order_date\', \'right_column\': \'date_key\'}], \'join_type\': \'left_outer\', \'relationship_type\': \'many_to_one\'}\n{\'name\': \'sales_item_to_sales\', \'left_table\': \'fact_sales_item\', \'right_table\': \'fact_sales\', \'relationship_columns\': [{\'left_column\': \'order_id\', \'right_column\': \'order_id\'}], \'join_type\': \'left_outer\', \'relationship_type\': \'many_to_one\'}\n{\'name\': \'sales_item_to_product\', \'left_table\': \'fact_sales_item\', \'right_table\': \'dim_product\', \'relationship_columns\': [{\'left_column\': \'product_id\', \'right_column\': \'product_id\'}], \'join_type\': \'left_outer\', \'relationship_type\': \'many_to_one\'}\n\nCUSTOM INSTRUCTIONS:\nInterpret user questions by business meaning, not by exact wording. Treat verified_queries as validated examples\nof correct SQL patterns, not as an exact-match question list. When a user\'s wording differs from a verified\nquestion, map the user\'s intent to the closest semantic concepts in this model and generate SQL using the defined\ndimensions, measures, relationships, and time dimensions.\n\nNatural-language mapping:\n- "sales", "revenue", "sales amount", "sales value", "sales dollars", "how much did we sell" generally refer to\n  SUM(fact_sales.total_amount) for order-level sales, unless the question is explicitly about products,\n  categories, brands, or line items, in which case use SUM(fact_sales_item.line_total).\n- "orders", "number of orders", "order volume", "transactions" generally refer to COUNT(fact_sales.order_id).\n- "units", "units sold", "quantity sold", "volume sold" refer to SUM(fact_sales_item.quantity).\n- "customers", "clients", "accounts" refer to dim_customer.\n- "products", "items", "merchandise" refer to dim_product.\n- "sales reps", "salespeople", "sellers", "representatives" refer to dim_sales_rep.\n- "channel" or "sales channel" refers to fact_sales.order_channel.\n- "region" should be interpreted from context: customer region means dim_customer.region; sales representative\n  region means dim_sales_rep.region.\n- "year", "quarter", "month", "week", "day", "calendar year" refer to dim_date calendar attributes.\n- "fiscal year" and "fiscal quarter" refer to dim_date.fiscal_year and dim_date.fiscal_quarter.\n- Explicit years such as 2000 or 2025 are filters on dim_date.year unless the user explicitly says fiscal year.\n- "top", "best", "leading", or "highest" normally means ORDER BY the requested measure DESC; if a count is requested,\n  rank by count; if sales/revenue is requested, rank by sales.\n- "lowest", "bottom", "worst", or "least" normally means ORDER BY the requested measure ASC.\n- "compare" means return the requested groups side by side using the same metric and grouping dimension.\n- "average order value" means AVG(fact_sales.total_amount) unless a different level is explicitly requested.\n- When the user asks for multiple dimensions or metrics, include all requested fields and group at the appropriate\n  grain. Do not silently drop a requested filter, grouping dimension, or metric.\n- Apply explicit filters such as year, category, region, channel, status, customer type, or numeric thresholds\n  in WHERE/HAVING as appropriate.\n- Use the existing relationships for joins. Do not invent columns, tables, metrics, categories, or business\n  definitions that are not present in the semantic model.\n- Prefer the semantic model\'s business fields over raw physical-table names.\n- If the request is ambiguous between order-level sales (total_amount) and product-line sales (line_total),\n  choose the grain implied by the question: customer/region/channel/order questions use total_amount; product,\n  category, sub-category, brand, or units questions use line_total/quantity as appropriate.\n- Verified queries are trusted SQL examples. Reuse their logic when the user\'s intent is similar, while adapting\n  filters, years, grouping dimensions, ranking limits, and requested metrics to the user\'s actual wording.\n- Do not require the user\'s wording to match a verified query verbatim.'


def _verified_examples(question: str, limit: int = 8) -> str:
    try:
        examples = retrieve_verified_queries(question, top_k=limit)
    except Exception:
        examples = []
    if not examples:
        return "No closely related verified examples were found."
    return "\n\n".join(
        f"VERIFIED EXAMPLE {i}\nQuestion: {x.get('question','')}\nSQL:\n{clean_generated_sql(x.get('sql',''))}"
        for i,x in enumerate(examples,1)
    )


def _extract_sql(raw: str) -> str:
    raw=str(raw or "").strip()
    raw=re.sub(r"```(?:sql)?","",raw,flags=re.I).replace("```","")
    hit=re.search(r"(?is)\b(?:with|select)\b",raw)
    if hit:
        raw=raw[hit.start():]
    if ";" in raw:
        raw=raw.split(";",1)[0]
    return clean_generated_sql(raw)


def _semantic_sql(question: str, conversation_context: str = "", repair_context: str = "") -> Optional[str]:
    prompt=f"""
You are the primary SQL reasoning engine for a production Snowflake Sales Copilot.

Translate ANY user question that can be answered by this Sales Intelligence
warehouse into one correct Snowflake SELECT/WITH query. Do not require exact
wording from verified questions. Understand paraphrases, synonyms, business
language, implicit intent, filters, dates, aggregations, rankings, HAVING,
joins, comparisons, ratios, percentages and follow-up questions.

FULL SEMANTIC MODEL:
{SEMANTIC_CATALOG}

VERIFIED EXAMPLES:
{_verified_examples(question)}

RECENT CONVERSATION:
{conversation_context[-8000:] if conversation_context else "None"}

{repair_context}

USER QUESTION:
{question}

NON-NEGOTIABLE GRAIN RULES:
- FACT_SALES is order/header grain.
- FACT_SALES.total_amount is order-level sales.
- FACT_SALES_ITEM is product-line grain.
- FACT_SALES_ITEM.line_total is product-line sales.
- Customer, region, channel, order and sales-rep sales normally use FACT_SALES.total_amount.
- Product, category and brand sales normally use FACT_SALES_ITEM.line_total.
- Never sum order-level total_amount after a one-to-many line-item join without restoring order grain.
- DIM_DATE is authoritative for year/month/quarter/date analysis.

SQL RULES:
1. Infer meaning rather than matching keywords.
2. Apply EVERY requested filter, grouping, date condition and ranking.
3. Use the exact fields in the semantic model; never invent columns.
4. Correctly interpret total/sum, average, count, min/max, percentages and ratios.
5. Correctly interpret top/bottom/highest/lowest/best/worst and explicit N.
6. Correctly interpret comparisons and percentage change using NULLIF.
7. Use GROUP BY/HAVING correctly.
8. Use date dimension fields for date analysis.
9. Return ONE executable Snowflake SELECT or WITH statement only.
10. Never generate write or DDL statements.
11. Do not use SELECT * unless explicitly requested.
12. If the request genuinely cannot be answered from the model, return CANNOT_ANSWER_FROM_MODEL.

{repair_context}
"""
    for model_name in ["claude-sonnet-4-5","llama3.3-70b","llama3.1-70b","llama3.1-8b","mistral-7b"]:
        try:
            rows=session.sql(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS sql_out",
                params=[model_name,prompt]
            ).collect()
            if not rows:
                continue
            raw=str(rows[0]["SQL_OUT"])
            if "CANNOT_ANSWER_FROM_MODEL" in raw.upper():
                continue
            sql=_extract_sql(raw)
            if not (sql.lower().startswith("select") or sql.lower().startswith("with")):
                continue
            return sql
        except Exception:
            continue
    return None


def _repair_sql(question: str, sql: str, error_text: str, conversation_context: str = "") -> Optional[str]:
    return _semantic_sql(
        question,
        conversation_context,
        f"""
The previous SQL failed in Snowflake.

PREVIOUS SQL:
{sql}

ACTUAL SNOWFLAKE ERROR:
{error_text[:6000]}

Repair the query while preserving the original business intent. Return only SQL.
"""
    )


def generate_sql_for_database(prompt: str, conversation_context: str = "") -> Tuple[str, Optional[str]]:
    """General warehouse reasoning. No fixed question list is required."""
    norm_p=normalize_text(prompt)
    if norm_p in ["hi","hello","hey","help","who are you","good morning","good evening"]:
        return "Hello! I am your Sales Intelligence Assistant. Ask any question about the enterprise sales warehouse.",None
    if "county" in norm_p:
        return ("⚠️ The Snowflake Data Mart (`CORTEX.MART`) does not contain a `county` dimension. "
                "Customer geographic data is tracked by `city`, `state`, `country`, `postal_code`, and `region`."),None

    # Primary path: full semantic model + natural-language reasoning.
    sql=_semantic_sql(prompt,conversation_context)
    if sql:
        return f"Generated from the Sales Intelligence semantic model for: **{prompt}**",sql

    # Preserve the original generator as a fallback so existing behavior is not lost.
    legacy=_legacy_generate_sql_for_database(prompt)
    if legacy[1]:
        return legacy

    return "I could not generate a safe warehouse query for this question.",None


def _legacy_generate_sql_for_database(prompt: str) -> Tuple[str, Optional[str]]:
    p = prompt.lower().strip()
    norm_p = normalize_text(prompt)

    # 1. Greetings
    if norm_p in ["hi", "hello", "hey", "help", "who are you", "good morning", "good evening"]:
        return "Hello! I am your Sales Intelligence Assistant. Ask any question about enterprise revenue, customers, products, regions, or time trends.", None

    # 2. Guardrail for known missing dimensions
    if "county" in p:
        return "⚠️ The Snowflake Data Mart (`CORTEX.MART`) does not contain a `county` dimension. Customer geographic data is tracked by `city`, `state`, `country`, `postal_code`, and `region`.", None

    # 3. Detect Directionality (Least / Lowest vs Most / Top)
    is_ascending = any(k in p for k in ["least", "lowest", "bottom", "worst", "minimum", "min", "smallest", "fewest"])
    sort_dir = "ASC" if is_ascending else "DESC"
    rank_label = "bottom (least)" if is_ascending else "top"

    # 4. Detect Explicit Limits (e.g., "top 5", "least 3", default 10)
    limit_match = re.search(r'\b(top|least|bottom|first|limit)\s+(\d+)\b', p)
    record_limit = int(limit_match.group(2)) if limit_match else 10

    # 5. Extract Years
    year_match = re.search(r'\b(19\d\d|20\d\d)\b', p)
    target_year = year_match.group(1) if year_match else None

    # 6. Resolve Aggregation Metric
    is_avg = any(k in p for k in ["average", "avg", "mean"])
    is_count = any(k in p for k in ["count", "number of orders", "order volume", "how many orders", "order count"])
    
    if is_avg:
        metric_agg = "ROUND(AVG(s.total_amount), 2)"
        item_agg = "ROUND(AVG(si.line_total), 2)"
        alias = "average_sales"
        metric_label = "average sales"
    elif is_count:
        metric_agg = "COUNT(s.order_id)"
        item_agg = "COUNT(si.order_item_id)"
        alias = "order_count"
        metric_label = "order count"
    else:
        metric_agg = "SUM(s.total_amount)"
        item_agg = "SUM(si.line_total)"
        alias = "total_sales"
        metric_label = "total sales"

    # 7. Semantic Query Generators with Directionality

    # Product-level queries (handles: "which product has least sales?", "top products", etc.)
    if any(k in p for k in ["product", "item", "sku"]) and not any(k in p for k in ["category", "brand"]):
        year_filter = f"JOIN CORTEX.MART.FACT_SALES s ON si.order_id = s.order_id JOIN CORTEX.MART.DIM_DATE d ON s.order_date = d.date_key WHERE d.year = {target_year}" if target_year else ""
        sql = f"""
SELECT 
    p.product_name,
    {item_agg} AS {alias}
FROM CORTEX.MART.FACT_SALES_ITEM si
JOIN CORTEX.MART.DIM_PRODUCT p ON si.product_id = p.product_id
{year_filter}
GROUP BY p.product_name
ORDER BY {alias} {sort_dir}
LIMIT {record_limit}
        """.strip()
        year_desc = f" for year {target_year}" if target_year else ""
        return f"Ranking {rank_label} products by {metric_label}{year_desc}:", sql

    # Category queries (handles: "least sales category", "top categories")
    if any(k in p for k in ["category", "categories", "sub-category", "subcategory"]):
        year_filter = f"JOIN CORTEX.MART.FACT_SALES s ON si.order_id = s.order_id JOIN CORTEX.MART.DIM_DATE d ON s.order_date = d.date_key WHERE d.year = {target_year}" if target_year else ""
        sql = f"""
SELECT 
    p.category,
    {item_agg} AS {alias}
FROM CORTEX.MART.FACT_SALES_ITEM si
JOIN CORTEX.MART.DIM_PRODUCT p ON si.product_id = p.product_id
{year_filter}
GROUP BY p.category
ORDER BY {alias} {sort_dir}
LIMIT {record_limit}
        """.strip()
        year_desc = f" for year {target_year}" if target_year else ""
        return f"Ranking {rank_label} product categories by {metric_label}{year_desc}:", sql

    # Brand queries
    if "brand" in p:
        sql = f"""
SELECT 
    p.brand,
    {item_agg} AS {alias}
FROM CORTEX.MART.FACT_SALES_ITEM si
JOIN CORTEX.MART.DIM_PRODUCT p ON si.product_id = p.product_id
GROUP BY p.brand
ORDER BY {alias} {sort_dir}
LIMIT {record_limit}
        """.strip()
        return f"Ranking {rank_label} brands by {metric_label}:", sql

    # Customer queries
    if "customer" in p and not any(k in p for k in ["region", "industry", "type"]):
        sql = f"""
SELECT 
    c.customer_name,
    {metric_agg} AS {alias}
FROM CORTEX.MART.FACT_SALES s
JOIN CORTEX.MART.DIM_CUSTOMER c ON s.customer_id = c.customer_id
GROUP BY c.customer_name
ORDER BY {alias} {sort_dir}
LIMIT {record_limit}
        """.strip()
        return f"Ranking {rank_label} customers by {metric_label}:", sql

    # Sales Rep queries
    if any(k in p for k in ["rep", "salesperson", "representative"]):
        sql = f"""
SELECT 
    r.sales_rep_name,
    {metric_agg} AS {alias}
FROM CORTEX.MART.FACT_SALES s
JOIN CORTEX.MART.DIM_SALES_REP r ON s.sales_rep_id = r.sales_rep_id
GROUP BY r.sales_rep_name
ORDER BY {alias} {sort_dir}
LIMIT {record_limit}
        """.strip()
        return f"Ranking {rank_label} sales representatives by {metric_label}:", sql

    # Region queries (handles: "region wise total sales", "sales by region")
    if "region" in p:
        year_clause = f"JOIN CORTEX.MART.DIM_DATE d ON s.order_date = d.date_key WHERE d.year = {target_year}" if target_year else ""
        sql = f"""
SELECT 
    c.region,
    {metric_agg} AS {alias}
FROM CORTEX.MART.FACT_SALES s
JOIN CORTEX.MART.DIM_CUSTOMER c ON s.customer_id = c.customer_id
{year_clause}
GROUP BY c.region
ORDER BY {alias} {sort_dir}
        """.strip()
        year_desc = f" for year {target_year}" if target_year else ""
        return f"Sales by customer region{year_desc} (sorted {sort_dir}):", sql

    # Month / Monthly queries
    if any(k in p for k in ["month", "monthly"]):
        year_clause = f"WHERE d.year = {target_year}" if target_year else ""
        sql = f"""
SELECT 
    d.year,
    d.month,
    d.month_name,
    {metric_agg} AS {alias}
FROM CORTEX.MART.FACT_SALES s
JOIN CORTEX.MART.DIM_DATE d ON s.order_date = d.date_key
{year_clause}
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month ASC
        """.strip()
        return f"Monthly {metric_label}:", sql

    # Specific Year Query
    if target_year:
        sql = f"""
SELECT 
    d.year,
    {metric_agg} AS {alias}
FROM CORTEX.MART.FACT_SALES s
JOIN CORTEX.MART.DIM_DATE d ON s.order_date = d.date_key
WHERE d.year = {target_year}
GROUP BY d.year
        """.strip()
        return f"Total sales for year {target_year}:", sql

    # Yearly trend across all calendar years
    if any(k in p for k in ["year wise", "yearly", "annual", "by year"]):
        sql = f"""
SELECT 
    d.year,
    {metric_agg} AS {alias}
FROM CORTEX.MART.FACT_SALES s
JOIN CORTEX.MART.DIM_DATE d ON s.order_date = d.date_key
GROUP BY d.year
ORDER BY d.year ASC
        """.strip()
        return f"Yearly trend across all calendar years:", sql

    # Total / Overall Sales (e.g. "what is the total sales", "overall sales")
    if any(k in p for k in ["total sales", "total revenue", "overall sales", "sales amount", "gross sales"]):
        sql = f"SELECT {metric_agg} AS {alias} FROM CORTEX.MART.FACT_SALES s"
        return f"Calculating overall {metric_label} across all orders:", sql

    # 8. Snowflake Cortex Fallback
    cortex_instruction = (
        f"You are a Snowflake SQL generator for database CORTEX, schema MART.\n"
        f"Tables:\n"
        f"- FACT_SALES s (order_id, customer_id, sales_rep_id, order_status, order_channel, order_date, total_amount)\n"
        f"- FACT_SALES_ITEM si (order_item_id, order_id, product_id, quantity, unit_price, line_total)\n"
        f"- DIM_CUSTOMER c (customer_id, customer_name, customer_type, industry, city, state, country, region)\n"
        f"- DIM_PRODUCT p (product_id, product_name, category, sub_category, brand)\n"
        f"- DIM_SALES_REP r (sales_rep_id, sales_rep_name, region)\n"
        f"- DIM_DATE d (date_key, year, month, month_name, quarter)\n"
        f"Joins:\n"
        f"- s.customer_id = c.customer_id\n"
        f"- s.order_date = d.date_key\n"
        f"- si.order_id = s.order_id\n"
        f"- si.product_id = p.product_id\n"
        f"- s.sales_rep_id = r.sales_rep_id\n"
        f"Return ONLY valid Snowflake SQL without markdown formatting or backticks for: {prompt}"
    )

    for model in ['llama3.1-8b', 'mistral-7b']:
        try:
            res = session.sql(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS sql_out",
                params=[model, cortex_instruction]
            ).collect()
            raw_sql = res[0]["SQL_OUT"].strip()
            clean_sql = re.sub(r"^```(sql)?", "", raw_sql, flags=re.IGNORECASE).strip().rstrip("`").strip()
            if clean_sql.lower().startswith("select") or clean_sql.lower().startswith("with"):
                return f"Generated SQL for: **{prompt}**", clean_sql
        except Exception:
            continue

    return "I could not formulate a query for this question. Please ask about sales revenue, averages, products, customers, or regions.", None

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

def answer_user_question_on_document(question: str, doc_context: str, filename: str, df: Optional[pd.DataFrame] = None) -> str:
    q_lower = question.lower().strip()

    # Priority 1: Direct High-Accuracy Pandas Tabular Analytics
    if df is not None and not df.empty:
        col_map = {col.lower().strip(): col for col in df.columns}
        matched_target_col = None
        for c_lower, c_orig in col_map.items():
            stem = c_lower.rstrip('s')
            if stem in q_lower or (stem.endswith('y') and stem[:-1] + 'ies' in q_lower):
                matched_target_col = c_orig
                break

        is_count_query = any(k in q_lower for k in ["how many", "count", "number of", "total", "distinct", "unique"])
        is_list_query = any(k in q_lower for k in ["list", "what are", "show", "names of", "give me"])

        if matched_target_col and is_count_query:
            valid_entries = df[matched_target_col].dropna()
            valid_entries = valid_entries[valid_entries.astype(str).str.strip().str.lower() != 'none']
            total_rows = len(valid_entries)
            unique_count = valid_entries.nunique()
            unique_vals = list(valid_entries.unique())

            sample_str = ", ".join([f"`{str(v)}`" for v in unique_vals[:8]])
            if len(unique_vals) > 8:
                sample_str += f" and {len(unique_vals) - 8} more..."

            return (
                f"In **`{filename}`**, there are **{unique_count} unique {matched_target_col}s** "
                f"(across **{total_rows}** total populated records).\n\n"
                f"**Entries:** {sample_str}"
            )

        if matched_target_col and is_list_query:
            valid_entries = df[matched_target_col].dropna()
            valid_entries = valid_entries[valid_entries.astype(str).str.strip().str.lower() != 'none']
            unique_vals = list(valid_entries.unique())
            val_bullets = "\n".join([f"• {str(v)}" for v in unique_vals])
            return f"**List of {matched_target_col}s in `{filename}` ({len(unique_vals)} unique):**\n\n{val_bullets}"

        words = [w for w in re.findall(r'\b[a-zA-Z0-9_]+\b', q_lower) if len(w) > 2 and w not in [
            "what", "is", "the", "are", "sales", "for", "total", "average", "avg", 
            "count", "show", "give", "list", "of", "in", "by", "all", "me", "find",
            "county", "state", "city", "district", "value", "how", "many"
        ]]
        
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
                preview = matched_df.dropna(how='all', axis=1).head(15)
                return f"Found **{len(matched_df)}** matching record(s) in **`{filename}`**:\n\n" + preview.to_markdown(index=False)

    # Priority 2: Generative Cortex QA with Document Context
    clean_doc = doc_context[:10000].replace("'", "''")
    clean_q = question.replace("'", "''")
    prompt = f"Answer factually using only this data from {filename}:\n\n{clean_doc}\n\nQuestion: {clean_q}"
    
    for model in ['llama3.1-8b', 'mistral-7b']:
        try:
            res = session.sql(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', '{prompt}') AS answer").collect()
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
                recent_context = "\n".join([m.get('role','') + ': ' + m.get('content','') for m in messages[-8:]])
                explanation, sql_query = generate_sql_for_database(user_prompt, recent_context)
                
                st.markdown(f'<span class="source-badge badge-snowflake">📌 Source: {source_label}</span>', unsafe_allow_html=True)
                if sql_query:
                    st.markdown(explanation)
                    response_text = explanation
                    with st.expander("Generated SQL Query", expanded=False):
                        st.code(sql_query, language="sql")
                    try:
                        last_error = None
                        for attempt in range(3):
                            try:
                                df_result = session.sql(sql_query).to_pandas()
                                last_error = None
                                break
                            except Exception as exec_error:
                                last_error = str(exec_error)
                                if attempt >= 2:
                                    break
                                repaired_sql = _repair_sql(
                                    user_prompt,
                                    sql_query,
                                    last_error,
                                    recent_context
                                )
                                if not repaired_sql:
                                    break
                                sql_query = repaired_sql

                        if last_error:
                            raise RuntimeError(last_error)

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
