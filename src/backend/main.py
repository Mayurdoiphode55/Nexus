"""
main.py — FastAPI application for the Order-to-Cash Graph Query System.

Endpoints:
  POST /api/query   — NL → SQL → execute → answer
  GET  /api/graph   — graph nodes/edges for visualization
  GET  /api/schema  — database schema introspection
"""

import traceback
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import execute_query, get_schema_summary, get_schema_json
from llm import generate_sql, generate_answer
from graph_builder import build_graph

# ─── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Order to Cash Graph Query System",
    description="NL-to-SQL query engine and interactive graph explorer for SAP O2C data",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ───────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    chat_history: list[dict] | None = None


class QueryResponse(BaseModel):
    question: str
    sql: str
    results: list[dict]
    answer: str
    error: str | None = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    """
    Accept a natural language question, generate SQL via LLM,
    execute it, and return a human-readable answer.
    """
    schema = get_schema_summary()
    sql = ""
    results = []
    answer = ""
    error = None

    try:
        # Step 1: Generate SQL from the question
        sql = generate_sql(req.question, schema, req.chat_history)
        
        # Check guardrail rejection
        if sql.startswith("REJECT:"):
            answer = sql.replace("REJECT: ", "")
            return QueryResponse(
                question=req.question,
                sql="",  # No SQL was executed
                results=[],
                answer=answer,
                error=None,
            )

        # Step 2: Execute the SQL
        try:
            results = execute_query(sql)
        except Exception as exec_err:
            error = str(exec_err)
            results = []

        # Step 3: Generate human-readable answer
        answer = generate_answer(req.question, sql, results, error)

    except Exception as e:
        error = str(e)
        answer = f"I encountered an error processing your question: {error}"
        traceback.print_exc()

    return QueryResponse(
        question=req.question,
        sql=sql,
        results=results[:50],  # Cap results sent to frontend
        answer=answer,
        error=error,
    )


@app.get("/api/graph")
async def graph_endpoint(
    customer_id: str | None = Query(None, description="Filter by customer/business_partner ID"),
    order_id: str | None = Query(None, description="Filter by sales order ID"),
):
    """
    Return graph nodes and edges for the interactive visualization.
    Supports optional filtering by customer or order.
    """
    try:
        graph = build_graph(customer_id=customer_id, order_id=order_id)
        return graph
    except Exception as e:
        traceback.print_exc()
        return {"nodes": [], "edges": [], "error": str(e)}


@app.get("/api/schema")
async def schema_endpoint():
    """Return the database schema as structured JSON."""
    try:
        schema = get_schema_json()
        return {"schema": schema}
    except Exception as e:
        traceback.print_exc()
        return {"schema": [], "error": str(e)}


@app.get("/api/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "message": "Order to Cash Graph Query System is running"}
