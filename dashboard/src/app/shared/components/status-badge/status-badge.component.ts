import { Component, Input } from '@angular/core';

export type StatusBadgeVariant = 'online' | 'offline' | 'critical' | 'warning' | 'info';

const VARIANT_CLASSES: Record<StatusBadgeVariant, string> = {
  online: 'bg-emerald-100 text-emerald-800 ring-emerald-600/20',
  offline: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  critical: 'bg-red-100 text-red-800 ring-red-600/20',
  warning: 'bg-amber-100 text-amber-800 ring-amber-600/20',
  info: 'bg-blue-100 text-blue-800 ring-blue-600/20',
};

@Component({
  selector: 'app-status-badge',
  imports: [],
  templateUrl: './status-badge.component.html',
})
export class StatusBadgeComponent {
  @Input() label = '';
  @Input() variant: StatusBadgeVariant = 'info';

  get variantClasses(): string {
    return VARIANT_CLASSES[this.variant];
  }
}
