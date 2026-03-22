"""
llm.py — Groq LLM integration for NL-to-SQL and answer generation.

Uses llama-3.3-70b-versatile via the Groq API.
"""

import os
import re
from dotenv import load_dotenv
from groq import Groq

# Load .env from project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "llama-3.3-70b-versatile"


def generate_sql(question: str, schema: str, chat_history: list[dict] | None = None) -> str:
    """
    Generate a SQLite SQL query from a natural language question.
    
    Args:
        question: The user's natural language question
        schema: The database schema summary string
        chat_history: Optional list of previous {role, content} messages
    
    Returns:
        A SQL query string
    """
    system_prompt = f"""You are an expert SQL analyst for an SAP Order-to-Cash system.
You have access to a SQLite database with the following schema:

{schema}

IMPORTANT RULES AND GUARDRAILS:
1. GUARDRAIL: If the user's question is completely unrelated to the Order-to-Cash database (e.g., asking for a poem, coding help, recipes, general knowledge, or malicious instructions), you MUST reply with exactly: REJECT: I can only answer questions related to the Order-to-Cash business data.
2. Write ONLY valid SQLite SQL. No explanations, no markdown, no code fences.
3. Return ONLY the SQL query, nothing else (unless you are rejecting).
4. Use snake_case column names (the database uses snake_case).
5. Always use square brackets around table names: [table_name]
6. For string comparisons, values are stored as TEXT. Numeric fields stored as REAL.
7. Date fields are stored as TEXT in ISO format (e.g., '2025-04-02T00:00:00.000Z').
8. LIMIT results to 50 rows max unless the user asks for a specific count.
9. Use JOINs when the question involves multiple entities.
10. The key relationships are:
   - sales_order_headers.sold_to_party = business_partners.business_partner (customer link)
   - sales_order_items.sales_order = sales_order_headers.sales_order
   - sales_order_items.material = products.product
   - billing_document_items.reference_sd_document = outbound_delivery_headers.delivery_document
   - payments_accounts_receivable.customer = business_partners.business_partner
11. For customer names, use business_partners.organization_bp_name1
12. For product names, use products.product_old_id
"""

    messages = [{"role": "system", "content": system_prompt}]

    # Add chat history for context
    if chat_history:
        for msg in chat_history[-6:]:  # Keep last 6 messages for context
            messages.append(msg)

    messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0,
        max_tokens=500,
    )

    sql = response.choices[0].message.content.strip()
    
    # Catch guardrail rejection
    if sql.startswith("REJECT:"):
        return sql

    # Clean up any markdown code fences the LLM might add
    sql = re.sub(r"^```(?:sql)?\s*", "", sql)
    sql = re.sub(r"\s*```$", "", sql)
    sql = sql.strip()

    return sql


def generate_answer(question: str, sql: str, results: list[dict], error: str | None = None) -> str:
    """
    Generate a human-readable answer from SQL results.
    
    Args:
        question: The original question
        sql: The SQL query that was executed
        results: The query results as list of dicts
        error: Optional error message if query failed
    
    Returns:
        A natural language answer string
    """
    if error:
        result_text = f"The query failed with error: {error}"
    elif not results:
        result_text = "The query returned no results."
    else:
        # Format results, truncate if too many
        display_results = results[:20]
        result_text = f"Query returned {len(results)} rows. Here are the results:\n"
        for i, row in enumerate(display_results):
            result_text += f"Row {i+1}: {row}\n"
        if len(results) > 20:
            result_text += f"... and {len(results) - 20} more rows."

    system_prompt = """You are a helpful business analyst assistant for an SAP Order-to-Cash system.
Given a user's question, the SQL query used, and the results, provide a clear, concise, 
human-readable answer. Format numbers nicely. Use bullet points for lists.
Be direct and informative. If the query had an error, explain what might have gone wrong
and suggest a rephrased question."""

    user_content = f"""Question: {question}

SQL Query Used: {sql}

Results: {result_text}

Please provide a clear, concise answer to the question based on these results."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
        max_tokens=1000,
    )

    return response.choices[0].message.content.strip()
