import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return {
    headers: {
      Authorization: `Bearer ${token}`
    }
  };
};

export const serviceCenterApi = {
  getDashboard: async () => {
    const res = await axios.get(`${API_BASE_URL}/service-center/dashboard`, getAuthHeaders());
    return res.data;
  },

  getClaims: async () => {
    const res = await axios.get(`${API_BASE_URL}/service-center/claims`, getAuthHeaders());
    return res.data;
  },

  getClaim: async (claimId: string) => {
    const res = await axios.get(`${API_BASE_URL}/service-center/claims/${claimId}`, getAuthHeaders());
    return res.data;
  },

  updateClaimStatus: async (claimId: string, status: string) => {
    const res = await axios.patch(`${API_BASE_URL}/service-center/claims/${claimId}/status`, { status }, getAuthHeaders());
    return res.data;
  },

  assignTechnician: async (claimId: string, technicianName: string) => {
    const res = await axios.post(`${API_BASE_URL}/service-center/claims/${claimId}/assign`, { technician_name: technicianName }, getAuthHeaders());
    return res.data;
  },

  uploadEvidence: async (claimId: string, files: File[], category: string = 'Service Center Image') => {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    formData.append('category', category);

    const token = localStorage.getItem('token');
    const res = await axios.post(`${API_BASE_URL}/service-center/claims/${claimId}/evidence`, formData, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'multipart/form-data'
      }
    });
    return res.data;
  },

  runAssessment: async (claimId: string) => {
    const res = await axios.post(`${API_BASE_URL}/assessments/${claimId}/run`, {}, getAuthHeaders());
    return res.data;
  },

  getAssessment: async (claimId: string) => {
    const res = await axios.get(`${API_BASE_URL}/assessments/${claimId}`, getAuthHeaders());
    return res.data;
  },

  submitTechnicianReview: async (claimId: string, data: { technician_overrides: any; review_notes?: string; technician_name?: string }) => {
    const res = await axios.post(`${API_BASE_URL}/service-center/claims/${claimId}/technician-review`, data, getAuthHeaders());
    return res.data;
  },

  saveRepairEstimate: async (claimId: string, data: { items: any[]; total_estimated_cost?: number }) => {
    const res = await axios.post(`${API_BASE_URL}/service-center/claims/${claimId}/repair-estimate`, data, getAuthHeaders());
    return res.data;
  },

  generateClaimPackage: async (claimId: string) => {
    const res = await axios.post(`${API_BASE_URL}/assessments/${claimId}/generate-package`, {}, getAuthHeaders());
    return res.data;
  },

  getClaimPDFUrl: (claimId: string) => {
    return `${API_BASE_URL}/claims/${claimId}/package/pdf`;
  },

  getClaimZIPUrl: (claimId: string) => {
    return `${API_BASE_URL}/claims/${claimId}/package/zip`;
  }
};
