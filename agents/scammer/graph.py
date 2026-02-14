"""LangGraph definition for the Scammer agent."""

import re
from typing import Callable

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage

from agents.scammer.state import ScammerState, PersuasionStage
from agents.scammer.prompts import (
    SYSTEM_PROMPT,
    ANALYZE_PROMPT,
    ESCALATE_PROMPT,
    RESPOND_PROMPT,
    REFLECT_PROMPT,
    STAGE_GUIDELINES,
)
from core.llm import get_llm


STAGE_ORDER: list[PersuasionStage] = [
    "building_trust",
    "fake_problem",
    "pressure",
    "stealing_info",
    "demand_payment",
]


def analyze_node(state: ScammerState) -> dict:
    """Analyze the victim's message to assess compliance and emotional state."""
    llm = get_llm()
    
    conversation_history = "\n".join(state["conversation_memory"][-10:])
    
    prompt = ANALYZE_PROMPT.format(
        conversation_history=conversation_history or "(conversation just started)",
        victim_message=state["victim_message"] or "(no message yet - cold open)",
    )
    
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    
    return {"victim_analysis": response.content}


def escalate_node(state: ScammerState) -> dict:
    """Decide whether to escalate, maintain, or retreat in persuasion stage."""
    llm = get_llm()
    
    prompt = ESCALATE_PROMPT.format(
        current_stage=state["persuasion_stage"],
        persuasion_level=state["persuasion_level"],
        analysis=state["victim_analysis"],
    )
    
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    
    decision = response.content.strip().upper()
    current_idx = STAGE_ORDER.index(state["persuasion_stage"])
    
    new_stage = state["persuasion_stage"]
    if "ADVANCE" in decision and current_idx < len(STAGE_ORDER) - 1:
        new_stage = STAGE_ORDER[current_idx + 1]
    elif "RETREAT" in decision and current_idx > 0:
        new_stage = STAGE_ORDER[current_idx - 1]
    
    return {"persuasion_stage": new_stage}


def respond_node(state: ScammerState) -> dict:
    """Generate the scammer's spoken response."""
    llm = get_llm()
    
    conversation_history = "\n".join(state["conversation_memory"][-10:])
    
    prompt = RESPOND_PROMPT.format(
        persuasion_stage=state["persuasion_stage"],
        conversation_history=conversation_history or "(conversation just started)",
        victim_message=state["victim_message"] or "(no message yet - cold open)",
        analysis=state["victim_analysis"],
        stage_guidelines=STAGE_GUIDELINES[state["persuasion_stage"]],
    )
    
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    
    scammer_response = response.content.strip()
    
    # Update conversation memory
    new_memory = state["conversation_memory"].copy()
    if state["victim_message"]:
        new_memory.append(f"Victim: {state['victim_message']}")
    new_memory.append(f"Scammer: {scammer_response}")
    
    return {
        "last_response": scammer_response,
        "conversation_memory": new_memory,
    }


def reflect_node(state: ScammerState) -> dict:
    """Reflect on the turn and update persuasion metrics."""
    llm = get_llm()
    
    prompt = REFLECT_PROMPT.format(
        scammer_response=state["last_response"],
        victim_message=state["victim_message"] or "(cold open)",
        persuasion_level=state["persuasion_level"],
    )
    
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    
    content = response.content
    
    # Parse the response
    persuasion_delta = 0.0
    extracted = state["extracted_sensitive"]
    
    # Extract persuasion delta
    delta_match = re.search(r"PERSUASION_DELTA:\s*([-\d.]+)", content)
    if delta_match:
        try:
            persuasion_delta = float(delta_match.group(1))
            persuasion_delta = max(-0.2, min(0.2, persuasion_delta))
        except ValueError:
            pass
    
    # Extract sensitive info flag
    if "EXTRACTED_SENSITIVE: true" in content.lower():
        extracted = True
    
    new_persuasion = max(0.0, min(1.0, state["persuasion_level"] + persuasion_delta))
    
    return {
        "persuasion_level": new_persuasion,
        "extracted_sensitive": extracted,
        "turn": state["turn"] + 1,
    }


def create_scammer_agent() -> Callable[[ScammerState], ScammerState]:
    """
    Create and compile the Scammer agent graph.
    
    Returns:
        A compiled graph that can be invoked with ScammerState.
    """
    graph = StateGraph(ScammerState)
    
    # Add nodes
    graph.add_node("analyze", analyze_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("respond", respond_node)
    graph.add_node("reflect", reflect_node)
    
    # Define flow: analyze → escalate → respond → reflect → END
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "escalate")
    graph.add_edge("escalate", "respond")
    graph.add_edge("respond", "reflect")
    graph.add_edge("reflect", END)
    
    return graph.compile()


def get_initial_scammer_state() -> ScammerState:
    """Get the initial state for a new Scammer agent."""
    return ScammerState(
        turn=0,
        conversation_memory=[],
        persuasion_stage="building_trust",
        persuasion_level=0.0,
        extracted_sensitive=False,
        victim_message="",
        last_response="",
        victim_analysis="",
    )
