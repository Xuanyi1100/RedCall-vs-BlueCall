import { useState, useRef, useEffect } from 'react';
import { Message } from '../types';

interface ConversationPanelProps {
  messages: Message[];
}

export function ConversationPanel({ messages }: ConversationPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current && isExpanded) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isExpanded]);

  return (
    <div className="rounded-xl bg-slate-800/50 border border-slate-700/50 overflow-hidden">
      {/* Header - Clickable */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">📜</span>
          <span className="text-slate-300 font-medium">
            Conversation Transcript
          </span>
          <span className="text-slate-500 text-sm">
            ({messages.length} messages)
          </span>
        </div>
        <span className={`text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div
          ref={scrollRef}
          className="max-h-96 overflow-y-auto border-t border-slate-700/50"
        >
          {messages.map((msg, idx) => (
            <MessageBubble key={idx} message={msg} />
          ))}
        </div>
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isScammer = message.speaker === 'scammer';
  
  return (
    <div className={`p-4 border-b border-slate-700/30 ${isScammer ? 'bg-red-950/10' : 'bg-blue-950/10'}`}>
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-lg flex-shrink-0 ${
          isScammer ? 'bg-red-500/20' : 'bg-blue-500/20'
        }`}>
          {isScammer ? '🎭' : '👵'}
        </div>
        
        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`font-medium text-sm ${isScammer ? 'text-red-400' : 'text-blue-400'}`}>
              {isScammer ? 'Scammer' : 'Senior'}
            </span>
            <span className="text-slate-600 text-xs">
              Turn {message.turn}
            </span>
          </div>
          <p className="text-slate-300 text-sm leading-relaxed">
            {message.message}
          </p>
        </div>
      </div>
    </div>
  );
}
