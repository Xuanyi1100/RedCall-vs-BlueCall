import { LiveCaption } from '../types';

interface LiveTranscriptProps {
  captions: LiveCaption[];
  currentSpeaker: 'scammer' | 'senior' | null;
}

export function LiveTranscript({ captions, currentSpeaker }: LiveTranscriptProps) {
  const visible = captions.slice(-4);

  return (
    <div className="mb-6 rounded-xl bg-black/40 border border-slate-700/60 overflow-hidden">
      <div className="px-4 py-2 border-b border-slate-700/50 flex items-center justify-between">
        <div className="text-xs tracking-wide text-slate-400 uppercase">Live Transcript (CC)</div>
        <div className="text-xs text-slate-500">
          {currentSpeaker === 'scammer' && <span className="text-red-400">Scammer speaking...</span>}
          {currentSpeaker === 'senior' && <span className="text-blue-400">Senior speaking...</span>}
          {!currentSpeaker && <span>Waiting...</span>}
        </div>
      </div>

      <div className="p-4 min-h-[124px] flex flex-col gap-2">
        {visible.length === 0 && (
          <div className="text-slate-500 text-sm italic">Subtitle lines will appear here sentence by sentence.</div>
        )}

        {visible.map((caption, idx) => {
          const isLatest = idx === visible.length - 1;
          const isScammer = caption.speaker === 'scammer';
          return (
            <div
              key={caption.id}
              className={`caption-pop rounded-lg px-3 py-2 ${
                isScammer ? 'bg-red-950/30 border border-red-700/30' : 'bg-blue-950/30 border border-blue-700/30'
              } ${isLatest ? 'opacity-100' : 'opacity-70'}`}
            >
              <span className={`text-xs font-semibold uppercase mr-2 ${isScammer ? 'text-red-300' : 'text-blue-300'}`}>
                {isScammer ? 'Scammer' : 'Senior'}
              </span>
              <span className="text-sm text-slate-100 leading-relaxed">{caption.sentence}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
