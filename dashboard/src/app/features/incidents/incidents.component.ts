import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { environment } from '../../../environments/environment';
import { ApiService } from '../../core/services/api.service';
import { DetectionType, Incident, IncidentListResponse } from '../../core/models';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';

const PAGE_SIZE = 20;

@Component({
  selector: 'app-incidents',
  imports: [DatePipe, DecimalPipe, FormsModule, StatusBadgeComponent],
  templateUrl: './incidents.component.html',
})
export class IncidentsComponent implements OnInit {
  items: Incident[] = [];
  total = 0;
  page = 1;
  readonly pageSize = PAGE_SIZE;

  cameraIdFilter = '';
  typeFilter: DetectionType | '' = '';

  selectedIncident: Incident | null = null;

  constructor(private readonly api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  get totalPages(): number {
    return Math.max(1, Math.ceil(this.total / this.pageSize));
  }

  applyFilters(): void {
    this.page = 1;
    this.load();
  }

  goToPage(page: number): void {
    if (page < 1 || page > this.totalPages) {
      return;
    }
    this.page = page;
    this.load();
  }

  openSnapshot(incident: Incident): void {
    this.selectedIncident = incident;
  }

  closeSnapshot(): void {
    this.selectedIncident = null;
  }

  snapshotSrc(incident: Incident): string {
    return `${environment.backendOrigin}${incident.snapshotUrl}`;
  }

  private load(): void {
    this.api
      .getIncidents({
        cameraId: this.cameraIdFilter || undefined,
        type: this.typeFilter || undefined,
        page: this.page,
        pageSize: this.pageSize,
      })
      .subscribe((response: IncidentListResponse) => {
        this.items = response.items;
        this.total = response.total;
        this.page = response.page;
      });
  }
}
