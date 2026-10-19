import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Navbar } from './components/Navbar';
import { HeroSection } from './components/HeroSection';
import { TripDashboard } from './components/TripDashboard';
import { AiPlanningOverlay } from './components/AiPlanningOverlay';
import { AiConciergeDrawer } from './components/AiConciergeDrawer';
import { AuthModal } from './components/AuthModal';
import { ShareModal } from './components/ShareModal';
import { NotificationsModal } from './components/NotificationsModal';
import { LogExpenseModal } from './components/LogExpenseModal';
import { PricingModal } from './components/PricingModal';
import { FaqModal } from './components/FaqModal';
import { SharedTripView } from './components/SharedTripView';
import { api } from './services/api';
import type {
  CanonicalItinerary,
  ChatMessage,
  Destination,
  Expense,
  NotificationItem,
  TripAnalytics,
  TripSummary,
  User,
  VersionSummary
} from './types';

export function App() {
  // Check if current route is a public share link `/s/:token`
  const pathParts = window.location.pathname.split('/');
  const isShareRoute = pathParts[1] === 's' && pathParts[2];
  const shareToken = isShareRoute ? pathParts[2] : null;

  // App State
  const [user, setUser] = useState<User | null>(null);
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [trips, setTrips] = useState<TripSummary[]>([]);
  const [currentTripId, setCurrentTripId] = useState<number | string | null>(null);
  const [currentItinerary, setCurrentItinerary] = useState<CanonicalItinerary | null>(null);
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [analytics, setAnalytics] = useState<TripAnalytics | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  // UI Flow & Modals State
  const [planningOpen, setPlanningOpen] = useState(false);
  const [planningDestName, setPlanningDestName] = useState('Goa');
  const [planningTrace, setPlanningTrace] = useState<string[]>([]);
  const [conciergeOpen, setConciergeOpen] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register' | 'demo'>('login');
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [notifModalOpen, setNotifModalOpen] = useState(false);
  const [expenseModalOpen, setExpenseModalOpen] = useState(false);
  const [pricingModalOpen, setPricingModalOpen] = useState(false);
  const [faqModalOpen, setFaqModalOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // Initial Load: Destinations, User & Trips
  useEffect(() => {
    async function init() {
      try {
        const dests = await api.getDestinations();
        setDestinations(dests);
      } catch (err) {
        console.warn('Destinations fetch warning:', err);
      }

      if (api.getToken()) {
        try {
          const me = await api.getMe();
          setUser(me);
          await loadUserTrips();
          await loadNotifications();
        } catch (err) {
          api.logout();
          setUser(null);
        }
      }
    }
    init();
  }, []);

  const loadUserTrips = async () => {
    try {
      const list = await api.getTrips();
      setTrips(list);
      return list;
    } catch (err) {
      console.error('Error loading trips:', err);
      return [];
    }
  };

  const loadNotifications = async () => {
    try {
      const list = await api.getNotifications();
      setNotifications(list);
    } catch (err) {
      console.warn('Error loading notifications:', err);
    }
  };

  const loadTripDetails = async (id: number | string) => {
    try {
      const res = await api.getTrip(id);
      setCurrentTripId(id);
      if (res.itinerary) {
        setCurrentItinerary(res.itinerary);
      }
      // Load versions
      const vList = await api.getVersions(id);
      setVersions(vList);
      // Load expenses
      const expRes = await api.getExpenses(id);
      setExpenses(expRes.expenses);
      // Load analytics
      const analRes = await api.getTripAnalytics(id);
      setAnalytics(analRes);
      // Load chat history
      const msgs = await api.getChatHistory(id);
      setChatMessages(msgs);
    } catch (err) {
      console.error('Error loading trip details:', err);
    }
  };

  // Handle Planning from Hero
  const handleStartPlanning = async (planData: {
    destination_id: string;
    start_date: string;
    end_date: string;
    travelers: { adults: number; children: number };
    budget: number;
    title: string;
    prompt?: string;
    pace: string;
    interests: string[];
  }) => {
    let currentUser = user;
    if (!currentUser) {
      try {
        const authRes = await api.demoLogin();
        currentUser = authRes.user;
        setUser(currentUser);
        showToast('Logged in with demo access for seamless planning.');
      } catch (err) {
        setAuthModalOpen(true);
        return;
      }
    }

    const destObj = destinations.find(d => d.id === planData.destination_id);
    const destName = destObj?.name || 'Destination';
    setPlanningDestName(destName);
    setPlanningOpen(true);
    setPlanningTrace(['Initiating trip configuration...']);

    try {
      // 1. Create Trip in DB
      const createRes = await api.createTrip({
        destination_id: planData.destination_id,
        start_date: planData.start_date,
        end_date: planData.end_date,
        travelers: planData.travelers,
        budget: planData.budget,
        title: planData.title,
        preferences: {
          pace: planData.pace,
          interests: planData.interests,
        },
      });

      const newTripId = createRes.trip_id;

      // 2. Generate Itinerary (calls PlannerAgent & BaselinePlanner fallback)
      setPlanningTrace(prev => [...prev, 'Running AI Planner reasoning and route optimizer...']);
      const genRes = await api.generateItinerary(newTripId);

      setCurrentTripId(newTripId);
      setCurrentItinerary(genRes.itinerary);
      setPlanningTrace(genRes.trace || []);

      // Refresh trips list
      await loadUserTrips();
      await loadTripDetails(newTripId);
      await loadNotifications();

      setTimeout(() => {
        setPlanningOpen(false);
        showToast(`Your personalized ${destName} itinerary is ready!`);
      }, 1000);
    } catch (err: any) {
      console.error('Planning error:', err);
      setPlanningOpen(false);
      showToast(err.message || 'Failed to generate itinerary. Please try again.');
    }
  };

  // Weather Simulation Trigger
  const handleSimulateWeather = async () => {
    if (!currentTripId) return;
    try {
      const res = await api.simulateEvent(currentTripId, {
        type: 'weather',
        day_id: 'day_3',
        severity: 'high',
        detail: 'Heavy monsoon showers with 85% rain forecasted',
      });

      if (res.itinerary) {
        setCurrentItinerary(res.itinerary);
        await loadTripDetails(currentTripId);
        await loadNotifications();
        showToast('Monsoon alert detected! Swapped Day 3 outdoor stop for an indoor museum.');
      }
    } catch (err: any) {
      showToast(err.message || 'Simulation replanning failed.');
    }
  };

  // Condition check
  const handleCheckConditions = async () => {
    if (!currentTripId) return;
    try {
      const res = await api.checkConditions(currentTripId);
      if (res.replan_result) {
        setCurrentItinerary(res.replan_result);
        await loadTripDetails(currentTripId);
        showToast('Itinerary dynamically adapted to real conditions.');
      } else {
        showToast('All conditions normal. Your itinerary is fully optimal.');
      }
      await loadNotifications();
    } catch (err: any) {
      showToast(err.message || 'Conditions check failed.');
    }
  };

  // Revert version
  const handleRevertVersion = async (v: number) => {
    if (!currentTripId) return;
    try {
      const reverted = await api.revertVersion(currentTripId, v);
      setCurrentItinerary(reverted);
      await loadTripDetails(currentTripId);
      await loadNotifications();
      showToast(`Itinerary reverted back to version ${v}.`);
    } catch (err: any) {
      showToast(err.message || 'Revert failed.');
    }
  };

  // Item lock toggle
  const handleToggleLock = async (itemId: string, currentLock: boolean) => {
    if (!currentTripId) return;
    try {
      const res = await api.updateItem(currentTripId, itemId, {
        op: currentLock ? 'UNLOCK_ITEM' : 'LOCK_ITEM',
      });
      setCurrentItinerary(res.itinerary);
      showToast(currentLock ? 'Item unlocked.' : 'Item locked against AI modification.');
    } catch (err: any) {
      showToast(err.message || 'Failed to update item lock.');
    }
  };

  // Alternative apply
  const handleApplyAlternative = async (altId: string) => {
    if (!currentTripId) return;
    try {
      const res = await api.applyAlternative(currentTripId, altId);
      setCurrentItinerary(res.itinerary);
      await loadTripDetails(currentTripId);
      showToast('Alternative variant successfully applied!');
    } catch (err: any) {
      showToast(err.message || 'Failed to apply alternative.');
    }
  };

  // Concierge chat
  const handleSendChat = async (msg: string) => {
    if (!currentTripId) return null;
    const res = await api.sendChat(currentTripId, msg);
    // Reload messages
    const updated = await api.getChatHistory(currentTripId);
    setChatMessages(updated);
    if (res.version_change) {
      await loadTripDetails(currentTripId);
      await loadNotifications();
    }
    return res;
  };

  // If public shared link
  if (isShareRoute && shareToken) {
    return (
      <SharedTripView
        token={shareToken}
        onGoHome={() => {
          window.location.href = '/';
        }}
      />
    );
  }

  const currentTripSummary = trips.find(t => t.id === currentTripId);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-[#1a1a1a] font-geist selection:bg-[#905831]/20 selection:text-[#905831]">
      {/* Toast Notification Alert */}
      <AnimatePresence>
        {toastMessage && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed top-5 left-1/2 -translate-x-1/2 z-50 liquid-glass-dark px-5 py-2.5 rounded-full text-white text-xs font-semibold shadow-2xl border border-white/20 flex items-center gap-2"
          >
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <span>{toastMessage}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Navigation Bar */}
      <Navbar
        user={user}
        trips={trips}
        notifications={notifications}
        currentTripId={currentTripId}
        onSelectTrip={id => loadTripDetails(id)}
        onOpenAuth={mode => {
          setAuthMode(mode);
          setAuthModalOpen(true);
        }}
        onLogout={() => {
          api.logout();
          setUser(null);
          setCurrentTripId(null);
          setCurrentItinerary(null);
          showToast('Signed out successfully.');
        }}
        onOpenPlan={() => {
          setCurrentTripId(null);
          setCurrentItinerary(null);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        onOpenPricing={() => setPricingModalOpen(true)}
        onOpenFaq={() => setFaqModalOpen(true)}
        onOpenNotifications={() => setNotifModalOpen(true)}
        onGoHome={() => {
          setCurrentTripId(null);
          setCurrentItinerary(null);
        }}
      />

      {/* Main Viewport: Hero vs Dashboard */}
      <main className="w-full">
        {!currentItinerary || !currentTripSummary ? (
          <HeroSection
            destinations={destinations}
            onStartPlanning={handleStartPlanning}
          />
        ) : (
          <TripDashboard
            trip={currentTripSummary}
            itinerary={currentItinerary}
            versions={versions}
            expenses={expenses}
            analytics={analytics}
            onRefreshTrip={() => currentTripId && loadTripDetails(currentTripId)}
            onOpenConcierge={() => setConciergeOpen(true)}
            onOpenShare={() => setShareModalOpen(true)}
            onOpenLogExpense={() => setExpenseModalOpen(true)}
            onSimulateWeather={handleSimulateWeather}
            onCheckConditions={handleCheckConditions}
            onRevertVersion={handleRevertVersion}
            onToggleLock={handleToggleLock}
            onApplyAlternative={handleApplyAlternative}
            onItineraryUpdated={(newIt) => {
              setCurrentItinerary(newIt);
              if (currentTripId) loadTripDetails(currentTripId);
            }}
          />
        )}
      </main>

      {/* AI Planning Fullscreen Animation Overlay */}
      <AiPlanningOverlay
        isOpen={planningOpen}
        destinationName={planningDestName}
        traceSteps={planningTrace}
      />

      {/* AI Concierge Drawer */}
      {currentTripId && (
        <AiConciergeDrawer
          isOpen={conciergeOpen}
          onClose={() => setConciergeOpen(false)}
          tripId={currentTripId}
          onSendMessage={handleSendChat}
          messages={chatMessages}
          onRefreshTrip={() => loadTripDetails(currentTripId)}
          onRevertVersion={handleRevertVersion}
          currentVersion={currentItinerary?.version || 1}
        />
      )}

      {/* Auth Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        initialMode={authMode}
        onSuccess={loggedUser => {
          setUser(loggedUser);
          loadUserTrips();
          loadNotifications();
          showToast(`Welcome, ${loggedUser.display_name}!`);
        }}
      />

      {/* Share Modal */}
      {currentTripId && (
        <ShareModal
          isOpen={shareModalOpen}
          onClose={() => setShareModalOpen(false)}
          tripId={currentTripId}
        />
      )}

      {/* Notifications Modal */}
      <NotificationsModal
        isOpen={notifModalOpen}
        onClose={() => setNotifModalOpen(false)}
        notifications={notifications}
        onMarkRead={async id => {
          await api.markNotificationRead(id);
          await loadNotifications();
        }}
      />

      {/* Log Expense Modal */}
      {currentTripId && currentItinerary && (
        <LogExpenseModal
          isOpen={expenseModalOpen}
          onClose={() => setExpenseModalOpen(false)}
          tripId={currentTripId}
          days={currentItinerary.days}
          onExpenseAdded={async () => {
            if (currentTripId) await loadTripDetails(currentTripId);
            showToast('Expense recorded successfully.');
          }}
        />
      )}

      {/* Pricing & FAQ Modals */}
      <PricingModal
        isOpen={pricingModalOpen}
        onClose={() => setPricingModalOpen(false)}
        onPlanTrip={() => {
          setCurrentTripId(null);
          setCurrentItinerary(null);
        }}
      />

      <FaqModal
        isOpen={faqModalOpen}
        onClose={() => setFaqModalOpen(false)}
      />
    </div>
  );
}

export default App;
