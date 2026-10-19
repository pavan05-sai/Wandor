import type {
  AuthResponse,
  CanonicalItinerary,
  ChatMessage,
  ChatResponseData,
  Destination,
  Expense,
  NotificationItem,
  Preferences,
  ShareResponse,
  TripAnalytics,
  TripDetailResponse,
  TripSummary,
  User,
  VersionSummary
} from '../types';

const rawApiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_BASE = rawApiBase.replace(/\/+$/, '');

class ApiClient {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem('wandor_token');
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('wandor_token', token);
    } else {
      localStorage.removeItem('wandor_token');
    }
  }

  getToken(): string | null {
    return this.token || localStorage.getItem('wandor_token');
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers || {});
    headers.set('Content-Type', 'application/json');

    const currentToken = this.getToken();
    if (currentToken && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${currentToken}`);
    }

    const url = `${API_BASE}${path}`;
    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      const json = await response.json();

      if (!response.ok || json.ok === false) {
        const errorMsg = json.error?.message || `Request failed with status ${response.status}`;
        throw new Error(errorMsg);
      }

      return json.data as T;
    } catch (err: any) {
      console.error(`API Error [${options.method || 'GET'} ${path}]:`, err);
      throw err;
    }
  }

  // --- Auth ---
  async register(data: { email: string; password: string; display_name: string }): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    this.setToken(res.token);
    return res;
  }

  async login(data: { email: string; password: string }): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    this.setToken(res.token);
    return res;
  }

  async demoLogin(): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>('/auth/demo', {
      method: 'POST',
    });
    this.setToken(res.token);
    return res;
  }

  logout() {
    this.setToken(null);
  }

  async getMe(): Promise<User> {
    return this.request<User>('/users/me');
  }

  async getPreferences(): Promise<Preferences> {
    return this.request<Preferences>('/users/me/preferences');
  }

  async updatePreferences(preferences: Preferences): Promise<Preferences> {
    return this.request<Preferences>('/users/me/preferences', {
      method: 'PUT',
      body: JSON.stringify(preferences),
    });
  }

  // --- Destinations & Trips ---
  async getDestinations(): Promise<Destination[]> {
    return this.request<Destination[]>('/destinations');
  }

  async searchDestinations(query: string): Promise<Destination[]> {
    return this.request<Destination[]>(`/destinations/search?q=${encodeURIComponent(query)}`);
  }

  async createTrip(data: {
    destination_id: string;
    start_date: string;
    end_date: string;
    travelers: { adults: number; children: number };
    budget: number;
    title?: string;
    preferences?: Partial<Preferences>;
  }): Promise<{ trip_id: number; trip: TripSummary }> {
    return this.request<{ trip_id: number; trip: TripSummary }>('/trips', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getTrips(): Promise<TripSummary[]> {
    return this.request<TripSummary[]>('/trips');
  }

  async getTrip(id: number | string): Promise<TripDetailResponse> {
    return this.request<TripDetailResponse>(`/trips/${id}`);
  }

  async deleteTrip(id: number | string): Promise<{ ok: boolean }> {
    return this.request<{ ok: boolean }>(`/trips/${id}`, {
      method: 'DELETE',
    });
  }

  async updateTripSettings(
    id: number | string,
    settings: { budget?: number; num_days?: number; preferences?: Preferences }
  ): Promise<{ itinerary: CanonicalItinerary; diff: any }> {
    return this.request<{ itinerary: CanonicalItinerary; diff: any }>(`/trips/${id}/settings`, {
      method: 'PATCH',
      body: JSON.stringify(settings),
    });
  }

  // --- Itinerary & Versions ---
  async generateItinerary(
    id: number | string,
    regenerate: boolean = false
  ): Promise<{ itinerary: CanonicalItinerary; trace: string[]; alternatives: any[] }> {
    return this.request<{ itinerary: CanonicalItinerary; trace: string[]; alternatives: any[] }>(
      `/trips/${id}/generate?regenerate=${regenerate}`,
      {
        method: 'POST',
      }
    );
  }

  async getVersions(id: number | string): Promise<VersionSummary[]> {
    return this.request<VersionSummary[]>(`/trips/${id}/versions`);
  }

  async getVersion(id: number | string, version: number): Promise<CanonicalItinerary> {
    return this.request<CanonicalItinerary>(`/trips/${id}/versions/${version}`);
  }

  async getDiff(id: number | string, fromVersion: number, toVersion: number): Promise<any> {
    return this.request<any>(`/trips/${id}/diff?from=${fromVersion}&to=${toVersion}`);
  }

  async revertVersion(id: number | string, version: number): Promise<CanonicalItinerary> {
    const res = await this.request<any>(`/trips/${id}/versions/${version}/revert`, {
      method: 'POST',
    });
    return (res.itinerary || res) as CanonicalItinerary;
  }

  async updateItem(
    tripId: number | string,
    itemId: string,
    operation: { op: string; parameters?: any }
  ): Promise<{ itinerary: CanonicalItinerary; diff: any }> {
    return this.request<{ itinerary: CanonicalItinerary; diff: any }>(`/trips/${tripId}/items/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify(operation),
    });
  }

  async applyAlternative(
    tripId: number | string,
    altId: string
  ): Promise<{ itinerary: CanonicalItinerary; diff: any }> {
    return this.request<{ itinerary: CanonicalItinerary; diff: any }>(`/trips/${tripId}/alternatives/${altId}/apply`, {
      method: 'POST',
    });
  }

  // --- AI Chat ---
  async sendChat(tripId: number | string, message: string): Promise<ChatResponseData> {
    return this.request<ChatResponseData>(`/trips/${tripId}/chat`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  }

  async getChatHistory(tripId: number | string): Promise<ChatMessage[]> {
    return this.request<ChatMessage[]>(`/trips/${tripId}/chat`);
  }

  // --- Weather & Events ---
  async getWeather(tripId: number | string): Promise<{ forecast: any[]; provenance: any }> {
    return this.request<{ forecast: any[]; provenance: any }>(`/trips/${tripId}/weather`);
  }

  async checkConditions(tripId: number | string): Promise<{ events: any[]; replan_result?: CanonicalItinerary }> {
    return this.request<{ events: any[]; replan_result?: CanonicalItinerary }>(`/trips/${tripId}/events/check`, {
      method: 'POST',
    });
  }

  async simulateEvent(
    tripId: number | string,
    data: { type: string; day_id?: string; severity?: string; detail?: string; payload?: any }
  ): Promise<{ event: any; itinerary?: CanonicalItinerary }> {
    return this.request<{ event: any; itinerary?: CanonicalItinerary }>(`/trips/${tripId}/events/simulate`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // --- Compiler & Unstructured Import ---
  async compilerParse(
    tripId: number | string,
    text: string
  ): Promise<{
    source_lines_analyzed: number;
    extracted_count: number;
    items: any[];
    conflicts: string[];
    catalog_matched_count: number;
  }> {
    return this.request<any>(`/trips/${tripId}/compiler/parse`, {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
  }

  async compilerApply(
    tripId: number | string,
    items: any[]
  ): Promise<{ itinerary: CanonicalItinerary; added_count: number; version: number }> {
    return this.request<any>(`/trips/${tripId}/compiler/apply`, {
      method: 'POST',
      body: JSON.stringify({ items }),
    });
  }


  // --- Budget & Expenses ---
  async getBudget(tripId: number | string): Promise<any> {
    return this.request<any>(`/trips/${tripId}/budget`);
  }

  async logExpense(
    tripId: number | string,
    data: { category: string; amount: number; day_id?: string; note?: string }
  ): Promise<Expense> {
    return this.request<Expense>(`/trips/${tripId}/expenses`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getExpenses(tripId: number | string): Promise<{ expenses: Expense[]; totals_by_category: Record<string, number> }> {
    return this.request<{ expenses: Expense[]; totals_by_category: Record<string, number> }>(`/trips/${tripId}/expenses`);
  }

  // --- Notifications ---
  async getNotifications(unreadOnly: boolean = false): Promise<NotificationItem[]> {
    return this.request<NotificationItem[]>(`/notifications?unread=${unreadOnly}`);
  }

  async markNotificationRead(id: number | string): Promise<{ ok: boolean }> {
    return this.request<{ ok: boolean }>(`/notifications/${id}/read`, {
      method: 'POST',
    });
  }

  // --- Sharing ---
  async shareTrip(tripId: number | string, expiresInDays?: number): Promise<ShareResponse> {
    return this.request<ShareResponse>(`/trips/${tripId}/share`, {
      method: 'POST',
      body: JSON.stringify({ expiry_days: expiresInDays || 30 }),
    });
  }

  async revokeShare(tripId: number | string): Promise<{ ok: boolean }> {
    return this.request<{ ok: boolean }>(`/trips/${tripId}/share`, {
      method: 'DELETE',
    });
  }

  async getSharedTrip(token: string): Promise<CanonicalItinerary> {
    const res = await this.request<{ shared: boolean; token: string; itinerary: CanonicalItinerary }>(`/shared/${token}`);
    return res.itinerary;
  }

  // --- Analytics ---
  async getTripAnalytics(tripId: number | string): Promise<TripAnalytics> {
    const raw = await this.request<any>(`/trips/${tripId}/analytics`);
    const plannedByCat = raw.planned_by_category || {};
    const actualByCat = raw.actual_by_category || {};
    const allCategories = Array.from(new Set([...Object.keys(plannedByCat), ...Object.keys(actualByCat)]));

    const by_category = allCategories.map(cat => ({
      category: cat,
      planned: Number(plannedByCat[cat]) || 0,
      actual: Number(actualByCat[cat]) || 0,
    }));

    const timeDist = raw.time_distribution?.by_day || [];
    const pace_distribution = timeDist.map((d: any) => ({
      day_number: d.day_number,
      active_minutes: d.active_minutes || 0,
      travel_minutes: d.travel_minutes || 0,
      items_count: d.items_count || 3,
    }));

    const pVsA = raw.planned_vs_actual || {};
    const plannedTotal = Number(pVsA.planned_total) || 0;
    const actualTotal = Number(pVsA.actual_total) || 0;

    return {
      totals: {
        budget_limit: plannedTotal,
        estimated_total: plannedTotal,
        actual_spent: actualTotal,
        remaining_budget: Math.max(0, plannedTotal - actualTotal),
      },
      by_category,
      pace_distribution,
    };
  }

  async getOverviewAnalytics(): Promise<any> {
    return this.request<any>('/analytics/overview');
  }

  // --- Health ---
  async getHealth(): Promise<{ status: string; providers: Record<string, string>; demo_mode: string }> {
    return this.request<{ status: string; providers: Record<string, string>; demo_mode: string }>('/health');
  }
}

export const api = new ApiClient();
