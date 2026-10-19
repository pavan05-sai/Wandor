export interface User {
  id: number | string;
  email: string;
  display_name: string;
  created_at?: string;
}

export interface AuthResponse {
  user: User;
  token: string;
}

export interface Preferences {
  interests: string[];
  pace: string;
  budget_level: string;
  transport_modes: string[];
  accommodation_type: string;
  dietary: string[];
  avoid: string[];
  mobility: string;
  home_city?: string | null;
}

export interface Destination {
  id: string;
  catalog_id: string;
  name: string;
  country: string;
  lat: float;
  lng: float;
  blurb: string;
  image: string;
  coverage: number;
}

export type float = number;

export interface Travelers {
  adults: number;
  children: number;
}

export interface DestinationRef {
  name: string;
  country: string;
  lat: number;
  lng: number;
  catalog_id: string;
}

export interface TripInfo {
  title: string;
  destination: DestinationRef;
  start_date: string;
  end_date: string;
  num_days: number;
  travelers: Travelers;
  currency: string;
}

export interface BudgetBreakdown {
  accommodation: number;
  transport: number;
  food: number;
  activities: number;
  misc: number;
  reserve: number;
}

export interface BudgetBlock {
  total_limit: number;
  reserve_pct: number;
  breakdown: BudgetBreakdown;
  estimated_total: number;
  spendable: number;
  remaining: number;
  per_day: number;
  per_person: number;
  status: 'ok' | 'tight' | 'over';
  computed_at?: string;
}

export interface BookingRef {
  type: string;
  url?: string | null;
  ref?: string | null;
  note: string;
}

export interface AccommodationBlock {
  place_id: string;
  name: string;
  nights: number;
  rooms: number;
  nightly_cost: number;
  check_in: string;
  check_out: string;
  booking?: BookingRef | null;
  reason: string;
}

export interface ItemCost {
  amount: number;
  per: string;
  basis: string;
}

export interface ItineraryItem {
  id: string;
  type: 'activity' | 'meal' | 'transit' | 'free_time' | 'checkin' | 'checkout';
  place_id: string;
  name: string;
  category: string;
  lat: number;
  lng: number;
  start_time: string;
  end_time: string;
  duration_min: number;
  indoor: boolean;
  cost: ItemCost;
  reason: string;
  reason_factors: string[];
  locked: boolean;
  status: string;
  booking?: BookingRef | null;
  alt_ids?: string[];
}

export interface RouteLeg {
  id: string;
  from_item: string;
  to_item: string;
  mode: string;
  distance_km: number;
  duration_min: number;
  cost: number;
  source: string;
  geometry: [number, number][];
}

export interface DayTotals {
  activity_cost: number;
  food_cost: number;
  transport_cost: number;
  travel_minutes: number;
  active_minutes: number;
}

export interface DayWeather {
  summary: string;
  temp_max_c: number;
  rain_prob_pct: number;
  source: 'live' | 'cache' | 'demo' | 'simulated';
  as_of?: string | null;
}

export interface ItineraryDay {
  id: string;
  day_number: number;
  date: string;
  theme: string;
  weather: DayWeather;
  items: ItineraryItem[];
  routes: RouteLeg[];
  totals: DayTotals;
}

export interface ChangeOp {
  op: 'REPLACE_ITEM' | 'REMOVE_ITEM' | 'ADD_ITEM' | 'MOVE_ITEM' | 'LOCK_ITEM' | 'UNLOCK_ITEM';
  item_id?: string | null;
  day_id?: string | null;
  target_day_id?: string | null;
  new_place_id?: string | null;
  position?: number | null;
  parameters?: Record<string, any>;
}

export interface ChangeSet {
  ops: ChangeOp[];
  rationale: string;
  expected_effects?: Record<string, any>;
}

export interface AlternativeOption {
  id: string;
  label: string;
  summary: string;
  delta: Record<string, any>;
  change_set: {
    ops: ChangeOp[];
  };
}

export interface EventRecord {
  id: string;
  type: string;
  day_id?: string | null;
  severity: string;
  detail: string;
  source: string;
  handled_in_version?: number | null;
}

export interface NoteItem {
  id: string;
  day_id?: string | null;
  text: string;
  origin: string;
}

export interface ProvenanceBlock {
  weather: string;
  routing: string;
  places: string;
  llm: string;
  overall: string;
}

export interface WarningItem {
  code: string;
  message: string;
  day_id?: string | null;
}

export interface CanonicalItinerary {
  schema_version: string;
  trip_id: string;
  version: number;
  parent_version?: number | null;
  created_by: string;
  change_summary: string;
  mode: string;
  trip: TripInfo;
  preferences: Preferences;
  budget: BudgetBlock;
  accommodation: AccommodationBlock;
  days: ItineraryDay[];
  alternatives: AlternativeOption[];
  events: EventRecord[];
  notes: NoteItem[];
  provenance: ProvenanceBlock;
  warnings: WarningItem[];
}

export interface TripSummary {
  id: number | string;
  user_id: number | string;
  title: string;
  destination_id: string;
  destination_name: string;
  start_date: string;
  end_date: string;
  num_days: number;
  status: string;
  current_version: number;
  mode: string;
  total_budget: number;
  estimated_total: number;
  budget_status: string;
  created_at: string;
}

export interface TripDetailResponse {
  trip: TripSummary;
  itinerary?: CanonicalItinerary | null;
}

export interface ChatMessage {
  id: number | string;
  trip_id: number | string;
  role: 'user' | 'assistant';
  content: string;
  intent?: string | null;
  created_at?: string;
}

export interface ChatResponseData {
  reply: string;
  intent: 'answer' | 'modify' | 'regenerate' | 'clarify';
  version_change: boolean;
  diff?: any;
  trace?: string[];
  changeset?: ChangeSet;
}

export interface Expense {
  id: number | string;
  trip_id: number | string;
  day_id?: string | null;
  category: string;
  amount: number;
  note?: string | null;
  spent_at: string;
}

export interface NotificationItem {
  id: number | string;
  user_id: number | string;
  trip_id?: number | string | null;
  type: string;
  title: string;
  body: string;
  severity: 'info' | 'warning' | 'alert';
  read: boolean;
  created_at: string;
}

export interface VersionSummary {
  version: number;
  parent_version?: number | null;
  created_by: string;
  change_summary: string;
  created_at: string;
}

export interface ShareResponse {
  token: string;
  url: string;
}

export interface TripAnalytics {
  totals: {
    budget_limit: number;
    estimated_total: number;
    actual_spent: number;
    remaining_budget: number;
  };
  by_category: {
    category: string;
    planned: number;
    actual: number;
  }[];
  pace_distribution: {
    day_number: number;
    active_minutes: number;
    travel_minutes: number;
    items_count: number;
  }[];
}
