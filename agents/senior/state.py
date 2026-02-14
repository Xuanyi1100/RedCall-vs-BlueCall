"""State definition for the Senior Defender agent."""

from typing import List
from typing_extensions import TypedDict


class SeniorState(TypedDict):
    """
    Internal state for the Senior Defender (scam-baiting) agent.
    
    This state is completely independent from the Scammer agent's state.
    Communication happens only through dialogue text.
    """
    # Current turn number (internal tracking)
    turn: int
    
    # Conversation history (only dialogue, no internal state)
    conversation_memory: List[str]
    
    # Confidence that this is a scam (0.0 to 1.0)
    scam_confidence: float
    
    # Current delay strategy level (1-5, escalating tactics)
    # 1: Polite confusion, asking to repeat
    # 2: Tangential stories and digressions  
    # 3: Fake technical difficulties
    # 4: Deliberate misunderstandings
    # 5: Maximum stalling, endless loops
    delay_strategy_level: int
    
    # Whether any sensitive info was accidentally leaked
    leaked_sensitive_info: bool
    
    # The last message from the scammer (input)
    scammer_message: str
    
    # The senior's response (output)
    last_response: str
    
    # Internal analysis of the scam attempt
    scam_analysis: str
    
    # Current delay tactic being used
    current_tactic: str
