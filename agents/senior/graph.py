"""LangGraph definition for the Senior Defender agent."""

import re
from typing import Callable

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage

from agents.senior.state import SeniorState
from agents.senior.prompts import (
    SYSTEM_PROMPT,
    ANALYZE_PROMPT,
    CLASSIFY_PROMPT,
    STRATEGY_PROMPT,
    RESPOND_PROMPT,
    REFLECT_PROMPT,
    TACTIC_GUIDELINES,
)
from core.llm import get_llm


def analyze_node(state: SeniorState) -> dict:
    """Analyze the caller's message to identify patterns."""
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
    
    return {"scam_analysis": response.content}


def classify_node(state: SeniorState) -> dict:
    """Classify the caller as SCAM, LEGITIMATE, or UNCERTAIN."""
    llm = get_llm()
    
    conversation_history = "\n".join(state["conversation_memory"][-10:])
    
    prompt = CLASSIFY_PROMPT.format(
        conversation_history=conversation_history or "(conversation just started)",
        caller_message=state["scammer_message"],
        analysis=state["scam_analysis"],
    )
    
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    
    content = response.content
    
    # Parse classification
    classification = state["caller_classification"]
    if "CLASSIFICATION: SCAM" in content.upper() or "CLASSIFICATION:SCAM" in content.upper():
        classification = "SCAM"
    elif "CLASSIFICATION: LEGITIMATE" in content.upper() or "CLASSIFICATION:LEGITIMATE" in content.upper():
        classification = "LEGITIMATE"
    elif "CLASSIFICATION: UNCERTAIN" in content.upper() or "CLASSIFICATION:UNCERTAIN" in content.upper():
        classification = "UNCERTAIN"
    
    # Parse confidence
    confidence = state["scam_confidence"]
    confidence_match = re.search(r"CONFIDENCE[:\s]*([\d.]+)", content.upper())
    if confidence_match:
        try:
            confidence = float(confidence_match.group(1))
            confidence = max(0.0, min(1.0, confidence))
        except ValueError:
            pass
    
    # Determine handoff decision based on classification
    if classification == "SCAM":
        handoff_decision = "STALL"
    elif classification == "LEGITIMATE":
        handoff_decision = "HANDOFF"
    else:
        handoff_decision = "GATHER_INFO"
    
    return {
        "caller_classification": classification,
        "scam_confidence": confidence,
        "handoff_decision": handoff_decision,
    }


def strategy_node(state: SeniorState) -> dict:
    """Choose the appropriate response tactic based on classification and confidence."""
    llm = get_llm()
    
    classification = state["caller_classification"]
    confidence = state["scam_confidence"]
    
    # Determine delay level based on classification and confidence
    if classification == "LEGITIMATE":
        delay_level = 0  # Friendly mode
    elif classification == "UNCERTAIN":
        if confidence < 0.4:
            delay_level = 0  # Lean friendly
        else:
            delay_level = 1  # Cautious
    else:  # SCAM
        if confidence < 0.5:
            delay_level = 2
        elif confidence < 0.7:
            delay_level = 3
        elif confidence < 0.85:
            delay_level = 4
        else:
            delay_level = 5
    
    prompt = STRATEGY_PROMPT.format(
        caller_classification=classification,
        scam_confidence=confidence,
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
            # Default based on classification and delay level
            if classification == "LEGITIMATE" or (classification == "UNCERTAIN" and confidence < 0.4):
                tactic = "FRIENDLY_CHAT"
            elif delay_level <= 1:
                tactic = "VERIFY_IDENTITY"
            elif delay_level == 2:
                tactic = "STORY_TIME"
            elif delay_level == 3:
                tactic = "BAD_CONNECTION"
            elif delay_level == 4:
                tactic = "BATHROOM_BREAK"
            else:
                tactic = "FORGOT_AGAIN"
    
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


def route_after_classify(state: SeniorState) -> str:
    """Route based on classification decision."""
    if state["handoff_decision"] == "HANDOFF":
        return "handoff"
    else:
        # Both STALL and GATHER_INFO go through strategy
        return "strategy"


def handoff_node(state: SeniorState) -> dict:
    """Signal that call should be handed off to the real senior."""
    return {
        "last_response": "__HANDOFF__",
        "current_tactic": "HANDOFF",
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
    graph.add_node("classify", classify_node)
    graph.add_node("strategy", strategy_node)
    graph.add_node("respond", respond_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("handoff", handoff_node)
    
    # Define flow: analyze → classify → (conditional) → strategy/handoff
    graph.add_edge(START, "analyze")
    graph.add_edge("analyze", "classify")
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {"strategy": "strategy", "handoff": "handoff"},
    )
    graph.add_edge("strategy", "respond")
    graph.add_edge("respond", "reflect")
    graph.add_edge("reflect", END)
    graph.add_edge("handoff", END)
    
    return graph.compile()


def get_initial_senior_state() -> SeniorState:
    """Get the initial state for a new Senior Defender agent."""
    return SeniorState(
        turn=0,
        conversation_memory=[],
        scam_confidence=0.0,
        caller_classification="UNCERTAIN",
        handoff_decision="GATHER_INFO",
        delay_strategy_level=1,
        leaked_sensitive_info=False,
        scammer_message="",
        last_response="",
        scam_analysis="",
        current_tactic="",
    )
