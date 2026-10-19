import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, IndianRupee, Receipt } from 'lucide-react';
import { api } from '../services/api';
import type { Expense, ItineraryDay } from '../types';

interface LogExpenseModalProps {
  isOpen: boolean;
  onClose: () => void;
  tripId: number | string;
  days: ItineraryDay[];
  onExpenseAdded: (expense: Expense) => void;
}

const CATEGORIES = [
  { id: 'food', label: 'Food & Dining' },
  { id: 'accommodation', label: 'Accommodation' },
  { id: 'transport', label: 'Transport / Cabs' },
  { id: 'activities', label: 'Activities & Tickets' },
  { id: 'misc', label: 'Miscellaneous' },
];

export const LogExpenseModal: React.FC<LogExpenseModalProps> = ({
  isOpen,
  onClose,
  tripId,
  days,
  onExpenseAdded,
}) => {
  const [amount, setAmount] = useState<number | ''>('');
  const [category, setCategory] = useState<string>('food');
  const [dayId, setDayId] = useState<string>(days[0]?.id || 'day_1');
  const [note, setNote] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!amount || amount <= 0) return;

    setLoading(true);
    setError(null);

    try {
      const newExp = await api.logExpense(tripId, {
        amount: Number(amount),
        category,
        day_id: dayId,
        note: note.trim() || undefined,
      });

      onExpenseAdded(newExp);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to log expense');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-md">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 15 }}
          className="w-full max-w-md liquid-glass-dark rounded-3xl p-6 sm:p-7 text-white border border-white/10 shadow-2xl relative overflow-hidden"
        >
          <button
            onClick={onClose}
            className="absolute top-5 right-5 p-1.5 rounded-full hover:bg-white/10 text-neutral-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-2.5 mb-5">
            <div className="w-9 h-9 rounded-2xl bg-[#905831]/30 border border-[#905831]/50 flex items-center justify-center text-amber-300">
              <Receipt className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-base text-white">Log Travel Expense</h3>
              <p className="text-[11px] text-neutral-400">
                Track actual on-ground spending vs planned budget
              </p>
            </div>
          </div>

          {error && (
            <div className="mb-3 p-2.5 rounded-xl bg-red-950/40 border border-red-500/30 text-xs text-red-300">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3.5">
            <div>
              <label className="block text-[10px] font-bold text-neutral-400 uppercase tracking-wider mb-1">
                Amount (INR ₹)
              </label>
              <div className="relative flex items-center">
                <IndianRupee className="w-4 h-4 text-emerald-400 absolute left-3.5" />
                <input
                  type="number"
                  required
                  min={1}
                  value={amount}
                  onChange={e => setAmount(Number(e.target.value))}
                  placeholder="e.g. 850"
                  className="w-full rounded-2xl bg-white/5 border border-white/10 pl-10 pr-4 py-2.5 text-xs text-white placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-[#905831]/60"
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-bold text-neutral-400 uppercase tracking-wider mb-1">
                Category
              </label>
              <select
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="w-full rounded-2xl bg-neutral-900 border border-white/10 px-3 py-2.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-[#905831]/60 cursor-pointer"
              >
                {CATEGORIES.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-bold text-neutral-400 uppercase tracking-wider mb-1">
                Trip Day
              </label>
              <select
                value={dayId}
                onChange={e => setDayId(e.target.value)}
                className="w-full rounded-2xl bg-neutral-900 border border-white/10 px-3 py-2.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-[#905831]/60 cursor-pointer"
              >
                {days.map(d => (
                  <option key={d.id} value={d.id}>
                    Day {d.day_number} ({d.date}) — {d.theme}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-bold text-neutral-400 uppercase tracking-wider mb-1">
                Note / Description (Optional)
              </label>
              <input
                type="text"
                value={note}
                onChange={e => setNote(e.target.value)}
                placeholder="e.g. Kingfish thali & kokum juice at Vinayak"
                className="w-full rounded-2xl bg-white/5 border border-white/10 px-3.5 py-2.5 text-xs text-white placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-[#905831]/60"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !amount}
              className="w-full py-3 rounded-2xl bg-[#905831] hover:bg-[#a6683c] text-white text-xs font-bold tracking-wide transition-all shadow-lg flex items-center justify-center gap-2 mt-4 disabled:opacity-40"
            >
              {loading ? <span>Recording expense...</span> : <span>Save Expense</span>}
            </button>
          </form>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
