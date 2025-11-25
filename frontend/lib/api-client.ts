import axios, { AxiosInstance } from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config) => {
        if (typeof window !== 'undefined') {
          const token = localStorage.getItem('access_token');
          if (token) {
            config.headers.Authorization = `Bearer ${token}`;
          }
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor to handle token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          if (typeof window !== 'undefined') {
            const refreshToken = localStorage.getItem('refresh_token');

            if (refreshToken) {
              try {
                const response = await axios.post(`${API_URL}/api/v1/auth/refresh`, {
                  refresh_token: refreshToken,
                });

                const { access_token, refresh_token: newRefreshToken } = response.data;
                localStorage.setItem('access_token', access_token);
                localStorage.setItem('refresh_token', newRefreshToken);

                originalRequest.headers.Authorization = `Bearer ${access_token}`;
                return this.client(originalRequest);
              } catch (refreshError) {
                // Refresh failed, redirect to login
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
                window.location.href = '/login';
                return Promise.reject(refreshError);
              }
            } else {
              // No refresh token, redirect to login
              window.location.href = '/login';
            }
          }
        }

        return Promise.reject(error);
      }
    );
  }

  // Auth endpoints
  async signup(data: {
    organization_name: string;
    email: string;
    password: string;
    first_name: string;
    last_name: string;
  }) {
    return this.client.post('/api/v1/auth/signup', data);
  }

  async login(email: string, password: string) {
    return this.client.post('/api/v1/auth/login', { email, password });
  }

  async getCurrentUser() {
    return this.client.get('/api/v1/users/me');
  }

  async getUserPermissions() {
    return this.client.get('/api/v1/users/me/permissions');
  }

  // Organizations
  async getOrganization() {
    return this.client.get('/api/v1/organizations/me');
  }

  async getOrganizationStats() {
    return this.client.get('/api/v1/organizations/me/stats');
  }

  // Companies
  async getCompanies(params?: { limit?: number; offset?: number; search?: string }) {
    return this.client.get('/api/v1/crm/companies', { params });
  }

  async getCompany(id: number) {
    return this.client.get(`/api/v1/crm/companies/${id}`);
  }

  async createCompany(data: { company_name: string; cin?: string }) {
    return this.client.post('/api/v1/crm/companies', data);
  }

  async updateCompany(id: number, data: { company_name?: string; cin?: string }) {
    return this.client.patch(`/api/v1/crm/companies/${id}`, data);
  }

  async deleteCompany(id: number) {
    return this.client.delete(`/api/v1/crm/companies/${id}`);
  }

  // Contacts
  async getContacts(params?: { limit?: number; offset?: number; search?: string; company_id?: number }) {
    return this.client.get('/api/v1/crm/contacts', { params });
  }

  async getContact(id: number) {
    return this.client.get(`/api/v1/crm/contacts/${id}`);
  }

  async createContact(data: any) {
    return this.client.post('/api/v1/crm/contacts', data);
  }

  async updateContact(id: number, data: any) {
    return this.client.patch(`/api/v1/crm/contacts/${id}`, data);
  }

  async deleteContact(id: number) {
    return this.client.delete(`/api/v1/crm/contacts/${id}`);
  }

  // WhatsApp Instances
  async getWhatsAppInstances() {
    return this.client.get('/api/v1/whatsapp/instances');
  }

  async getWhatsAppInstance(id: number) {
    return this.client.get(`/api/v1/whatsapp/instances/${id}`);
  }

  async createWhatsAppInstance(data: { name: string; phone_number: string }) {
    return this.client.post('/api/v1/whatsapp/instances', data);
  }

  async getWhatsAppInstanceQR(id: number) {
    return this.client.get(`/api/v1/whatsapp/instances/${id}/qr`);
  }

  async deleteWhatsAppInstance(id: number) {
    return this.client.delete(`/api/v1/whatsapp/instances/${id}`);
  }

  async sendWhatsAppMessage(data: {
    instance_id: number;
    phone_number: string;
    message: string;
    contact_id?: number;
  }) {
    return this.client.post('/api/v1/whatsapp/send', data);
  }

  async getWhatsAppMessages(params?: { limit?: number; offset?: number; instance_id?: number; contact_id?: number }) {
    return this.client.get('/api/v1/whatsapp/messages', { params });
  }

  // Campaigns
  async getCampaigns(params?: { limit?: number; offset?: number; status_filter?: string }) {
    return this.client.get('/api/v1/campaigns', { params });
  }

  async getCampaign(id: number) {
    return this.client.get(`/api/v1/campaigns/${id}`);
  }

  async createCampaign(data: any) {
    return this.client.post('/api/v1/campaigns', data);
  }

  async addContactsToCampaign(campaignId: number, contactIds: number[]) {
    return this.client.post(`/api/v1/campaigns/${campaignId}/contacts`, {
      contact_ids: contactIds,
    });
  }

  async startCampaign(id: number) {
    return this.client.post(`/api/v1/campaigns/${id}/start`);
  }

  async pauseCampaign(id: number) {
    return this.client.post(`/api/v1/campaigns/${id}/pause`);
  }

  async getCampaignStats(id: number) {
    return this.client.get(`/api/v1/campaigns/${id}/stats`);
  }

  async deleteCampaign(id: number) {
    return this.client.delete(`/api/v1/campaigns/${id}`);
  }

  // Users
  async getUsers() {
    return this.client.get('/api/v1/users');
  }

  async inviteUser(data: {
    email: string;
    role: string;
    first_name: string;
    last_name: string;
  }) {
    return this.client.post('/api/v1/users', data);
  }

  async updateUserRole(userId: number, role: string) {
    return this.client.patch(`/api/v1/users/${userId}/role`, { role });
  }

  async deleteUser(userId: number) {
    return this.client.delete(`/api/v1/users/${userId}`);
  }
}

const apiClient = new APIClient();
export default apiClient;

