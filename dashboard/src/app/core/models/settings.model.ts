export interface DetectionSettings {
  fireThreshold: number;
  smokeThreshold: number;
  debounceFrames: number;
  cooldownSeconds: number;
}

export type DetectionSettingsUpdate = Partial<DetectionSettings>;
