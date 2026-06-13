import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./features/monitoring/monitoring.component').then((m) => m.MonitoringComponent),
  },
  {
    path: 'alerts',
    loadComponent: () =>
      import('./features/alerts/alerts.component').then((m) => m.AlertsComponent),
  },
  {
    path: 'incidents',
    loadComponent: () =>
      import('./features/incidents/incidents.component').then((m) => m.IncidentsComponent),
  },
  { path: '**', redirectTo: '' },
];
