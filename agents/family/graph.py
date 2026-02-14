"""LangGraph definition for the Family Agent."""

import random
from typing import Callable

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage

from agents.family.state import FamilyState
from agents.family.prompts import (
    SYSTEM_PROMPT,
    RESPOND_PROMPT,
    REFLECT_PROMPT,
)
from core.llm import get_llm


# Predefined family scenarios for variety
FAMILY_SCENARIOS = [
    {"relationship": "grandson", "caller_name": "Tommy", "call_reason": "checking in and saying hi"},
    {"relationship": "granddaughter", "caller_name": "Sarah", "call_reason": "planning a visit next weekend"},
    {"relationship": "daughter", "caller_name": "Linda", "call_reason": "making sure you took your medicine"},
    {"relationship": "son", "caller_name": "Michael", "call_reason": "telling you about the kids' soccer game"},
    {"relationship": "nephew", "caller_name": "David", "call_reason": "wishing you happy birthday"},
    {"relationship": "niece", "caller_name": "Emily", "call_reason": "inviting you to Thanksgiving dinner"},
]


def respond_node(state: FamilyState) -> dict:
    """Generate the family member's spoken response."""
    llm = get_llm()
    
    conversation_history = "\n".join(state["conversation_memory"][-10:])
    
    system = SYSTEM_PROMPT.format(
        relationship=state["relationship"],
        caller_name=state["caller_name"],
        call_reason=state["call_reason"],
    )
    
    prompt = RESPOND_PROMPT.format(
        relationship=state["relationship"],
        caller_name=state["caller_name"],
        call_reason=state["call_reason"],
        recognized=state["recognized"],
        conversation_history=conversation_history or "(call just started)",
        senior_message=state["senior_message"] or "(no message yet - you're starting the call)",
    )
    
    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ])
    
    family_response = response.content.strip()
    
    # Update conversation memory
    new_memory = state["conversation_memory"].copy()
    if state["senior_message"]:
        new_memory.append(f"Senior: {state['senior_message']}")
    new_memory.append(f"Family: {family_response}")
    
    return {
        "last_response": family_response,
        "conversation_memory": new_memory,
    }


def reflect_node(state: FamilyState) -> dict:
    """Reflect on whether the senior has recognized the caller."""
    llm = get_llm()
    
    system = SYSTEM_PROMPT.format(
        relationship=state["relationship"],
        caller_name=state["caller_name"],
        call_reason=state["call_reason"],
    )
    
    prompt = REFLECT_PROMPT.format(
        family_response=state["last_response"],
        senior_message=state["senior_message"] or "(call just started)",
        recognized=state["recognized"],
    )
    
    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ])
    
    content = response.content
    
    # Parse the response
    recognized = state["recognized"]
    handed_off = state["handed_off"]
    
    if "RECOGNIZED: true" in content.lower():
        recognized = True
    
    if "HANDOFF_READY: true" in content.lower():
        handed_off = True
    
    return {
        "recognized": recognized,
        "handed_off": handed_off,
        "turn": state["turn"] + 1,
    }


def create_family_agent() -> Callable[[FamilyState], FamilyState]:
    """
    Create and compile the Family Agent graph.
    
    Returns:
        A compiled graph that can be invoked with FamilyState.
    """
    graph = StateGraph(FamilyState)
    
    # Add nodes (simpler than scammer - just respond and reflect)
    graph.add_node("respond", respond_node)
    graph.add_node("reflect", reflect_node)
    
    # Define flow: respond → reflect → END
    graph.add_edge(START, "respond")
    graph.add_edge("respond", "reflect")
    graph.add_edge("reflect", END)
    
    return graph.compile()


def get_initial_family_state(scenario: dict = None) -> FamilyState:
    """
    Get the initial state for a new Family Agent.
    
    Args:
        scenario: Optional dict with relationship, caller_name, call_reason.
                  If not provided, a random scenario is chosen.
    """
    if scenario is None:
        scenario = random.choice(FAMILY_SCENARIOS)
    
    return FamilyState(
        turn=0,
        conversation_memory=[],
        relationship=scenario.get("relationship", "grandson"),
        caller_name=scenario.get("caller_name", "Tommy"),
        call_reason=scenario.get("call_reason", "checking in"),
        recognized=False,
        handed_off=False,
        senior_message="",
        last_response="",
    )
