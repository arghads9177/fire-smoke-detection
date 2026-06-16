import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class AudioAlarmService {
  private audioCtx: AudioContext | null = null;
  private gainNode: GainNode | null = null;
  private oscillator: OscillatorNode | null = null;
  private pulseInterval: ReturnType<typeof setInterval> | null = null;

  private _audioEnabled = false;
  private _alarmActive = false;

  get audioEnabled(): boolean {
    return this._audioEnabled;
  }

  get alarmActive(): boolean {
    return this._alarmActive;
  }

  /** Call on a user-gesture (click) to satisfy the browser autoplay policy. */
  enable(): void {
    if (this._audioEnabled) return;
    this.audioCtx = new AudioContext();
    this._audioEnabled = true;
    // If the alarm was already requested before audio was enabled, start it now.
    if (this._alarmActive) {
      this.startTone();
    }
  }

  /** Turn the alarm on or off. Safe to call before enable(). */
  setAlarm(active: boolean): void {
    if (active === this._alarmActive) return;
    this._alarmActive = active;
    if (active && this._audioEnabled) {
      this.startTone();
    } else if (!active) {
      this.stopTone();
    }
  }

  private startTone(): void {
    if (!this.audioCtx) return;
    this.stopTone(); // clean up any previous tone

    this.gainNode = this.audioCtx.createGain();
    this.gainNode.gain.value = 0;
    this.gainNode.connect(this.audioCtx.destination);

    this.oscillator = this.audioCtx.createOscillator();
    this.oscillator.type = 'square';
    this.oscillator.frequency.value = 880;
    this.oscillator.connect(this.gainNode);
    this.oscillator.start();

    // Pulse: 400ms on / 400ms off
    let on = false;
    this.pulseInterval = setInterval(() => {
      if (!this.gainNode || !this.audioCtx) return;
      on = !on;
      this.gainNode.gain.setTargetAtTime(on ? 0.3 : 0, this.audioCtx.currentTime, 0.02);
    }, 400);
  }

  private stopTone(): void {
    if (this.pulseInterval !== null) {
      clearInterval(this.pulseInterval);
      this.pulseInterval = null;
    }
    if (this.oscillator) {
      try {
        this.oscillator.stop();
        this.oscillator.disconnect();
      } catch {
        // already stopped
      }
      this.oscillator = null;
    }
    if (this.gainNode) {
      this.gainNode.disconnect();
      this.gainNode = null;
    }
  }
}
