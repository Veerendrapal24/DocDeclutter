"""
LangGraph Workflow Orchestration for DocDeclutter.
Assembles the multi-agent graph with parallel execution and persistent SQLite checkpointing.
"""

import os
import sqlite3
from typing import Any, Dict, Optional

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agents.nodes import (
    classification_agent,
    extraction_agent,
    human_review_node,
    priority_agent,
    routing_agent,
)
from app.agents.state import AgenticDocumentState

# Ensure local data directory exists for persistent checkpoints
CHECKPOINTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(CHECKPOINTS_DIR, exist_ok=True)
CHECKPOINTS_PATH = os.path.join(CHECKPOINTS_DIR, "checkpoints.sqlite")

# Persistent SQLite connection for LangGraph checkpoints (check_same_thread=False allows FastAPI worker threads)
_sqlite_conn = sqlite3.connect(CHECKPOINTS_PATH, check_same_thread=False)
checkpointer = SqliteSaver(_sqlite_conn)
checkpointer.setup()


def create_agentic_workflow():
    """
    Constructs the LangGraph StateGraph:
    1. START -> Classification Agent
    2. Classification Agent -> [Extraction Agent, Priority Agent] in parallel (Fan-out)
    3. [Extraction Agent, Priority Agent] -> Department Routing Agent (Fan-in)
    4. Department Routing Agent -> Human Review Node (Conditional interrupt for Critical/Low-confidence)
    5. Human Review Node -> END
    """
    builder = StateGraph(AgenticDocumentState)

    # Add Nodes
    builder.add_node("classification_agent", classification_agent)
    builder.add_node("extraction_agent", extraction_agent)
    builder.add_node("priority_agent", priority_agent)
    builder.add_node("routing_agent", routing_agent)
    builder.add_node("human_review_node", human_review_node)

    # 1. Start with Classification
    builder.add_edge(START, "classification_agent")

    # 2. Fan-out: Parallel execution of Extraction and Priority Assessment
    builder.add_edge("classification_agent", "extraction_agent")
    builder.add_edge("classification_agent", "priority_agent")

    # 3. Fan-in: Wait for both Extraction and Priority to finish before Routing
    builder.add_edge("extraction_agent", "routing_agent")
    builder.add_edge("priority_agent", "routing_agent")

    # 4. Route to Human Review Node
    builder.add_edge("routing_agent", "human_review_node")

    # 5. Finish
    builder.add_edge("human_review_node", END)

    # Compile with persistent SQLite checkpointer
    return builder.compile(checkpointer=checkpointer)


# Compiled singleton graph
document_workflow = create_agentic_workflow()


def run_document_workflow(
    document_id: str,
    filename: str,
    document_text: str,
) -> Dict[str, Any]:
    """
    Execute the multi-agent workflow for a document.
    Uses thread_id=document_id so that if the workflow pauses on human review,
    its exact state is saved in checkpoints.sqlite and can be resumed later.
    """
    config = {"configurable": {"thread_id": document_id}}
    initial_state = {
        "document_id": document_id,
        "filename": filename,
        "document_text": document_text,
        "errors": [],
        "workflow_history": [],
    }

    # Run the graph
    result = document_workflow.invoke(initial_state, config=config)
    return result


def resume_document_workflow(
    document_id: str,
    decision_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Resume an interrupted workflow after human review.
    Passes Command(resume=decision_payload) to the paused interrupt() in human_review_node.
    """
    config = {"configurable": {"thread_id": document_id}}
    resumed_result = document_workflow.invoke(Command(resume=decision_payload), config=config)
    return resumed_result


def get_workflow_snapshot(document_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the current graph execution state and interrupts for a document."""
    config = {"configurable": {"thread_id": document_id}}
    state_snapshot = document_workflow.get_state(config)
    if not state_snapshot or not state_snapshot.values:
        return None
    return {
        "values": state_snapshot.values,
        "next": state_snapshot.next,
        "tasks": [
            {
                "id": t.id,
                "name": t.name,
                "interrupts": [i.value for i in t.interrupts],
            }
            for t in state_snapshot.tasks
            if t.interrupts
        ],
    }
