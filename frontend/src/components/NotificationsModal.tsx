import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Bell, CloudRain, Sparkles, AlertTriangle, Check } from 'lucide-react';
import type { NotificationItem } from '../types';

interface NotificationsModalProps {
  isOpen: boolean;
  onClose: () => void;
  notifications: NotificationItem[];
  onMarkRead: (id: number | string) => void;
}

export const NotificationsModal: React.FC<NotificationsModalProps> = ({
  isOpen,
  onClose,
  notifications,
  onMarkRead,
}) => {
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-md">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 15 }}
          className="w-full max-w-lg liquid-glass-dark rounded-3xl p-6 text-white border border-white/10 shadow-2xl relative overflow-hidden"
        >
          <button
            onClick={onClose}
            className="absolute top-5 right-5 p-1.5 rounded-full hover:bg-white/10 text-neutral-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-2.5 mb-5">
            <div className="w-9 h-9 rounded-2xl bg-[#905831]/30 border border-[#905831]/50 flex items-center justify-center text-amber-300">
              <Bell className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-base text-white">Travel Notifications</h3>
              <p className="text-[11px] text-neutral-400">
                Weather alerts, condition replans & itinerary version updates
              </p>
            </div>
          </div>

          <div className="max-h-[380px] overflow-y-auto space-y-2.5 pr-1">
            {notifications.length === 0 ? (
              <div className="py-12 text-center text-neutral-400">
                <Bell className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-xs">No notifications right now.</p>
              </div>
            ) : (
              notifications.map(item => (
                <div
                  key={item.id}
                  className={`p-3.5 rounded-2xl border transition-all ${
                    item.read
                      ? 'bg-white/5 border-white/5 opacity-70'
                      : 'bg-white/10 border-white/20 shadow-md'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2.5">
                      <div className="mt-0.5">
                        {item.type.includes('weather') ? (
                          <CloudRain className="w-4 h-4 text-sky-400" />
                        ) : item.severity === 'warning' ? (
                          <AlertTriangle className="w-4 h-4 text-amber-400" />
                        ) : (
                          <Sparkles className="w-4 h-4 text-[#905831]" />
                        )}
                      </div>
                      <div>
                        <div className="text-xs font-bold text-white flex items-center gap-2">
                          <span>{item.title}</span>
                          {!item.read && (
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                          )}
                        </div>
                        <p className="text-[11px] text-neutral-300 mt-0.5 leading-relaxed">
                          {item.body}
                        </p>
                        <div className="text-[9px] text-neutral-400 mt-1">
                          {new Date(item.created_at).toLocaleString()}
                        </div>
                      </div>
                    </div>

                    {!item.read && (
                      <button
                        onClick={() => onMarkRead(item.id)}
                        className="p-1 rounded-lg hover:bg-white/10 text-neutral-400 hover:text-white transition-colors shrink-0"
                        title="Mark as read"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
