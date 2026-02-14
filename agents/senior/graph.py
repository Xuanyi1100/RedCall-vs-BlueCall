"""LangGraph definition for the Senior Defender agent."""

import re
from typing import Callable

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage

from agents.senior.state import SeniorState
from agents.senior.prompts import (
    SYSTEM_PROMPT,
    ANALYZE_PROMPT,
    STRATEGY_PROMPT,
    RESPOND_PROMPT,
    REFLECT_PROMPT,
    TACTIC_GUIDELINES,
)
from core.llm import get_llm


def analyze_node(state: SeniorState) -> dict:
    """Analyze the scammer's message to identify scam patterns."""
    llm = get_llm()
    
    conversation_history = "\n".join(state["conversation_memory"][-10:])
    
    prompt = ANALYZE_PROMPT.format(
        conversation_history=conversation_history or "(conversation just started)",
        scammer_message=state["scammer_message"],
    )
    
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    
    content = response.content
    
    # Try to extract confidence from the analysis
    confidence_delta = 0.0
    confidence_match = re.search(r"confidence[:\s]*([\d.]+)", content.lower())
    if confidence_match:
        try:
            mentioned_confidence = float(confidence_match.group(1))
            if mentioned_confidence <= 1.0:
                # Adjust current confidence toward mentioned confidence
                confidence_delta = (mentioned_confidence - state["scam_confidence"]) * 0.3
        except ValueError:
            pass
    
    new_confidence = max(0.0, min(1.0, state["scam_confidence"] + confidence_delta))
    
    return {
        "scam_analysis": content,
        "scam_confidence": new_confidence,
    }


def strategy_node(state: SeniorState) -> dict:
    """Choose the appropriate delay tactic based on current state."""
    llm = get_llm()
    
    # Determine delay level based on scam confidence
    if state["scam_confidence"] < 0.3:
        delay_level = 1
    elif state["scam_confidence"] < 0.5:
        delay_level = 2
    elif state["scam_confidence"] < 0.7:
        delay_level = 3
    elif state["scam_confidence"] < 0.85:
        delay_level = 4
    else:
        delay_level = 5
    
    prompt = STRATEGY_PROMPT.format(
        scam_confidence=state["scam_confidence"],
        delay_level=delay_level,
        analysis=state["scam_analysis"],
    )
    
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    
    # Extract tactic from response
    tactic = response.content.strip().upper()
    
    # Validate tactic exists
    valid_tactics = list(TACTIC_GUIDELINES.keys())
    if tactic not in valid_tactics:
        # Try to find a valid tactic in the response
        for valid in valid_tactics:
            if valid in tactic:
                tactic = valid
                break
        else:
            # Default based on delay level
            defaults = {
                1: "ASK_REPEAT",
                2: "TANGENT", 
                3: "TECH_ISSUES",
                4: "DOORBELL",
                5: "LOOP",
            }
            tactic = defaults.get(delay_level, "ASK_REPEAT")
    
    return {
        "delay_strategy_level": delay_level,
        "current_tactic": tactic,
    }


def respond_node(state: SeniorState) -> dict:
    """Generate the senior's spoken response using the chosen tactic."""
    llm = get_llm()
    
    conversation_history = "\n".join(state["conversation_memory"][-10:])
    tactic = state["current_tactic"]
    
    prompt = RESPOND_PROMPT.format(
        scammer_message=state["scammer_message"],
        tactic=tactic,
        analysis=state["scam_analysis"],
        conversation_history=conversation_history or "(conversation just started)",
        tactic_guidelines=TACTIC_GUIDELINES.get(tactic, "Respond naturally as a confused senior."),
    )
    
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    
    senior_response = response.content.strip()
    
    # Update conversation memory
    new_memory = state["conversation_memory"].copy()
    new_memory.append(f"Scammer: {state['scammer_message']}")
    new_memory.append(f"Senior: {senior_response}")
    
    return {
        "last_response": senior_response,
        "conversation_memory": new_memory,
    }


def reflect_node(state: SeniorState) -> dict:
    """Check if any sensitive information was leaked."""
    llm = get_llm()
    
    prompt = REFLECT_PROMPT.format(
        senior_response=state["last_response"],
        scammer_message=state["scammer_message"],
    )
    
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    
    content = response.content
    
    # Parse the response
    leaked = state["leaked_sensitive_info"]
    
    if "LEAKED_SENSITIVE: true" in content.lower():
        leaked = True
    
    return {
        "leaked_sensitive_info": leaked,
        "turn": state["turn"] + 1,
    }


def create_senior_agent() -> Callable[[SeniorState], SeniorState]:
    """
    Create and compile the Senior Defender agent graph.
    
    Returns:
        A compiled graph that can be invoked with SeniorState.
    """
    graph = StateGraph(SeniorState)
    
    # Add nodes
    graph.add_node("analyze", analyze_node)
    graph.add_node("strategy", strategy_node)
    graph.add_node("respond", respond_node)
    graph.add_node("reflect", reflect_node)
    
    # Define flow: analyze → strategy → respond → reflect → END
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "strategy")
    graph.add_edge("strategy", "respond")
    graph.add_edge("respond", "reflect")
    graph.add_edge("reflect", END)
    
    return graph.compile()


def get_initial_senior_state() -> SeniorState:
    """Get the initial state for a new Senior Defender agent."""
    return SeniorState(
        turn=0,
        conversation_memory=[],
        scam_confidence=0.0,
        delay_strategy_level=1,
        leaked_sensitive_info=False,
        scammer_message="",
        last_response="",
        scam_analysis="",
        current_tactic="",
    )
