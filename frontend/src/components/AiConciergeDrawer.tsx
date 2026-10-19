import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles,
  Send,
  X,
  Bot,
  RotateCcw,
  ChevronRight,
  TrendingDown
} from 'lucide-react';
import type { ChatMessage, ChatResponseData } from '../types';

interface AiConciergeDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  tripId?: number | string;
  onSendMessage: (msg: string) => Promise<ChatResponseData | null>;
  messages: ChatMessage[];
  onRefreshTrip: () => void;
  onRevertVersion?: (v: number) => void;
  currentVersion: number;
}

const SUGGESTED_PROMPTS = [
  'Make Day 2 cheaper',
  'Add a beach visit',
  'Remove museums',
  'Why was Fort Aguada selected for Day 1?',
  'What should I pack for this trip?',
  'Find quieter cultural sights',
];

export const AiConciergeDrawer: React.FC<AiConciergeDrawerProps> = ({
  isOpen,
  onClose,
  onSendMessage,
  messages,
  onRefreshTrip,
  onRevertVersion,
  currentVersion,
}) => {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [recentDiff, setRecentDiff] = useState<any>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (textToSend?: string) => {
    const text = textToSend || input;
    if (!text.trim() || loading) return;

    setInput('');
    setLoading(true);
    setRecentDiff(null);

    try {
      const res = await onSendMessage(text);
      if (res && res.diff) {
        setRecentDiff(res.diff);
        onRefreshTrip();
      }
    } catch (err) {
      console.error('Chat error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 lg:hidden"
          />

          {/* Drawer Container */}
          <motion.div
            initial={{ x: '100%', opacity: 0.5 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0.5 }}
            transition={{ type: 'spring', damping: 28, stiffness: 280 }}
            className="fixed top-0 right-0 bottom-0 w-full sm:w-[460px] liquid-glass-dark text-white shadow-2xl z-50 flex flex-col border-l border-white/10 backdrop-blur-2xl"
          >
            {/* Header */}
            <div className="p-4 sm:p-5 border-b border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-[#905831] flex items-center justify-center shadow-md">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-white flex items-center gap-1.5">
                    <span>Wandor Concierge</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  </h3>
                  <p className="text-[10px] text-neutral-400">
                    Live dynamic reasoning & modification agent
                  </p>
                </div>
              </div>

              <button
                onClick={onClose}
                className="p-1.5 rounded-full hover:bg-white/10 text-neutral-400 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* ChangeSet / Diff Card if a modification just occurred */}
            {recentDiff && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mx-4 mt-3 p-3.5 rounded-2xl bg-amber-950/30 border border-amber-600/30 text-xs shadow-lg"
              >
                <div className="flex items-center justify-between font-bold text-amber-300 mb-1.5">
                  <span className="flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5" />
                    Itinerary Updated (v{currentVersion})
                  </span>
                  {onRevertVersion && currentVersion > 1 && (
                    <button
                      onClick={() => {
                        onRevertVersion(currentVersion - 1);
                        setRecentDiff(null);
                      }}
                      className="px-2 py-0.5 rounded-lg bg-white/10 hover:bg-white/20 text-[10px] text-neutral-300 flex items-center gap-1 transition-colors"
                    >
                      <RotateCcw className="w-3 h-3" />
                      Undo
                    </button>
                  )}
                </div>
                <div className="text-[11px] text-neutral-300 leading-snug">
                  {recentDiff.summary || 'Applied optimal modifications to the itinerary.'}
                </div>
                {recentDiff.delta && (
                  <div className="mt-2 flex items-center gap-3 text-[10px] text-neutral-400">
                    {recentDiff.delta.cost !== undefined && (
                      <span className="flex items-center gap-1 text-emerald-400 font-semibold">
                        <TrendingDown className="w-3 h-3" />
                        Cost delta: ₹{recentDiff.delta.cost}
                      </span>
                    )}
                  </div>
                )}
              </motion.div>
            )}

            {/* Chat Message Stream */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
              {messages.length === 0 && (
                <div className="text-center py-8">
                  <div className="w-12 h-12 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-3 text-[#905831]">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <h4 className="font-semibold text-sm text-neutral-200 mb-1">
                    Ask questions or ask to modify your trip
                  </h4>
                  <p className="text-xs text-neutral-400 max-w-xs mx-auto mb-5">
                    I can explain why specific sights were chosen, lower your day-wise expenses, or adapt to your preferences.
                  </p>

                  <div className="space-y-2 max-w-xs mx-auto text-left">
                    <div className="text-[10px] uppercase font-bold text-neutral-500 tracking-wider mb-1">
                      Suggested requests:
                    </div>
                    {SUGGESTED_PROMPTS.map((prompt, i) => (
                      <button
                        key={i}
                        onClick={() => handleSend(prompt)}
                        className="w-full text-left p-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-neutral-300 hover:text-white transition-all flex items-center justify-between group"
                      >
                        <span className="truncate">{prompt}</span>
                        <ChevronRight className="w-3 h-3 text-neutral-500 group-hover:text-white" />
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map(msg => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                >
                  <div className="flex items-center gap-1.5 mb-1 px-1">
                    <span className="text-[10px] font-semibold text-neutral-400">
                      {msg.role === 'user' ? 'You' : 'Wandor Concierge'}
                    </span>
                    {msg.intent === 'modify' && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        Modified
                      </span>
                    )}
                  </div>

                  <div
                    className={`p-3.5 rounded-2xl max-w-[85%] text-xs leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-[#905831] text-white rounded-tr-sm shadow-md'
                        : 'bg-white/10 border border-white/10 text-neutral-200 rounded-tl-sm shadow-md'
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex items-center gap-2 p-3 rounded-2xl bg-white/5 border border-white/10 max-w-[60%]">
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
                    className="w-4 h-4 border-2 border-[#905831] border-t-transparent rounded-full"
                  />
                  <span className="text-xs text-neutral-400">Reasoning...</span>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            {/* Quick Chips above Input */}
            <div className="px-4 py-2 flex items-center gap-1.5 overflow-x-auto no-scrollbar border-t border-white/5">
              {['Make Day 2 cheaper', 'Add a beach', 'Why Fort Aguada?'].map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSend(q)}
                  className="whitespace-nowrap px-2.5 py-1 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-[10px] text-neutral-300 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>

            {/* Input Composer */}
            <form
              onSubmit={e => {
                e.preventDefault();
                handleSend();
              }}
              className="p-4 border-t border-white/10 bg-black/30"
            >
              <div className="relative flex items-center">
                <input
                  type="text"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  placeholder="Ask a question or request a change..."
                  className="w-full rounded-2xl bg-white/10 border border-white/20 pl-4 pr-12 py-3 text-xs text-white placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-[#905831]/50 focus:bg-white/15 transition-all"
                />
                <button
                  type="submit"
                  disabled={!input.trim() || loading}
                  className="absolute right-2 p-2 rounded-xl bg-[#905831] text-white disabled:opacity-40 hover:bg-[#a6683c] transition-colors shadow-sm"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </div>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};
