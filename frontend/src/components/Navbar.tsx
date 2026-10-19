import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Compass, LogOut, Bell, Sparkles, MapPin, CheckCircle, Shield } from 'lucide-react';
import type { User, NotificationItem, TripSummary } from '../types';

interface NavbarProps {
  user: User | null;
  trips: TripSummary[];
  notifications: NotificationItem[];
  currentTripId: number | string | null;
  onSelectTrip: (id: number | string) => void;
  onOpenAuth: (mode: 'login' | 'register' | 'demo') => void;
  onLogout: () => void;
  onOpenPlan: () => void;
  onOpenPricing: () => void;
  onOpenFaq: () => void;
  onOpenNotifications: () => void;
  onGoHome: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  trips,
  notifications,
  currentTripId,
  onSelectTrip,
  onOpenAuth,
  onLogout,
  onOpenPlan,
  onOpenPricing,
  onOpenFaq,
  onOpenNotifications,
  onGoHome,
}) => {
  const [showTripsMenu, setShowTripsMenu] = useState(false);
  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="fixed top-0 left-0 right-0 z-50 px-4 md:px-8 py-4 transition-all duration-300"
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand Logo */}
        <button
          onClick={onGoHome}
          className="group flex items-center gap-2.5 focus:outline-none"
          title="Wandor Home"
        >
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-amber-500 to-orange-600 text-white flex items-center justify-center shadow-lg group-hover:scale-105 transition-transform duration-300">
            <Compass className="w-5 h-5 text-white animate-spin-slow group-hover:rotate-45 transition-transform duration-500" />
          </div>
          <span className="font-brand text-2xl tracking-wider text-[#1a1a1a] font-bold select-none group-hover:opacity-80 transition-opacity">
            wandor
          </span>
        </button>

        {/* Center Navigation Links */}
        <nav className="hidden md:flex items-center gap-1 px-2.5 py-1.5 rounded-full liquid-glass-dark border border-white/10 text-xs md:text-sm font-medium text-neutral-300 shadow-lg">
          <button
            onClick={onGoHome}
            className="px-3.5 py-1.5 rounded-full hover:text-white hover:bg-white/10 transition-colors"
          >
            Discover
          </button>
          <button
            onClick={onOpenPricing}
            className="px-3.5 py-1.5 rounded-full hover:text-white hover:bg-white/10 transition-colors"
          >
            Pricing
          </button>
          <button
            onClick={onOpenFaq}
            className="px-3.5 py-1.5 rounded-full hover:text-white hover:bg-white/10 transition-colors"
          >
            FAQs
          </button>

          {/* User's Trips dropdown if authenticated */}
          {user && trips.length > 0 && (
            <div className="relative">
              <button
                onClick={() => setShowTripsMenu(!showTripsMenu)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/10 text-white hover:bg-white/15 transition-colors font-semibold"
              >
                <MapPin className="w-3.5 h-3.5 text-amber-400" />
                <span>My Trips ({trips.length})</span>
              </button>

              <AnimatePresence>
                {showTripsMenu && (
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    className="absolute top-full left-0 mt-2 w-64 liquid-glass-dark text-white rounded-2xl p-2 shadow-2xl z-50"
                  >
                    <div className="px-3 py-2 text-xs font-semibold text-neutral-400 uppercase tracking-wider border-b border-white/10">
                      Saved Itineraries
                    </div>
                    <div className="max-h-56 overflow-y-auto py-1">
                      {trips.map(trip => (
                        <button
                          key={trip.id}
                          onClick={() => {
                            onSelectTrip(trip.id);
                            setShowTripsMenu(false);
                          }}
                          className={`w-full text-left px-3 py-2.5 rounded-xl text-xs flex items-center justify-between transition-colors ${
                            currentTripId === trip.id
                              ? 'bg-[#905831] text-white font-medium'
                              : 'hover:bg-white/10 text-neutral-200'
                          }`}
                        >
                          <div>
                            <div className="font-semibold">{trip.title}</div>
                            <div className="text-[10px] opacity-70">
                              {trip.destination_name} • {trip.num_days} days • v{trip.current_version}
                            </div>
                          </div>
                          {currentTripId === trip.id && <CheckCircle className="w-3.5 h-3.5 text-white" />}
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </nav>

        {/* Right Actions */}
        {/* Right Actions */}
        <div className="flex items-center gap-2.5">
          {user ? (
            <>
              {/* Notifications Bell */}
              <button
                onClick={onOpenNotifications}
                className="relative p-2.5 rounded-full liquid-glass-dark border border-white/10 text-neutral-300 hover:text-white hover:bg-white/10 transition-all shadow-md"
                title="Notifications"
              >
                <Bell className="w-4 h-4" />
                {unreadCount > 0 && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 text-white text-[10px] font-bold flex items-center justify-center animate-pulse shadow-md">
                    {unreadCount}
                  </span>
                )}
              </button>

              {/* User Chip */}
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full liquid-glass-dark border border-white/10 text-xs font-medium text-white shadow-md">
                <div className="w-6 h-6 rounded-full bg-gradient-to-br from-amber-500 to-orange-600 text-white flex items-center justify-center font-bold text-xs shadow-inner">
                  {user.display_name.charAt(0).toUpperCase()}
                </div>
                <span className="max-w-[120px] truncate">{user.display_name}</span>
              </div>

              {/* Logout Button */}
              <button
                onClick={onLogout}
                className="p-2.5 rounded-full liquid-glass-dark border border-white/10 text-neutral-400 hover:text-rose-400 hover:bg-white/10 transition-colors shadow-md"
                title="Sign Out"
              >
                <LogOut className="w-4 h-4" />
              </button>

              {/* Plan My Trip Button */}
              <button
                onClick={onOpenPlan}
                className="flex items-center gap-1.5 px-4 md:px-5 py-2 rounded-full bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-white text-xs md:text-sm font-semibold shadow-lg shadow-orange-500/25 transition-all duration-300 hover:scale-[1.02]"
              >
                <Sparkles className="w-3.5 h-3.5 text-amber-200" />
                <span>Plan My Trip</span>
              </button>
            </>
          ) : (
            <>
              {/* Quick Demo Login Button */}
              <button
                onClick={() => onOpenAuth('demo')}
                className="hidden sm:flex items-center gap-1.5 px-3.5 py-1.5 rounded-full liquid-glass-dark border border-emerald-500/30 text-xs font-medium text-emerald-400 hover:bg-white/10 transition-colors shadow-md"
                title="Explore with pre-seeded demo user"
              >
                <Shield className="w-3.5 h-3.5 text-emerald-400" />
                <span>Try Demo</span>
              </button>

              {/* Login Button */}
              <button
                onClick={() => onOpenAuth('login')}
                className="px-4 py-2 rounded-full liquid-glass-dark border border-white/10 text-xs md:text-sm font-medium text-white hover:bg-white/10 transition-colors shadow-md"
              >
                Login
              </button>

              {/* Plan My Trip CTA */}
              <button
                onClick={onOpenPlan}
                className="flex items-center gap-1.5 px-4 md:px-5 py-2 rounded-full bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-white text-xs md:text-sm font-semibold shadow-lg shadow-orange-500/25 transition-all duration-300 hover:scale-[1.02]"
              >
                <Sparkles className="w-3.5 h-3.5 text-amber-200" />
                <span>Plan My Trip</span>
              </button>
            </>
          )}
        </div>
      </div>
    </motion.header>
  );
};
