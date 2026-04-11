/* ──────────────────────────────────────────────────────────────
   API Client — centralised fetch wrapper
   All pages import this and call API.xxx()
   ────────────────────────────────────────────────────────────── */

const BASE_URL = (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost')
  ? 'http://127.0.0.1:8000'
  : '';

const API = (() => {
  function getToken() { return localStorage.getItem('re_token'); }

  function authHeaders() {
    const t = getToken();
    return t ? { 'Authorization': `Bearer ${t}`, 'Content-Type': 'application/json' }
             : { 'Content-Type': 'application/json' };
  }

  function toQS(params) {
    const q = Object.entries(params)
      .filter(([, v]) => v !== null && v !== undefined && v !== '')
      .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
      .join('&');
    return q ? '?' + q : '';
  }

  async function request(method, path, body = null) {
    const opts = { method, headers: authHeaders() };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(BASE_URL + path, opts);
    if (res.status === 401) {
      localStorage.removeItem('re_token');
      window.location.href = 'login.html';
      return;
    }
    if (res.status === 204) return null;
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    return data;
  }

  return {
    // ── Auth ───────────────────────────────────────────────────────
    async login(username, password) {
      const form = new URLSearchParams({ username, password });
      const res = await fetch(`${BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Login failed');
      return data;
    },
    async me() { return request('GET', '/auth/me'); },

    // ── Analytics ─────────────────────────────────────────────────
    async getSummary()                 { return request('GET', '/analytics/summary'); },
    async getPriceTrends(params = {})  { return request('GET', '/analytics/price-trends'    + toQS(params)); },
    async getLocalityDemand(params={}) { return request('GET', '/analytics/locality-demand' + toQS(params)); },
    async getPropertyDist(params={})   { return request('GET', '/analytics/property-distribution' + toQS(params)); },
    async getAgentPerf(params={})      { return request('GET', '/analytics/agent-performance' + toQS(params)); },
    async getBedroomPrice(params={})   { return request('GET', '/analytics/bedroom-price'   + toQS(params)); },
    async getCities()                  { return request('GET', '/analytics/cities'); },
    async getLocalities(cityId)        { return request('GET', `/analytics/localities${cityId ? '?city_id='+cityId : ''}`); },
    async refreshViews()               { return request('POST', '/analytics/refresh-views'); },

    // ── Listings ──────────────────────────────────────────────────
    async getListings(params = {})  { return request('GET', '/listings' + toQS(params)); },
    async getListing(id)            { return request('GET', `/listings/${id}`); },
    async createListing(body)       { return request('POST', '/listings', body); },
    async updateListing(id, body)   { return request('PUT', `/listings/${id}`, body); },
    async deleteListing(id)         { return request('DELETE', `/listings/${id}`); },

    // ── Agents ────────────────────────────────────────────────────
    async getAgents(params = {})    { return request('GET', '/agents' + toQS(params)); },
    async getAgent(id)              { return request('GET', `/agents/${id}`); },
    async createAgent(body)         { return request('POST', '/agents', body); },
    async updateAgent(id, body)     { return request('PUT', `/agents/${id}`, body); },
    async deleteAgent(id)           { return request('DELETE', `/agents/${id}`); },

    // ── Transactions ──────────────────────────────────────────────
    async getTransactions(params={}) { return request('GET', '/transactions' + toQS(params)); },
    async getTransaction(id)         { return request('GET', `/transactions/${id}`); },
    async createTransaction(body)    { return request('POST', '/transactions', body); },
    async updateTransaction(id,body) { return request('PUT', `/transactions/${id}`, body); },
    async deleteTransaction(id)      { return request('DELETE', `/transactions/${id}`); },
  };
})();

// ── Auth guard (call on every protected page) ─────────────────────────────────
function requireAuth() {
  if (!localStorage.getItem('re_token')) {
    window.location.href = 'login.html';
    return false;
  }
  return true;
}

// ── Format helpers ────────────────────────────────────────────────────────────
const Fmt = {
  price(v) {
    if (!v) return '—';
    const n = parseFloat(v);
    if (n >= 1e7)  return '₹' + (n / 1e7).toFixed(2)  + ' Cr';
    if (n >= 1e5)  return '₹' + (n / 1e5).toFixed(2)  + ' L';
    return '₹' + n.toLocaleString('en-IN');
  },
  number(v, decimals = 0) {
    if (v == null) return '—';
    return parseFloat(v).toLocaleString('en-IN', { maximumFractionDigits: decimals });
  },
  date(v) {
    if (!v) return '—';
    return new Date(v).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  },
  transact(v) { return v === 2 ? 'Rent' : 'Buy/Sell'; },
  furnish(v)  {
    return { 0:'Unknown', 1:'Furnished', 2:'Semi-Furnished', 4:'Unfurnished' }[v] || '—';
  },
};
