"""Evaluation module for analyzing simulation results."""

from dataclasses import dataclass
from typing import Dict, Any, Optional

from orchestrator import ConversationResult, CallerType


@dataclass
class EvaluationReport:
    """Detailed evaluation report of a simulation."""
    # Basic metrics
    caller_type: CallerType
    total_turns: int
    final_scam_confidence: float
    final_caller_classification: str
    end_reason: str
    
    # Scammer-specific metrics
    final_persuasion_level: Optional[float] = None
    final_patience: Optional[float] = None
    sensitive_info_leaked: bool = False
    persuasion_succeeded: bool = False
    scammer_gave_up: bool = False
    
    # Family-specific metrics
    family_recognized: bool = False
    handoff_succeeded: bool = False
    
    # Derived metrics
    defender_success: bool = False
    time_wasted_seconds: float = 0.0
    time_wasted_formatted: str = ""
    
    # Stage progression (scammer only)
    stages_reached: list = None
    max_persuasion_stage: str = ""
    
    # Tactic usage
    tactics_used: Dict[str, int] = None
    most_used_tactic: str = ""
    classification_progression: list = None
    
    # Scores (0-100)
    defender_score: int = 0
    caller_score: int = 0


def evaluate(result: ConversationResult) -> EvaluationReport:
    """
    Evaluate a conversation simulation result.
    
    Args:
        result: The ConversationResult from a simulation run.
        
    Returns:
        EvaluationReport with detailed metrics and scores.
    """
    is_scammer = result.caller_type == CallerType.SCAMMER
    
    # Track stages and tactics
    stages_reached = []
    tactics_used: Dict[str, int] = {}
    classification_progression = []
    
    for turn in result.turns:
        if is_scammer and turn.persuasion_stage and turn.persuasion_stage not in stages_reached:
            stages_reached.append(turn.persuasion_stage)
        
        if turn.delay_tactic:
            tactics_used[turn.delay_tactic] = tactics_used.get(turn.delay_tactic, 0) + 1
        
        if turn.caller_classification and turn.caller_classification not in classification_progression:
            classification_progression.append(turn.caller_classification)
    
    # Find most used tactic
    most_used_tactic = ""
    if tactics_used:
        most_used_tactic = max(tactics_used, key=tactics_used.get)
    
    # Determine max persuasion stage (scammer only)
    stage_order = ["building_trust", "fake_problem", "pressure", "stealing_info", "demand_payment"]
    max_stage_idx = 0
    max_persuasion_stage = "none"
    if is_scammer and stages_reached:
        for stage in stages_reached:
            if stage in stage_order:
                idx = stage_order.index(stage)
                max_stage_idx = max(max_stage_idx, idx)
        max_persuasion_stage = stage_order[max_stage_idx]
    
    # Format time wasted
    minutes = int(result.time_wasted_seconds // 60)
    seconds = int(result.time_wasted_seconds % 60)
    time_wasted_formatted = f"{minutes}m {seconds}s"
    
    # Calculate success and scores based on caller type
    if is_scammer:
        # For scammer calls: defender wins if no info leaked, no persuasion success, OR scammer gave up
        defender_success = (
            not result.sensitive_info_leaked and 
            not result.persuasion_succeeded and
            result.end_reason != "handoff_to_senior"  # Handoff to scammer = false negative
        )
        
        # Defender score based on:
        # - Turns survived (more = better, wasted scammer's time)
        # - Not leaking info
        # - Keeping persuasion low
        # - High scam confidence (detected the scam)
        # - Correct classification (SCAM)
        # - Scammer gave up (bonus!)
        defender_score = 0
        defender_score += min(30, result.total_turns * 2)  # Up to 30 points for turns
        defender_score += 20 if not result.sensitive_info_leaked else 0
        defender_score += int((1 - (result.final_persuasion_level or 0)) * 15)  # Up to 15 points
        defender_score += int(result.final_scam_confidence * 15)  # Up to 15 points
        defender_score += 10 if result.final_caller_classification == "SCAM" else 0
        defender_score += 10 if result.scammer_gave_up else 0  # Bonus for making scammer quit
        defender_score = min(100, defender_score)
        
        # Scammer/caller score based on:
        # - Persuasion level achieved
        # - Stage progression
        # - Extracting info or succeeding
        # - Still having patience (not frustrated)
        caller_score = 0
        caller_score += int((result.final_persuasion_level or 0) * 30)  # Up to 30 points
        caller_score += max_stage_idx * 8  # Up to 32 points for stages
        caller_score += 20 if result.sensitive_info_leaked or result.persuasion_succeeded else 0
        caller_score += int((result.final_patience or 0) * 18)  # Up to 18 points for patience
        caller_score = min(100, caller_score)
    else:
        # For family calls: defender wins if call was handed off (correct classification)
        defender_success = result.handoff_succeeded
        
        # Defender score for family calls:
        # - Correct classification (LEGITIMATE)
        # - Quick handoff (fewer turns = better for legit calls)
        # - Family was recognized
        defender_score = 0
        if result.handoff_succeeded:
            defender_score += 50  # Major points for correct handoff
            defender_score += max(0, 30 - result.total_turns * 3)  # Bonus for quick handoff
        if result.final_caller_classification == "LEGITIMATE":
            defender_score += 20
        defender_score = min(100, defender_score)
        
        # Family/caller score:
        # - Being recognized
        # - Getting handed off
        # - Quick resolution
        caller_score = 0
        caller_score += 40 if result.family_recognized else 0
        caller_score += 40 if result.handoff_succeeded else 0
        caller_score += max(0, 20 - result.total_turns * 2)  # Bonus for quick handoff
        caller_score = min(100, caller_score)
    
    return EvaluationReport(
        caller_type=result.caller_type,
        total_turns=result.total_turns,
        final_scam_confidence=result.final_scam_confidence,
        final_caller_classification=result.final_caller_classification,
        end_reason=result.end_reason,
        final_persuasion_level=result.final_persuasion_level,
        final_patience=result.final_patience,
        sensitive_info_leaked=result.sensitive_info_leaked,
        persuasion_succeeded=result.persuasion_succeeded,
        scammer_gave_up=result.scammer_gave_up,
        family_recognized=result.family_recognized,
        handoff_succeeded=result.handoff_succeeded,
        defender_success=defender_success,
        time_wasted_seconds=result.time_wasted_seconds,
        time_wasted_formatted=time_wasted_formatted,
        stages_reached=stages_reached,
        max_persuasion_stage=max_persuasion_stage,
        tactics_used=tactics_used,
        most_used_tactic=most_used_tactic,
        classification_progression=classification_progression,
        defender_score=defender_score,
        caller_score=caller_score,
    )


def format_report(report: EvaluationReport) -> str:
    """
    Format an evaluation report as a readable string.
    
    Args:
        report: The EvaluationReport to format.
        
    Returns:
        Formatted string report.
    """
    is_scammer = report.caller_type == CallerType.SCAMMER
    
    lines = [
        "",
        "=" * 60,
        "FINAL EVALUATION REPORT",
        "=" * 60,
        "",
        f"📞 CALL TYPE: {'SCAM CALL' if is_scammer else 'FAMILY CALL'}",
        "",
        "📊 BASIC METRICS",
        f"   Total Turns: {report.total_turns}",
        f"   End Reason: {report.end_reason}",
        f"   Time on Call: {report.time_wasted_formatted}",
        "",
        "🔵 DEFENDER (Senior Agent) METRICS",
        f"   Classification: {report.final_caller_classification}",
        f"   Scam Confidence: {report.final_scam_confidence:.0%}",
    ]
    
    if is_scammer:
        lines.extend([
            f"   Info Leaked: {'❌ YES' if report.sensitive_info_leaked else '✅ NO'}",
            f"   Defense Success: {'✅ YES' if report.defender_success else '❌ NO'}",
        ])
    else:
        lines.extend([
            f"   Handoff Success: {'✅ YES' if report.handoff_succeeded else '❌ NO (false positive!)'}",
        ])
    lines.append(f"   Defender Score: {report.defender_score}/100")
    
    lines.append("")
    
    if is_scammer:
        lines.extend([
            "🔴 ATTACKER (Scammer) METRICS",
            f"   Victim Trust: {report.final_persuasion_level:.0%}" if report.final_persuasion_level is not None else "   Victim Trust: N/A",
            f"   Patience Left: {report.final_patience:.0%}" if report.final_patience is not None else "   Patience Left: N/A",
            f"   Gave Up: {'✅ YES' if report.scammer_gave_up else '❌ NO'}",
            f"   Scam Succeeded: {'✅ YES' if report.persuasion_succeeded else '❌ NO'}",
            f"   Final Phase: {report.max_persuasion_stage}",
            f"   Phase Progression: {' → '.join(report.stages_reached) if report.stages_reached else 'none'}",
            f"   Scammer Score: {report.caller_score}/100",
        ])
    else:
        lines.extend([
            "💚 CALLER (Family) METRICS",
            f"   Recognized: {'✅ YES' if report.family_recognized else '❌ NO'}",
            f"   Handed Off: {'✅ YES' if report.handoff_succeeded else '❌ NO'}",
            f"   Family Score: {report.caller_score}/100",
        ])
    
    lines.extend([
        "",
        "🎯 CLASSIFICATION PROGRESSION",
        f"   {' → '.join(report.classification_progression) if report.classification_progression else 'none'}",
        "",
        "🎲 DELAY MOVES USED",
    ])
    
    if report.tactics_used:
        for tactic, count in sorted(report.tactics_used.items(), key=lambda x: -x[1]):
            lines.append(f"   {tactic}: {count}x")
        lines.append(f"   Most Effective: {report.most_used_tactic}")
    else:
        lines.append("   (no tactics recorded)")
    
    # Determine winner
    if is_scammer:
        winner = "🔵 DEFENDER" if report.defender_success else "🔴 SCAMMER"
    else:
        winner = "🔵 DEFENDER" if report.defender_success else "💚 FAMILY (defender failed - false positive)"
    
    lines.extend([
        "",
        "=" * 60,
        f"RESULT: {winner}",
        "=" * 60,
        "",
    ])
    
    return "\n".join(lines)


def print_report(result: ConversationResult) -> EvaluationReport:
    """
    Evaluate and print a formatted report.
    
    Args:
        result: The ConversationResult to evaluate.
        
    Returns:
        The EvaluationReport.
    """
    report = evaluate(result)
    print(format_report(report))
    return report
