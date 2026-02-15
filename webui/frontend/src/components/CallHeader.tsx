import { SimulationStatus } from '../types';

interface CallHeaderProps {
  status: SimulationStatus;
  turn: number;
  maxTurns: number;
  elapsedSeconds: number;
  endReason: string | null;
}

const END_REASON_MESSAGES: Record<string, { icon: string; text: string; color: string }> = {
  scammer_gave_up: { icon: '✅', text: 'Scammer Hung Up!', color: 'text-green-400' },
  max_turns: { icon: '⏱️', text: 'Max Turns Reached', color: 'text-yellow-400' },
  persuasion_succeeded: { icon: '⚠️', text: 'Scam Succeeded', color: 'text-red-400' },
  sensitive_info_extracted: { icon: '⚠️', text: 'Info Extracted', color: 'text-red-400' },
  sensitive_info_leaked: { icon: '⚠️', text: 'Info Leaked', color: 'text-red-400' },
  handoff: { icon: '📱', text: 'Call Handed Off', color: 'text-blue-400' },
  stopped: { icon: '⏹️', text: 'Simulation Stopped', color: 'text-slate-400' },
};

export function CallHeader({ status, turn, maxTurns, elapsedSeconds, endReason }: CallHeaderProps) {
  if (status === 'idle') return null;
  
  const timeSeconds = elapsedSeconds;
  const minutes = Math.floor(timeSeconds / 60);
  const seconds = timeSeconds % 60;
  const timeStr = `${minutes}:${seconds.toString().padStart(2, '0')}`;

  if (status === 'completed' && endReason) {
    const reason = END_REASON_MESSAGES[endReason] || { icon: '📵', text: 'Call Ended', color: 'text-slate-400' };
    
    return (
      <div className="flex justify-center mb-6">
        <div className="px-6 py-3 rounded-full bg-slate-800/80 border border-slate-700 flex items-center gap-3">
          <span className="text-xl">{reason.icon}</span>
          <span className={`font-medium ${reason.color}`}>{reason.text}</span>
          <span className="text-slate-500">•</span>
          <span className="text-slate-400">{turn} turns</span>
          <span className="text-slate-500">•</span>
          <span className="text-slate-400">{timeStr}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-center mb-6">
      <div className="px-6 py-3 rounded-full bg-green-500/10 border border-green-500/30 flex items-center gap-3">
        <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
        <span className="text-green-400 font-medium">Call in Progress</span>
        <span className="text-slate-500">•</span>
        <span className="text-slate-400">Turn {turn}/{maxTurns}</span>
        <span className="text-slate-500">•</span>
        <span className="text-slate-400">{timeStr}</span>
      </div>
    </div>
  );
}
