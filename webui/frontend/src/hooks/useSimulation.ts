import { useState, useCallback, useRef, useEffect } from 'react';
import { SimulationState, SimulationConfig, WSEvent, ScammerState, SeniorState } from '../types';

const initialScammerState: ScammerState = {
  persuasion_stage: 'building_trust',
  persuasion_level: 0,
  patience: 1,
  frustration_turns: 0,
  gave_up: false,
  victim_analysis: '',
};

const initialSeniorState: SeniorState = {
  scam_confidence: 0,
  caller_classification: 'UNCERTAIN',
  handoff_decision: 'GATHER_INFO',
  delay_strategy_level: 1,
  current_tactic: '',
  scam_analysis: '',
};

const initialState: SimulationState = {
  status: 'idle',
  turn: 0,
  activeCaptionTurn: null,
  maxTurns: 15,
  elapsedSeconds: 0,
  endReason: null,
  voiceEnabled: true,
  scammerState: initialScammerState,
  seniorState: initialSeniorState,
  messages: [],
  liveCaptions: [],
  currentSpeaker: null,
};

export function useSimulation() {
  const [state, setState] = useState<SimulationState>(initialState);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const audioQueueRef = useRef<string[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const isPlayingRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const startEpochRef = useRef<number | null>(null);
  const captionIdRef = useRef(0);

  const stopTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startTimer = useCallback(() => {
    stopTimer();
    startEpochRef.current = Date.now();
    timerRef.current = window.setInterval(() => {
      const startEpoch = startEpochRef.current;
      if (!startEpoch) return;
      const elapsed = Math.floor((Date.now() - startEpoch) / 1000);
      setState(prev => (
        prev.status === 'running'
          ? { ...prev, elapsedSeconds: elapsed }
          : prev
      ));
    }, 1000);
  }, [stopTimer]);

  const getElapsedNow = useCallback(() => {
    const startEpoch = startEpochRef.current;
    if (!startEpoch) return 0;
    return Math.floor((Date.now() - startEpoch) / 1000);
  }, []);

  const playNextAudio = useCallback(() => {
    if (audioQueueRef.current.length === 0 || isPlayingRef.current) {
      return;
    }

    const audioBase64 = audioQueueRef.current.shift();
    if (!audioBase64) return;

    isPlayingRef.current = true;
    const audio = new Audio(`data:audio/wav;base64,${audioBase64}`);
    audioRef.current = audio;

    audio.onended = () => {
      isPlayingRef.current = false;
      playNextAudio();
    };

    audio.onerror = () => {
      isPlayingRef.current = false;
      playNextAudio();
    };

    audio.play().catch(() => {
      isPlayingRef.current = false;
      playNextAudio();
    });
  }, []);

  const queueAudio = useCallback((audioBase64: string | null | undefined) => {
    if (audioBase64) {
      audioQueueRef.current.push(audioBase64);
      playNextAudio();
    }
  }, [playNextAudio]);

  const handleWSEvent = useCallback((event: WSEvent) => {
    switch (event.type) {
      case 'simulation_started':
        captionIdRef.current = 0;
        startTimer();
        setState(prev => ({
          ...prev,
          status: 'running',
          turn: 0,
          activeCaptionTurn: null,
          maxTurns: event.data.max_turns || 15,
          elapsedSeconds: 0,
          voiceEnabled: event.data.voice_enabled || false,
          scammerState: event.data.scammer_state || initialScammerState,
          seniorState: event.data.senior_state || initialSeniorState,
          messages: [],
          liveCaptions: [],
          endReason: null,
          currentSpeaker: null,
        }));
        break;

      case 'turn_start':
        setState(prev => ({
          ...prev,
          turn: event.data.turn || prev.turn,
        }));
        break;

      case 'scammer_message':
        setState(prev => ({
          ...prev,
          currentSpeaker: 'scammer',
          scammerState: event.data.scammer_state || prev.scammerState,
          messages: [...prev.messages, {
            turn: event.data.turn || prev.turn,
            speaker: 'scammer',
            message: event.data.message || '',
            audio_base64: event.data.audio_base64,
            timestamp: new Date(),
          }],
        }));
        queueAudio(event.data.audio_base64);
        break;

      case 'senior_message':
        setState(prev => ({
          ...prev,
          currentSpeaker: 'senior',
          seniorState: event.data.senior_state || prev.seniorState,
          messages: [...prev.messages, {
            turn: event.data.turn || prev.turn,
            speaker: 'senior',
            message: event.data.message || '',
            audio_base64: event.data.audio_base64,
            timestamp: new Date(),
          }],
        }));
        queueAudio(event.data.audio_base64);
        break;

      case 'scammer_gave_up':
        setState(prev => ({
          ...prev,
          currentSpeaker: 'scammer',
          scammerState: event.data.scammer_state || prev.scammerState,
          messages: [...prev.messages, {
            turn: event.data.turn || prev.turn,
            speaker: 'scammer',
            message: event.data.message || '',
            audio_base64: event.data.audio_base64,
            timestamp: new Date(),
          }],
        }));
        queueAudio(event.data.audio_base64);
        break;

      case 'live_caption':
        if (!event.data.speaker || !event.data.sentence) {
          break;
        }
        const captionSpeaker = event.data.speaker;
        const captionSentence = event.data.sentence;
        captionIdRef.current += 1;
        setState(prev => ({
          ...prev,
          currentSpeaker: captionSpeaker,
          activeCaptionTurn: event.data.turn || prev.activeCaptionTurn,
          liveCaptions: [...prev.liveCaptions, {
            id: captionIdRef.current,
            turn: event.data.turn || prev.turn,
            speaker: captionSpeaker,
            sentence: captionSentence,
            timestamp: new Date(),
          }].slice(-120),
        }));
        break;

      case 'live_caption_done':
        setState(prev => ({
          ...prev,
          currentSpeaker: null,
        }));
        break;

      case 'simulation_end':
        stopTimer();
        setState(prev => ({
          ...prev,
          status: 'completed',
          currentSpeaker: null,
          endReason: event.data.reason || null,
          elapsedSeconds: Math.max(prev.elapsedSeconds, getElapsedNow()),
          scammerState: event.data.scammer_state || prev.scammerState,
          seniorState: event.data.senior_state || prev.seniorState,
        }));
        break;

      case 'simulation_stopped':
        stopTimer();
        setState(prev => ({
          ...prev,
          status: 'completed',
          currentSpeaker: null,
          endReason: 'stopped',
          elapsedSeconds: Math.max(prev.elapsedSeconds, getElapsedNow()),
        }));
        break;

      case 'error':
        // Keep UI state stable but stop timer if backend errors out.
        stopTimer();
        break;
    }
  }, [getElapsedNow, queueAudio, startTimer, stopTimer]);

  const connect = useCallback(() => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/ws/simulation`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onclose = () => {
      setConnected(false);
      stopTimer();
    };

    ws.onerror = () => {
      stopTimer();
    };

    ws.onmessage = (event) => {
      const wsEvent: WSEvent = JSON.parse(event.data);
      handleWSEvent(wsEvent);
    };
  }, [handleWSEvent, stopTimer]);

  const start = useCallback((config: SimulationConfig) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    audioQueueRef.current = [];
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    isPlayingRef.current = false;

    wsRef.current.send(JSON.stringify({
      action: 'start',
      config,
    }));
  }, []);

  const stop = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    wsRef.current.send(JSON.stringify({
      action: 'stop',
    }));
  }, []);

  const reset = useCallback(() => {
    stopTimer();
    startEpochRef.current = null;
    captionIdRef.current = 0;
    audioQueueRef.current = [];
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    isPlayingRef.current = false;
    setState(initialState);
  }, [stopTimer]);

  useEffect(() => {
    connect();
    return () => {
      stopTimer();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect, stopTimer]);

  return {
    state,
    connected,
    start,
    stop,
    reset,
  };
}
