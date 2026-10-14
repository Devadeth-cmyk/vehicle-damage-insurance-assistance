import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export interface Vehicle {
  id: number;
  registration_number: string;
  make: string;
  model: string;
  year: number;
  fuel_type?: string;
  vehicle_type?: string;
  variant?: string;
  transmission?: string;
  color?: string;
  vin?: string;
  engine_number?: string;
  registration_date?: string;
  registration_state?: string;
  rto?: string;
  insurance_provider?: string;
  policy_number?: string;
  policy_type?: string;
  policy_start_date?: string;
  policy_expiry_date?: string;
}

export interface Claim {
  claim_id: string;
  vehicle_id: number;
  status: string;
  customer_address?: string | null;
  accident_date?: string | null;
  accident_time?: string | null;
  accident_type?: string | null;
  accident_location?: string | null;
  accident_description?: string | null;
  insurance_company?: string | null;
  policy_type?: string | null;
  policy_expiry?: string | null;
  incident_date?: string | null;
  incident_type?: string | null;
  incident_location?: string | null;
  incident_description?: string | null;
  policy_number?: string | null;
  created_at?: string | null;
  evidence?: { file_name: string; file_path?: string; file_type?: string; uploaded_at?: string | null }[];
  vehicle?: {
    make: string;
    model: string;
    year?: number | null;
    registration_number: string;
    vin?: string | null;
    engine_number?: string | null;
  } | null;
  assessment?: {
    status: string;
    damage_results?: Record<string, unknown> | null;
    parts_results?: Record<string, unknown> | null;
    severity_results?: Record<string, unknown> | null;
    fusion_results?: Record<string, unknown> | null;
    repair_results?: Record<string, unknown> | null;
    total_estimated_cost?: number | null;
    error_message?: string | null;
  } | null;
  service_center_id?: number;
  service_center_name?: string;
}

export const getEvidenceDisplay = (fileName: string) => {
  const documentTypes: Array<[RegExp, string]> = [
    [/^Policy_Document_/i, 'Policy Document'],
    [/^Registration_Certificate_RC_/i, 'Registration Certificate'],
    [/^Driving_Licence_/i, 'Driving License'],
  ];
  const documentType = documentTypes.find(([prefix]) => prefix.test(fileName));
  const originalName = documentType
    ? fileName.replace(documentType[0], '')
    : fileName;

  return {
    label: documentType?.[1] || 'Supporting Document',
    fileName: originalName.replace(/_/g, ' '),
  };
};

export const formatClaimDate = (claim: Claim): string => {
  const value = claim.accident_date || claim.incident_date || claim.created_at;
  if (!value || Number.isNaN(Date.parse(value))) return 'Not provided';
  return new Date(value).toLocaleDateString();
};

export interface User {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  role: 'user' | 'service_center' | 'admin' | 'adjuster';
  first_name?: string;
  last_name?: string;
  date_of_birth?: string;
  gender?: string;
  address_line?: string;
  city?: string;
  state?: string;
  pincode?: string;
  country?: string;
}

export interface ServiceCenter {
  id: number;
  name: string;
  address: string;
  city: string;
  phone: string;
  email: string;
  supported_brands: string[];
  insurance_providers: string[];
  rating: number;
  distance_km?: number;
  opening_hours?: string;
}

export interface ServiceRequest {
  id: string;
  claim_id: string;
  service_center_id: number;
  service_center_name: string;
  request_type: string;
  preferred_date: string;
  preferred_time: string;
  priority: string;
  pickup_required: boolean;
  pickup_address?: string;
  customer_notes?: string;
  status: 'Submitted' | 'Under Review' | 'Accepted' | 'Appointment Confirmed' | 'Vehicle Received' | 'Inspection' | 'Repair In Progress' | 'Repair Completed' | 'Ready For Pickup' | 'Completed' | 'Rejected' | 'Cancelled';
  created_at: string;
}

export interface Appointment {
  id: string;
  service_request_id: string;
  service_center_name: string;
  vehicle_info: string;
  appointment_date: string;
  appointment_time: string;
  status: 'Confirmed' | 'Completed' | 'Rescheduled' | 'Cancelled';
}

export interface NotificationItem {
  id: string;
  title: string;
  description: string;
  timestamp: string;
  read: boolean;
  type: 'assessment' | 'claim' | 'service_request' | 'appointment' | 'system';
}
