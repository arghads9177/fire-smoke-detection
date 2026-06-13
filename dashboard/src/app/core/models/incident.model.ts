import { AlertLevel, DetectionType } from './detection.model';

export interface Incident {
  incidentId: string;
  cameraId: string;
  type: DetectionType;
  level: AlertLevel;
  confidence: number;
  snapshot: string | null;
  snapshotUrl: string | null;
  timestamp: string;
  acknowledged: boolean;
}

export interface IncidentListResponse {
  items: Incident[];
  total: number;
  page: number;
  pageSize: number;
}

export interface IncidentFilters {
  cameraId?: string;
  type?: DetectionType;
  start?: string;
  end?: string;
  page?: number;
  pageSize?: number;
}
