import { DatePipe } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subscription } from 'rxjs';

import { ApiService } from '../../core/services/api.service';
import { SocketService } from '../../core/services/socket.service';
import { Camera } from '../../core/models';
import { ConfidenceBarComponent } from '../../shared/components/confidence-bar/confidence-bar.component';
import { HlsPlayerComponent } from '../../shared/components/hls-player/hls-player.component';
import { StatusBadgeComponent, StatusBadgeVariant } from '../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-monitoring',
  imports: [StatusBadgeComponent, ConfidenceBarComponent, HlsPlayerComponent, DatePipe],
  templateUrl: './monitoring.component.html',
})
export class MonitoringComponent implements OnInit, OnDestroy {
  cameras: Camera[] = [];
  uploadingCameraId: string | null = null;
  uploadError: string | null = null;
  connectingCameraId: string | null = null;

  /** RTMP target a phone broadcaster (e.g. Larix) should publish to.
   * Defaults to the page's hostname, then refined to the server's LAN IP
   * once /system/info responds — `window.location.hostname` is "localhost"
   * when the dashboard is opened locally, which a phone can't reach. */
  phoneRtmpUrl = `rtmp://${window.location.hostname}:1935/phonecam/live`;

  private readonly subscriptions = new Subscription();

  constructor(
    private readonly api: ApiService,
    private readonly socket: SocketService,
  ) {}

  ngOnInit(): void {
    this.api.getCameras().subscribe((cameras) => (this.cameras = cameras));

    this.api.getSystemInfo().subscribe({
      next: ({ lanIp }) => (this.phoneRtmpUrl = `rtmp://${lanIp}:1935/phonecam/live`),
      error: () => {
        // keep the window.location.hostname fallback
      },
    });

    this.subscriptions.add(
      this.socket.onCameraStatus().subscribe((update) => this.upsertCamera(update)),
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.unsubscribe();
  }

  cardVariant(camera: Camera): 'critical' | 'warning' | 'normal' {
    if (camera.currentState.fire) {
      return 'critical';
    }
    if (camera.currentState.smoke) {
      return 'warning';
    }
    return 'normal';
  }

  statusVariant(camera: Camera): StatusBadgeVariant {
    return camera.status === 'ONLINE' ? 'online' : 'offline';
  }

  /** WHEP (WebRTC) endpoint for a camera, or null if the stream uses HLS.
   *
   * Phone cameras (Larix → RTMP → MediaMTX) encode H.264 Baseline without
   * B-frames, so WebRTC works and gives sub-100ms latency. Simulator cams use
   * B-frame H264 which WebRTC rejects, so they fall through to hlsUrl(). */
  whepUrl(camera: Camera): string | null {
    const match = camera.streamUrl.match(/^rtsp:\/\/[^/]+\/(.+)$/);
    if (!match) return null;
    const path = match[1];
    // Only use WHEP for streams that come in via RTMP (phone camera paths)
    return path.includes('phonecam') ? `http://${window.location.hostname}:8889/${path}/whep` : null;
  }

  /** HLS playlist URL — fallback for cameras whose H264 has B-frames (simulator). */
  hlsUrl(camera: Camera): string {
    const match = camera.streamUrl.match(/^rtsp:\/\/[^/]+\/(.+)$/);
    const path = match ? match[1] : camera.cameraId;
    return `http://${window.location.hostname}:8888/${path}/index.m3u8`;
  }

  cardClasses(camera: Camera): string {
    switch (this.cardVariant(camera)) {
      case 'critical':
        return 'border-red-400 bg-red-50 ring-1 ring-red-200';
      case 'warning':
        return 'border-amber-400 bg-amber-50 ring-1 ring-amber-200';
      default:
        return 'border-slate-200 bg-white';
    }
  }

  uploadFeed(camera: Camera, event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) {
      return;
    }

    this.uploadingCameraId = camera.cameraId;
    this.uploadError = null;
    this.api.uploadFeed(camera.cameraId, file).subscribe({
      next: (updated) => {
        this.upsertCamera(updated);
        this.uploadingCameraId = null;
      },
      error: (err) => {
        this.uploadError = `Upload failed for ${camera.name}: ${err.error?.detail ?? err.message}`;
        this.uploadingCameraId = null;
      },
    });
    input.value = '';
  }

  connectPhone(camera: Camera): void {
    this.connectingCameraId = camera.cameraId;
    this.uploadError = null;
    this.api.setStreamUrl(camera.cameraId, 'rtsp://localhost:8554/phonecam/live').subscribe({
      next: (updated) => {
        this.upsertCamera(updated);
        this.connectingCameraId = null;
      },
      error: (err) => {
        this.uploadError = `Failed to connect phone feed for ${camera.name}: ${err.error?.detail ?? err.message}`;
        this.connectingCameraId = null;
      },
    });
  }

  private upsertCamera(update: Camera): void {
    const index = this.cameras.findIndex((c) => c.cameraId === update.cameraId);
    if (index === -1) {
      this.cameras = [...this.cameras, update];
    } else {
      this.cameras = this.cameras.map((c, i) => (i === index ? update : c));
    }
  }
}
