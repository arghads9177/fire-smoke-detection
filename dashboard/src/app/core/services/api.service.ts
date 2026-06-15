import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  Alert,
  Camera,
  DetectionSettings,
  DetectionSettingsUpdate,
  Incident,
  IncidentFilters,
  IncidentListResponse,
} from '../models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly baseUrl = environment.apiBaseUrl;

  constructor(private readonly http: HttpClient) {}

  getCameras(): Observable<Camera[]> {
    return this.http.get<Camera[]>(`${this.baseUrl}/cameras`);
  }

  uploadFeed(cameraId: string, file: File): Observable<Camera> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<Camera>(`${this.baseUrl}/cameras/${cameraId}/feed`, formData);
  }

  setStreamUrl(cameraId: string, streamUrl: string): Observable<Camera> {
    return this.http.post<Camera>(`${this.baseUrl}/cameras/${cameraId}/stream`, { streamUrl });
  }

  getSystemInfo(): Observable<{ lanIp: string }> {
    return this.http.get<{ lanIp: string }>(`${this.baseUrl}/system/info`);
  }

  getAlerts(status?: string, cameraId?: string): Observable<Alert[]> {
    let params = new HttpParams();
    if (status) {
      params = params.set('status', status);
    }
    if (cameraId) {
      params = params.set('cameraId', cameraId);
    }
    return this.http.get<Alert[]>(`${this.baseUrl}/alerts`, { params });
  }

  acknowledgeAlert(alertId: string): Observable<Alert> {
    return this.http.put<Alert>(`${this.baseUrl}/alerts/${alertId}/acknowledge`, {});
  }

  getIncidents(filters: IncidentFilters = {}): Observable<IncidentListResponse> {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, String(value));
      }
    }
    return this.http.get<IncidentListResponse>(`${this.baseUrl}/incidents`, { params });
  }

  getIncident(incidentId: string): Observable<Incident> {
    return this.http.get<Incident>(`${this.baseUrl}/incidents/${incidentId}`);
  }

  getSettings(): Observable<DetectionSettings> {
    return this.http.get<DetectionSettings>(`${this.baseUrl}/settings`);
  }

  updateSettings(update: DetectionSettingsUpdate): Observable<DetectionSettings> {
    return this.http.put<DetectionSettings>(`${this.baseUrl}/settings`, update);
  }
}
