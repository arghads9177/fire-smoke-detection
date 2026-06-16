import { AsyncPipe } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';
import { EMPTY, interval, Subscription } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';

import { Alert } from './core/models';
import { ApiService } from './core/services/api.service';
import { AudioAlarmService } from './core/services/audio-alarm.service';
import { SocketService } from './core/services/socket.service';
import { NavComponent } from './layout/nav/nav.component';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, NavComponent, AsyncPipe],
  templateUrl: './app.component.html',
})
export class AppComponent implements OnInit, OnDestroy {
  readonly connected$;
  criticalCount = 0;

  private readonly criticalAlerts = new Map<string, Alert>();
  private readonly subs = new Subscription();

  constructor(
    private readonly socketService: SocketService,
    private readonly api: ApiService,
    readonly audioAlarm: AudioAlarmService,
  ) {
    this.connected$ = this.socketService.onConnectionChange();
  }

  ngOnInit(): void {
    this.socketService.connect();
    this.seedCriticalAlerts();
    this.wireSocketAlerts();
    this.wirePollingFallback();
  }

  ngOnDestroy(): void {
    this.subs.unsubscribe();
  }

  enableAudio(): void {
    this.audioAlarm.enable();
  }

  private seedCriticalAlerts(): void {
    this.api.getAlerts('ACTIVE').subscribe((alerts) => {
      this.criticalAlerts.clear();
      alerts.filter((a) => a.level === 'CRITICAL').forEach((a) => this.criticalAlerts.set(a.alertId, a));
      this.sync();
    });
  }

  private wireSocketAlerts(): void {
    this.subs.add(this.socketService.onAlertNew().subscribe((a) => this.onAlert(a)));
    this.subs.add(this.socketService.onAlertUpdated().subscribe((a) => this.onAlert(a)));
    this.subs.add(
      this.socketService.onAlertCleared().subscribe((a) => {
        this.criticalAlerts.delete(a.alertId);
        this.sync();
      }),
    );
  }

  private wirePollingFallback(): void {
    this.subs.add(
      this.connected$
        .pipe(
          switchMap((connected) =>
            connected
              ? EMPTY
              : interval(10_000).pipe(
                  startWith(0),
                  switchMap(() => this.api.getAlerts('ACTIVE')),
                ),
          ),
        )
        .subscribe((alerts) => {
          this.criticalAlerts.clear();
          alerts.filter((a) => a.level === 'CRITICAL').forEach((a) => this.criticalAlerts.set(a.alertId, a));
          this.sync();
        }),
    );
  }

  private onAlert(alert: Alert): void {
    if (alert.level === 'CRITICAL' && alert.status === 'ACTIVE') {
      this.criticalAlerts.set(alert.alertId, alert);
    } else {
      this.criticalAlerts.delete(alert.alertId);
    }
    this.sync();
  }

  private sync(): void {
    this.criticalCount = this.criticalAlerts.size;
    this.audioAlarm.setAlarm(this.criticalCount > 0);
  }
}
