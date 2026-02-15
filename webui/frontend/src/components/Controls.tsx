import { SimulationStatus } from '../types';

interface ControlsProps {
  status: SimulationStatus;
  connected: boolean;
  callerType: 'scammer' | 'family';
  setCallerType: (callerType: 'scammer' | 'family') => void;
  maxTurns: number;
  setMaxTurns: (turns: number) => void;
  enableVoice: boolean;
  setEnableVoice: (enable: boolean) => void;
  showThoughts: boolean;
  setShowThoughts: (show: boolean) => void;
  onStart: () => void;
  onStop: () => void;
  onReset: () => void;
}

export function Controls({
  status,
  connected,
  callerType,
  setCallerType,
  maxTurns,
  setMaxTurns,
  enableVoice,
  setEnableVoice,
  showThoughts,
  setShowThoughts,
  onStart,
  onStop,
  onReset,
}: ControlsProps) {
  const isIdle = status === 'idle';
  const isRunning = status === 'running';
  
  return (
    <div className="flex flex-wrap items-center justify-center gap-4 mb-6 p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
      {/* Mode */}
      <div className="flex items-center gap-2">
        <label className="text-slate-400 text-sm">Mode:</label>
        <select
          value={callerType}
          onChange={(e) => setCallerType(e.target.value as 'scammer' | 'family')}
          disabled={!isIdle}
          className="bg-slate-700 text-white px-3 py-1.5 rounded-lg border border-slate-600 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <option value="scammer">🔴 Scammer Call</option>
          <option value="family">💚 Family Call</option>
        </select>
      </div>
      {/* Max Turns */}
      <div className="flex items-center gap-2">
        <label className="text-slate-400 text-sm">Max Turns:</label>
        <select
          value={maxTurns}
          onChange={(e) => setMaxTurns(Number(e.target.value))}
          disabled={!isIdle}
          className="bg-slate-700 text-white px-3 py-1.5 rounded-lg border border-slate-600 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <option value={5}>5</option>
          <option value={10}>10</option>
          <option value={15}>15</option>
          <option value={20}>20</option>
          <option value={30}>30</option>
        </select>
      </div>

      {/* Voice Toggle */}
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={enableVoice}
          onChange={(e) => setEnableVoice(e.target.checked)}
          disabled={!isIdle}
          className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-slate-800 disabled:opacity-50"
        />
        <span className="text-slate-400 text-sm">🔊 Voice</span>
      </label>

      {/* Thoughts Toggle */}
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={showThoughts}
          onChange={(e) => setShowThoughts(e.target.checked)}
          className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-slate-800"
        />
        <span className="text-slate-400 text-sm">🧠 Thoughts</span>
      </label>

      {/* Divider */}
      <div className="w-px h-6 bg-slate-700 hidden sm:block" />

      {/* Action Buttons */}
      {isIdle && (
        <button
          onClick={onStart}
          disabled={!connected}
          className="px-6 py-2 bg-gradient-to-r from-green-600 to-green-500 hover:from-green-500 hover:to-green-400 text-white font-medium rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-green-500/20"
        >
          ▶️ Start Call
        </button>
      )}

      {isRunning && (
        <button
          onClick={onStop}
          className="px-6 py-2 bg-gradient-to-r from-red-600 to-red-500 hover:from-red-500 hover:to-red-400 text-white font-medium rounded-lg transition-all shadow-lg shadow-red-500/20"
        >
          ⏹️ Stop
        </button>
      )}

      {status === 'completed' && (
        <button
          onClick={onReset}
          className="px-6 py-2 bg-gradient-to-r from-slate-600 to-slate-500 hover:from-slate-500 hover:to-slate-400 text-white font-medium rounded-lg transition-all"
        >
          🔄 Reset
        </button>
      )}
    </div>
  );
}
