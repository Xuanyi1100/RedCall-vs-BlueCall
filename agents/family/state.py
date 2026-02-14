"""State definition for the Family Agent."""

from typing import List
from typing_extensions import TypedDict


class FamilyState(TypedDict):
    """
    Internal state for the Family Agent (legitimate caller).
    
    This agent simulates a family member calling the senior.
    Used for testing false positive rates in the defender.
    """
    # Current turn number (internal tracking)
    turn: int
    
    # Conversation history (only dialogue, no internal state)
    conversation_memory: List[str]
    
    # The family member's relationship to the senior
    relationship: str  # e.g., "grandson", "daughter", "nephew"
    
    # The family member's name
    caller_name: str
    
    # The reason for calling
    call_reason: str  # e.g., "checking in", "planning visit", "birthday"
    
    # Whether the senior has recognized them yet
    recognized: bool
    
    # Whether the call was successfully handed off (goal achieved)
    handed_off: bool
    
    # The last message from the senior (input)
    senior_message: str
    
    # The family member's response (output)
    last_response: str
