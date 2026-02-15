import { useState } from 'react';
import { useSimulation } from './hooks/useSimulation';
import { AgentCard } from './components/AgentCard';
import { CallHeader } from './components/CallHeader';
import { Controls } from './components/Controls';
import { ConversationPanel } from './components/ConversationPanel';

function App() {
  const { state, connected, start, stop, reset } = useSimulation();
  const [showThoughts, setShowThoughts] = useState(true);
  const [callerType, setCallerType] = useState<'scammer' | 'family'>('scammer');
  const [maxTurns, setMaxTurns] = useState(15);
  const [enableVoice, setEnableVoice] = useState(true);

  const handleStart = () => {
    start({
      max_turns: maxTurns,
      enable_voice: enableVoice,
      caller_type: callerType,
    });
  };


  const transcriptTurn = state.activeCaptionTurn ?? state.turn;

  const scammerLiveLines = state.liveCaptions
    .filter(c => c.turn === transcriptTurn)
    .filter(c => c.speaker === 'scammer')
    .slice(-6)
    .map(c => c.sentence);
  
  const seniorLiveLines = state.liveCaptions
    .filter(c => c.turn === transcriptTurn)
    .filter(c => c.speaker === 'senior')
    .slice(-6)
    .map(c => c.sentence);

  const callerThoughts =
    callerType === 'scammer'
      ? state.scammerState.victim_analysis
      : '';

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-950 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Title */}
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-red-500 via-purple-500 to-blue-500 bg-clip-text text-transparent">
            Scammers Nightmare Calls Tester
          </h1>
          <p className="text-slate-400 mt-1">Voice AI Agent Scam Defense Demo</p>
        </div>

        {/* Controls */}
        <Controls
          status={state.status}
          connected={connected}
          callerType={callerType}
          setCallerType={setCallerType}
          maxTurns={maxTurns}
          setMaxTurns={setMaxTurns}
          enableVoice={enableVoice}
          setEnableVoice={setEnableVoice}
          showThoughts={showThoughts}
          setShowThoughts={setShowThoughts}
          onStart={handleStart}
          onStop={stop}
          onReset={reset}
        />

        {/* Call Header */}
        <CallHeader
          status={state.status}
          turn={state.turn}
          maxTurns={state.maxTurns}
          elapsedSeconds={state.elapsedSeconds}
          endReason={state.endReason}
        />

        {/* Main Call Interface */}
        {state.status !== 'idle' ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Scammer Card */}
            <AgentCard
              type={callerType}
              isSpeaking={state.currentSpeaker === 'scammer'}
              liveLines={scammerLiveLines}
              thoughts={showThoughts ? callerThoughts : ''}
              showThoughts={showThoughts}
              metrics={callerType === 'scammer'
                ? {
                    persuasion_stage: state.scammerState.persuasion_stage,
                    persuasion_level: state.scammerState.persuasion_level,
                    patience: state.scammerState.patience,
                  }
                : {
                    recognized: Boolean(state.scammerState.recognized),
                    caller_name: state.scammerState.caller_name || 'Family Member',
                    relationship: state.scammerState.relationship || 'relative',
                    call_reason: state.scammerState.call_reason || 'Checking in',
                  }}
            />

            {/* Senior Card */}
            <AgentCard
              type="senior"
              isSpeaking={state.currentSpeaker === 'senior'}
              liveLines={seniorLiveLines}
              thoughts={showThoughts ? state.seniorState.scam_analysis : ''}
              showThoughts={showThoughts}
              metrics={{
                caller_classification: state.seniorState.caller_classification,
                scam_confidence: state.seniorState.scam_confidence,
                current_tactic: state.seniorState.current_tactic,
              }}
            />
          </div>
        ) : (
          /* Welcome Screen */
          <div className="text-center py-20">
            <div className="text-6xl mb-6">📞</div>
            <h2 className="text-2xl font-semibold text-white mb-4">Ready to Start Demo</h2>
            <p className="text-slate-400 max-w-lg mx-auto mb-6">
              Watch an AI scammer try to deceive an AI senior defender.
              The defender will analyze, classify, and use delay tactics to waste the scammer's time.
            </p>
            <p className="text-slate-500 text-sm">
              {connected ? '🟢 Connected to server' : '🔴 Connecting to server...'}
            </p>
          </div>
        )}

        {/* Conversation Panel */}
        {state.messages.length > 0 && (
          <ConversationPanel messages={state.messages} />
        )}
      </div>
    </div>
  );
}

export default App;
