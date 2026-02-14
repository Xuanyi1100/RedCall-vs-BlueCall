"""State definition for the Scammer agent."""

from typing import List, Literal
from typing_extensions import TypedDict


PersuasionStage = Literal[
    "rapport",
    "scenario", 
    "urgency",
    "extraction",
    "final_push",
]


class ScammerState(TypedDict):
    """
    Internal state for the Scammer agent.
    
    This state is completely independent from the Senior agent's state.
    Communication happens only through dialogue text.
    """
    # Current turn number (internal tracking)
    turn: int
    
    # Conversation history (only dialogue, no internal state)
    conversation_memory: List[str]
    
    # Current persuasion stage in the scam progression
    persuasion_stage: PersuasionStage
    
    # How successful the persuasion has been (0.0 to 1.0)
    persuasion_level: float
    
    # Whether sensitive info has been extracted from victim
    extracted_sensitive: bool
    
    # The last message from the victim (input)
    victim_message: str
    
    # The scammer's response (output)
    last_response: str
    
    # Internal analysis of victim's compliance
    victim_analysis: str
