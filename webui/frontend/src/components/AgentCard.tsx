import { ProgressBar } from './ProgressBar';

interface ScammerMetrics {
  persuasion_stage: string;
  persuasion_level: number;
  patience: number;
}

function FamilyMetricsPanel({ metrics }: { metrics: FamilyMetrics }) {
  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <span className="text-slate-500 text-sm">Caller</span>
        <span className="text-green-300 font-medium">{metrics.caller_name || 'Family Member'}</span>
      </div>
      <div className="flex justify-between items-center">
        <span className="text-slate-500 text-sm">Relationship</span>
        <span className="text-white font-medium capitalize">{metrics.relationship || 'relative'}</span>
      </div>
      <div className="flex justify-between items-center gap-3">
        <span className="text-slate-500 text-sm">Call Reason</span>
        <span className="text-white/90 text-sm text-right">{metrics.call_reason || 'Checking in'}</span>
      </div>
      <div className="flex justify-between items-center">
        <span className="text-slate-500 text-sm">Recognized by Senior</span>
        <span className={`px-2 py-0.5 rounded text-xs font-semibold border ${
          metrics.recognized
            ? 'text-green-300 border-green-500/40 bg-green-500/10'
            : 'text-yellow-300 border-yellow-500/40 bg-yellow-500/10'
        }`}>
          {metrics.recognized ? 'YES' : 'NOT YET'}
        </span>
      </div>
    </div>
  );
}

interface SeniorMetrics {
  caller_classification: string;
  scam_confidence: number;
  current_tactic: string;
}

interface FamilyMetrics {
  recognized: boolean;
  caller_name: string;
  relationship: string;
  call_reason: string;
}

interface AgentCardProps {
  type: 'scammer' | 'family' | 'senior';
  isSpeaking: boolean;
  liveLines: string[];
  thoughts: string;
  showThoughts: boolean;
  metrics: ScammerMetrics | SeniorMetrics | FamilyMetrics;
}

const STAGE_NAMES: Record<string, string> = {
  building_trust: 'Building Trust',
  fake_problem: 'Fake Problem',
  pressure: 'Applying Pressure',
  stealing_info: 'Stealing Info',
  demand_payment: 'Demanding Payment',
};

const STAGE_ORDER = ['building_trust', 'fake_problem', 'pressure', 'stealing_info', 'demand_payment'];

const TACTIC_NAMES: Record<string, string> = {
  ASK_REPEAT: 'Asking to Repeat',
  CLARIFY: 'Clarifying',
  STORY_TIME: 'Telling Stories',
  HEARING_ISSUES: 'Hearing Issues',
  BAD_CONNECTION: 'Bad Connection',
  BATHROOM_BREAK: 'Bathroom Break',
  FORGOT_AGAIN: 'Forgetting',
  VERIFY_IDENTITY: 'Verifying Identity',
  FRIENDLY_CHAT: 'Friendly Chat',
  GATHER_INFO: 'Gathering Info',
};

function isScammerMetrics(metrics: ScammerMetrics | SeniorMetrics | FamilyMetrics): metrics is ScammerMetrics {
  return 'persuasion_stage' in metrics;
}

function isFamilyMetrics(metrics: ScammerMetrics | SeniorMetrics | FamilyMetrics): metrics is FamilyMetrics {
  return 'recognized' in metrics && 'caller_name' in metrics;
}

function isSeniorMetrics(metrics: ScammerMetrics | SeniorMetrics | FamilyMetrics): metrics is SeniorMetrics {
  return 'caller_classification' in metrics && 'scam_confidence' in metrics;
}

export function AgentCard({ type, isSpeaking, liveLines, thoughts, showThoughts, metrics }: AgentCardProps) {
  const isCaller = type === 'scammer' || type === 'family';
  const isScammer = type === 'scammer';
  const isFamily = type === 'family';
  
  const bgGradient = isScammer
    ? 'from-red-950/50 to-slate-900/50' 
    : isFamily
    ? 'from-green-950/50 to-slate-900/50'
    : 'from-blue-950/50 to-slate-900/50';
  
  const borderColor = isScammer ? 'border-red-500/30' : isFamily ? 'border-green-500/30' : 'border-blue-500/30';
  const accentColor = isScammer ? 'text-red-400' : isFamily ? 'text-green-400' : 'text-blue-400';
  const avatarBg = isScammer
    ? 'bg-gradient-to-br from-red-500 to-red-700' 
    : isFamily
    ? 'bg-gradient-to-br from-green-500 to-green-700'
    : 'bg-gradient-to-br from-blue-500 to-blue-700';

  return (
    <div className={`rounded-2xl bg-gradient-to-br ${bgGradient} border ${borderColor} overflow-hidden`}>
      {/* Header */}
      <div className="p-4 border-b border-white/5">
        <div className="flex items-center gap-4">
          {/* Avatar */}
          <div className={`relative`}>
            <div className={`w-16 h-16 rounded-full ${avatarBg} flex items-center justify-center text-3xl shadow-lg ${isSpeaking ? 'speaking-animation' : ''}`}>
              {isScammer ? '🎭' : isFamily ? '💚' : '👵'}
            </div>
            {isSpeaking && (
              <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-green-500 rounded-full border-2 border-slate-900 flex items-center justify-center">
                <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
              </div>
            )}
          </div>
          
          {/* Name & Role */}
          <div>
            <h2 className={`text-xl font-bold ${accentColor}`}>
              {isScammer ? 'Scammer' : isFamily ? 'Family Caller' : 'Scammers Nightmare'}
            </h2>
            <p className="text-slate-500 text-sm">
              {isScammer ? 'Red Team Attacker' : isFamily ? 'Legitimate Caller' : 'Blue Team AI Agent'}
            </p>
          </div>
        </div>
      </div>

      {/* Speech Bubble */}
      <div className="p-4">
        <div className={`rounded-xl p-4 min-h-[100px] ${
          isScammer
            ? 'bg-red-950/30 border-l-4 border-red-500'
            : isFamily
            ? 'bg-green-950/30 border-l-4 border-green-500'
            : 'bg-blue-950/30 border-l-4 border-blue-500'
        }`}>
          {liveLines.length > 0 ? (
            <div className="flex flex-col gap-2">
              {liveLines.slice(-4).map((line, idx) => (
                <p
                  key={`${idx}-${line}`}
                  className={`caption-pop text-white/90 leading-relaxed ${idx === liveLines.slice(-4).length - 1 ? 'opacity-100' : 'opacity-70'}`}
                >
                  {line}
                </p>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 italic">
              {isSpeaking ? 'Speaking...' : 'Waiting...'}
            </p>
          )}
        </div>

        {/* Thoughts Bubble */}
        {showThoughts && thoughts && (
          <div className="mt-3 p-3 rounded-lg bg-black/30 border border-dashed border-slate-700">
            <p className="text-xs text-slate-500 mb-1">🧠 Inner Thoughts</p>
            <p className="text-slate-400 text-sm italic">{thoughts}</p>
          </div>
        )}
      </div>

      {/* Metrics Panel */}
      <div className="p-4 bg-black/20 border-t border-white/5">
        {isCaller && isScammerMetrics(metrics) ? (
          <ScammerMetricsPanel metrics={metrics} />
        ) : isFamily && isFamilyMetrics(metrics) ? (
          <FamilyMetricsPanel metrics={metrics} />
        ) : isSeniorMetrics(metrics) ? (
          <SeniorMetricsPanel metrics={metrics} />
        ) : null
        }
      </div>
    </div>
  );
}

function ScammerMetricsPanel({ metrics }: { metrics: ScammerMetrics }) {
  const currentStageIndex = STAGE_ORDER.indexOf(metrics.persuasion_stage);
  
  return (
    <div className="space-y-4">
      {/* Phase Indicator */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <span className="text-slate-500 text-sm">Scam Phase</span>
          <span className="text-red-400 font-medium text-sm">
            {STAGE_NAMES[metrics.persuasion_stage] || metrics.persuasion_stage}
          </span>
        </div>
        <div className="flex gap-1">
          {STAGE_ORDER.map((stage, idx) => (
            <div
              key={stage}
              className={`flex-1 h-2 rounded-full ${
                idx < currentStageIndex
                  ? 'bg-green-500'
                  : idx === currentStageIndex
                  ? 'bg-red-500'
                  : 'bg-slate-700'
              }`}
            />
          ))}
        </div>
      </div>

      {/* Persuasion Level */}
      <div>
        <div className="flex justify-between items-center mb-1">
          <span className="text-slate-500 text-sm">Persuasion Level</span>
          <span className="text-white font-medium">{Math.round(metrics.persuasion_level * 100)}%</span>
        </div>
        <ProgressBar value={metrics.persuasion_level} color="red" />
      </div>

      {/* Patience */}
      <div>
        <div className="flex justify-between items-center mb-1">
          <span className="text-slate-500 text-sm">Patience</span>
          <span className="text-white font-medium">{Math.round(metrics.patience * 100)}%</span>
        </div>
        <ProgressBar value={metrics.patience} color="yellow" />
      </div>
    </div>
  );
}

function SeniorMetricsPanel({ metrics }: { metrics: SeniorMetrics }) {
  const classificationColors: Record<string, string> = {
    SCAM: 'bg-red-500/20 text-red-400 border-red-500/50',
    LEGITIMATE: 'bg-green-500/20 text-green-400 border-green-500/50',
    UNCERTAIN: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
  };
  
  const classColor = classificationColors[metrics.caller_classification] || classificationColors.UNCERTAIN;
  const tacticName = TACTIC_NAMES[metrics.current_tactic] || metrics.current_tactic || 'Listening';

  return (
    <div className="space-y-4">
      {/* Classification */}
      <div>
        <div className="flex justify-between items-center">
          <span className="text-slate-500 text-sm">Classification</span>
          <span className={`px-3 py-1 rounded-full text-sm font-medium border ${classColor}`}>
            {metrics.caller_classification === 'SCAM' && '⚠️ '}
            {metrics.caller_classification === 'LEGITIMATE' && '✅ '}
            {metrics.caller_classification === 'UNCERTAIN' && '❓ '}
            {metrics.caller_classification}
          </span>
        </div>
      </div>

      {/* Scam Confidence */}
      <div>
        <div className="flex justify-between items-center mb-1">
          <span className="text-slate-500 text-sm">Scam Confidence</span>
          <span className="text-white font-medium">{Math.round(metrics.scam_confidence * 100)}%</span>
        </div>
        <ProgressBar value={metrics.scam_confidence} color="blue" />
      </div>

      {/* Current Tactic */}
      <div>
        <div className="flex justify-between items-center">
          <span className="text-slate-500 text-sm">Current Tactic</span>
          <span className="px-3 py-1 rounded-lg text-sm bg-blue-500/20 text-blue-400 border border-blue-500/30">
            🎭 {tacticName}
          </span>
        </div>
      </div>
    </div>
  );
}
