import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Share2, Copy, Check, ExternalLink, ShieldCheck, Trash2 } from 'lucide-react';
import { api } from '../services/api';

interface ShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  tripId: number | string;
}

export const ShareModal: React.FC<ShareModalProps> = ({ isOpen, onClose, tripId }) => {
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [shareUrl, setShareUrl] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleGenerateShare = async () => {
    setLoading(true);
    try {
      const res = await api.shareTrip(tripId, 30);
      const url = `${window.location.origin}/s/${res.token}`;
      setShareUrl(url);
    } catch (err) {
      console.error('Failed to create share link:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!shareUrl) return;
    navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRevoke = async () => {
    setLoading(true);
    try {
      await api.revokeShare(tripId);
      setShareUrl(null);
    } catch (err) {
      console.error('Failed to revoke share link:', err);
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

          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-2xl bg-[#905831]/30 border border-[#905831]/50 flex items-center justify-center text-amber-300">
              <Share2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-white">Share Itinerary</h3>
              <p className="text-xs text-neutral-400">
                Generate a public, read-only link for friends or travel companions
              </p>
            </div>
          </div>

          <div className="p-3.5 rounded-2xl bg-white/5 border border-white/10 text-xs text-neutral-300 mb-5 flex items-start gap-2.5">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <span>
              Recipients can explore the day-by-day stops, routes, and timings. Budget limits and private expenses remain hidden.
            </span>
          </div>

          {!shareUrl ? (
            <button
              onClick={handleGenerateShare}
              disabled={loading}
              className="w-full py-3 rounded-2xl bg-[#905831] hover:bg-[#a6683c] text-white font-bold text-xs tracking-wide transition-all shadow-lg flex items-center justify-center gap-2"
            >
              {loading ? (
                <span>Generating secure link...</span>
              ) : (
                <>
                  <Share2 className="w-4 h-4" />
                  <span>Create Public Read-Only Link</span>
                </>
              )}
            </button>
          ) : (
            <div className="space-y-3">
              <div className="p-2.5 rounded-2xl bg-black/50 border border-white/20 flex items-center justify-between gap-2">
                <input
                  type="text"
                  readOnly
                  value={shareUrl}
                  className="bg-transparent text-xs text-neutral-200 font-mono focus:outline-none w-full truncate"
                />
                <button
                  onClick={handleCopy}
                  className="p-2 rounded-xl bg-white/10 hover:bg-white/20 text-white shrink-0 transition-colors"
                  title="Copy link"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>

              <div className="flex items-center justify-between pt-2">
                <a
                  href={shareUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-amber-400 hover:underline flex items-center gap-1 font-medium"
                >
                  <span>Open shared view</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>

                <button
                  onClick={handleRevoke}
                  disabled={loading}
                  className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1 font-medium"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Revoke link</span>
                </button>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
