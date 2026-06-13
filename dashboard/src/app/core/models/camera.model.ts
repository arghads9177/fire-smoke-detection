export interface CameraState {
  fire: boolean;
  smoke: boolean;
  confidence: number;
  lastEventAt: string | null;
}

export interface Camera {
  cameraId: string;
  name: string;
  location: string;
  streamUrl: string;
  status: 'ONLINE' | 'OFFLINE';
  lastHeartbeat: string | null;
  currentState: CameraState;
}
