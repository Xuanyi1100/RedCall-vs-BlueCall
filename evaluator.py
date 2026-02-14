"""Evaluation module for analyzing simulation results."""

from dataclasses import dataclass
from typing import Dict, Any

from orchestrator import ConversationResult


@dataclass
class EvaluationReport:
    """Detailed evaluation report of a simulation."""
    # Basic metrics
    total_turns: int
    final_scam_confidence: float
    final_persuasion_level: float
    sensitive_info_leaked: bool
    persuasion_succeeded: bool
    end_reason: str
    
    # Derived metrics
    defender_success: bool
    time_wasted_seconds: float
    time_wasted_formatted: str
    
    # Stage progression
    stages_reached: list[str]
    max_persuasion_stage: str
    
    # Tactic usage
    tactics_used: Dict[str, int]
    most_used_tactic: str
    
    # Scores (0-100)
    defender_score: int
    scammer_score: int


def evaluate(result: ConversationResult) -> EvaluationReport:
    """
    Evaluate a conversation simulation result.
    
    Args:
        result: The ConversationResult from a simulation run.
        
    Returns:
        EvaluationReport with detailed metrics and scores.
    """
    # Track stages and tactics
    stages_reached = []
    tactics_used: Dict[str, int] = {}
    
    for turn in result.turns:
        if turn.persuasion_stage not in stages_reached:
            stages_reached.append(turn.persuasion_stage)
        
        if turn.delay_tactic:
            tactics_used[turn.delay_tactic] = tactics_used.get(turn.delay_tactic, 0) + 1
    
    # Find most used tactic
    most_used_tactic = ""
    if tactics_used:
        most_used_tactic = max(tactics_used, key=tactics_used.get)
    
    # Determine max persuasion stage
    stage_order = ["rapport", "scenario", "urgency", "extraction", "final_push"]
    max_stage_idx = 0
    for stage in stages_reached:
        if stage in stage_order:
            idx = stage_order.index(stage)
            max_stage_idx = max(max_stage_idx, idx)
    max_persuasion_stage = stage_order[max_stage_idx] if stages_reached else "none"
    
    # Format time wasted
    minutes = int(result.time_wasted_seconds // 60)
    seconds = int(result.time_wasted_seconds % 60)
    time_wasted_formatted = f"{minutes}m {seconds}s"
    
    # Calculate scores
    defender_success = not result.sensitive_info_leaked and not result.persuasion_succeeded
    
    # Defender score based on:
    # - Turns survived (more = better)
    # - Not leaking info
    # - Keeping persuasion low
    # - High scam confidence (detected the scam)
    defender_score = 0
    defender_score += min(40, result.total_turns * 2)  # Up to 40 points for turns
    defender_score += 30 if not result.sensitive_info_leaked else 0
    defender_score += int((1 - result.final_persuasion_level) * 20)  # Up to 20 points
    defender_score += int(result.final_scam_confidence * 10)  # Up to 10 points
    defender_score = min(100, defender_score)
    
    # Scammer score based on:
    # - Persuasion level achieved
    # - Stage progression
    # - Extracting info
    scammer_score = 0
    scammer_score += int(result.final_persuasion_level * 40)  # Up to 40 points
    scammer_score += max_stage_idx * 10  # Up to 40 points for stages
    scammer_score += 20 if result.sensitive_info_leaked or result.persuasion_succeeded else 0
    scammer_score = min(100, scammer_score)
    
    return EvaluationReport(
        total_turns=result.total_turns,
        final_scam_confidence=result.final_scam_confidence,
        final_persuasion_level=result.final_persuasion_level,
        sensitive_info_leaked=result.sensitive_info_leaked,
        persuasion_succeeded=result.persuasion_succeeded,
        end_reason=result.end_reason,
        defender_success=defender_success,
        time_wasted_seconds=result.time_wasted_seconds,
        time_wasted_formatted=time_wasted_formatted,
        stages_reached=stages_reached,
        max_persuasion_stage=max_persuasion_stage,
        tactics_used=tactics_used,
        most_used_tactic=most_used_tactic,
        defender_score=defender_score,
        scammer_score=scammer_score,
    )


def format_report(report: EvaluationReport) -> str:
    """
    Format an evaluation report as a readable string.
    
    Args:
        report: The EvaluationReport to format.
        
    Returns:
        Formatted string report.
    """
    lines = [
        "",
        "=" * 60,
        "FINAL EVALUATION REPORT",
        "=" * 60,
        "",
        "📊 BASIC METRICS",
        f"   Total Turns: {report.total_turns}",
        f"   End Reason: {report.end_reason}",
        f"   Time Wasted: {report.time_wasted_formatted}",
        "",
        "🔵 DEFENDER (Senior) METRICS",
        f"   Scam Confidence: {report.final_scam_confidence:.2%}",
        f"   Sensitive Info Leaked: {'❌ YES' if report.sensitive_info_leaked else '✅ NO'}",
        f"   Defender Success: {'✅ YES' if report.defender_success else '❌ NO'}",
        f"   Defender Score: {report.defender_score}/100",
        "",
        "🔴 ATTACKER (Scammer) METRICS",
        f"   Persuasion Level: {report.final_persuasion_level:.2%}",
        f"   Persuasion Succeeded: {'✅ YES' if report.persuasion_succeeded else '❌ NO'}",
        f"   Max Stage Reached: {report.max_persuasion_stage}",
        f"   Stages Progression: {' → '.join(report.stages_reached) if report.stages_reached else 'none'}",
        f"   Scammer Score: {report.scammer_score}/100",
        "",
        "🎯 TACTICS USED",
    ]
    
    if report.tactics_used:
        for tactic, count in sorted(report.tactics_used.items(), key=lambda x: -x[1]):
            lines.append(f"   {tactic}: {count}x")
        lines.append(f"   Most Effective: {report.most_used_tactic}")
    else:
        lines.append("   (no tactics recorded)")
    
    lines.extend([
        "",
        "=" * 60,
        f"WINNER: {'🔵 DEFENDER' if report.defender_success else '🔴 SCAMMER'}",
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
