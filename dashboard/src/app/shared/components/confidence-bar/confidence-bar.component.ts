import { Component, Input } from '@angular/core';
import { PercentPipe } from '@angular/common';

@Component({
  selector: 'app-confidence-bar',
  imports: [PercentPipe],
  templateUrl: './confidence-bar.component.html',
})
export class ConfidenceBarComponent {
  /** Confidence value between 0 and 1. */
  @Input() confidence = 0;

  get fillClasses(): string {
    if (this.confidence >= 0.8) {
      return 'bg-red-500';
    }
    if (this.confidence >= 0.5) {
      return 'bg-amber-500';
    }
    return 'bg-emerald-500';
  }
}
