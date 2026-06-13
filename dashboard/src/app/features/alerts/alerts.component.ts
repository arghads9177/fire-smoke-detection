import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subscription } from 'rxjs';

import { ApiService } from '../../core/services/api.service';
import { SocketService } from '../../core/services/socket.service';
import { Alert } from '../../core/models';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-alerts',
  imports: [StatusBadgeComponent, DatePipe, DecimalPipe],
  templateUrl: './alerts.component.html',
})
export class AlertsComponent implements OnInit, OnDestroy {
  alerts: Alert[] = [];

  private readonly subscriptions = new Subscription();

  constructor(
    private readonly api: ApiService,
    private readonly socket: SocketService,
  ) {}

  ngOnInit(): void {
    this.refresh();

    this.subscriptions.add(this.socket.onAlertNew().subscribe((alert) => this.upsert(alert)));
    this.subscriptions.add(
      this.socket.onAlertUpdated().subscribe((alert) => this.upsert(alert)),
    );
    this.subscriptions.add(
      this.socket.onAlertCleared().subscribe((alert) => this.remove(alert)),
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.unsubscribe();
  }

  acknowledge(alert: Alert): void {
    this.api.acknowledgeAlert(alert.alertId).subscribe((updated) => this.upsert(updated));
  }

  rowClasses(alert: Alert): string {
    return alert.level === 'CRITICAL'
      ? 'border-red-300 bg-red-50'
      : 'border-amber-300 bg-amber-50';
  }

  private refresh(): void {
    this.api.getAlerts('ACTIVE').subscribe((alerts) => (this.alerts = alerts));
  }

  private upsert(alert: Alert): void {
    if (alert.status !== 'ACTIVE') {
      this.remove(alert);
      return;
    }
    const index = this.alerts.findIndex((a) => a.alertId === alert.alertId);
    if (index === -1) {
      this.alerts = [alert, ...this.alerts];
    } else {
      this.alerts = this.alerts.map((a, i) => (i === index ? alert : a));
    }
  }

  private remove(alert: Alert): void {
    this.alerts = this.alerts.filter((a) => a.alertId !== alert.alertId);
  }
}
