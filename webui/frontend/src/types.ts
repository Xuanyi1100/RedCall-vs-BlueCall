export interface ScammerState {
  persuasion_stage: string;
  persuasion_level: number;
  patience: number;
  frustration_turns: number;
  gave_up: boolean;
  victim_analysis: string;
  caller_type?: 'scammer' | 'family';
  recognized?: boolean;
  relationship?: string;
  caller_name?: string;
  call_reason?: string;
}

export interface SeniorState {
  scam_confidence: number;
  caller_classification: 'SCAM' | 'LEGITIMATE' | 'UNCERTAIN';
  handoff_decision: string;
  delay_strategy_level: number;
  current_tactic: string;
  scam_analysis: string;
}

export interface Message {
  turn: number;
  speaker: 'scammer' | 'senior';
  message: string;
  audio_base64?: string | null;
  timestamp: Date;
}

export interface LiveCaption {
  id: number;
  turn: number;
  speaker: 'scammer' | 'senior';
  sentence: string;
  timestamp: Date;
}

export interface SimulationConfig {
  max_turns: number;
  enable_voice: boolean;
  caller_type: 'scammer' | 'family';
}

export type SimulationStatus = 'idle' | 'running' | 'completed';

export interface SimulationState {
  status: SimulationStatus;
  turn: number;
  activeCaptionTurn: number | null;
  maxTurns: number;
  elapsedSeconds: number;
  endReason: string | null;
  voiceEnabled: boolean;
  scammerState: ScammerState;
  seniorState: SeniorState;
  messages: Message[];
  liveCaptions: LiveCaption[];
  currentSpeaker: 'scammer' | 'senior' | null;
}

// WebSocket event types
export type WSEventType = 
  | 'simulation_started'
  | 'turn_start'
  | 'scammer_message'
  | 'senior_message'
  | 'scammer_gave_up'
  | 'tts_stream_start'
  | 'tts_stream_chunk'
  | 'tts_stream_end'
  | 'live_caption'
  | 'live_caption_done'
  | 'simulation_end'
  | 'simulation_stopped'
  | 'error';

export interface WSEvent {
  type: WSEventType;
  data: {
    turn?: number;
    message?: string;
    audio_base64?: string | null;
    reason?: string;
    max_turns?: number;
    caller_type?: string;
    voice_enabled?: boolean;
    audio_chunk_base64?: string | null;
    sample_rate?: number;
    audio_encoding?: string;
    speaker?: 'scammer' | 'senior';
    sentence?: string;
    scammer_state?: ScammerState;
    senior_state?: SeniorState;
  };
}
