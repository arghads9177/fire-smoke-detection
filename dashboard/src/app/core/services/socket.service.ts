import { Injectable, OnDestroy } from '@angular/core';
import { BehaviorSubject, Observable, Subject } from 'rxjs';
import { io, Socket } from 'socket.io-client';

import { environment } from '../../../environments/environment';
import { Alert, Camera, Incident } from '../models';

@Injectable({ providedIn: 'root' })
export class SocketService implements OnDestroy {
  private socket: Socket | null = null;

  private readonly connected$ = new BehaviorSubject<boolean>(false);
  private readonly cameraStatus$ = new Subject<Camera>();
  private readonly alertNew$ = new Subject<Alert>();
  private readonly alertUpdated$ = new Subject<Alert>();
  private readonly alertCleared$ = new Subject<Alert>();
  private readonly incidentCreated$ = new Subject<Incident>();

  connect(): void {
    if (this.socket) {
      return;
    }

    this.socket = io(environment.socketUrl, {
      path: '/socket.io',
      transports: ['websocket'],
    });

    this.socket.on('connect', () => this.connected$.next(true));
    this.socket.on('disconnect', () => this.connected$.next(false));

    this.socket.on('camera:status', (camera: Camera) => this.cameraStatus$.next(camera));
    this.socket.on('alert:new', (alert: Alert) => this.alertNew$.next(alert));
    this.socket.on('alert:updated', (alert: Alert) => this.alertUpdated$.next(alert));
    this.socket.on('alert:cleared', (alert: Alert) => this.alertCleared$.next(alert));
    this.socket.on('incident:created', (incident: Incident) =>
      this.incidentCreated$.next(incident),
    );
  }

  disconnect(): void {
    this.socket?.disconnect();
    this.socket = null;
    this.connected$.next(false);
  }

  onConnectionChange(): Observable<boolean> {
    return this.connected$.asObservable();
  }

  onCameraStatus(): Observable<Camera> {
    return this.cameraStatus$.asObservable();
  }

  onAlertNew(): Observable<Alert> {
    return this.alertNew$.asObservable();
  }

  onAlertUpdated(): Observable<Alert> {
    return this.alertUpdated$.asObservable();
  }

  onAlertCleared(): Observable<Alert> {
    return this.alertCleared$.asObservable();
  }

  onIncidentCreated(): Observable<Incident> {
    return this.incidentCreated$.asObservable();
  }

  ngOnDestroy(): void {
    this.disconnect();
  }
}
