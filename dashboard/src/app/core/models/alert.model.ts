import { AlertLevel, DetectionType } from './detection.model';

export interface Alert {
  alertId: string;
  cameraId: string;
  type: DetectionType;
  level: AlertLevel;
  status: 'ACTIVE' | 'ACKNOWLEDGED' | 'CLEARED';
  firstSeenAt: string;
  lastSeenAt: string;
  maxConfidence: number;
  incidentId: string;
}
