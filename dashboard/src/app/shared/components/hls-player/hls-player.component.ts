import { AfterViewInit, Component, ElementRef, Input, OnChanges, OnDestroy, SimpleChanges, ViewChild } from '@angular/core';
import { NgIf } from '@angular/common';
import Hls from 'hls.js';

/** Plays a MediaMTX stream in a <video> element.
 *
 * When `whepUrl` is provided the component negotiates a WHEP/WebRTC session
 * directly (sub-100ms latency — used for the live phone camera).  Otherwise
 * it falls back to hls.js for HLS (used for simulator cams whose B-frame
 * H264 WebRTC rejects). */
@Component({
  selector: 'app-hls-player',
  imports: [NgIf],
  templateUrl: './hls-player.component.html',
})
export class HlsPlayerComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input({ required: true }) src!: string;
  /** WHEP endpoint (e.g. http://host:8889/<path>/whep). When set, WebRTC is
   * used instead of HLS. */
  @Input() whepUrl: string | null = null;

  @ViewChild('video') private readonly videoRef!: ElementRef<HTMLVideoElement>;

  muted = true;

  private hls: Hls | null = null;
  private pc: RTCPeerConnection | null = null;

  ngAfterViewInit(): void {
    this.attach();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if ((changes['src'] || changes['whepUrl']) && this.videoRef) {
      this.attach();
    }
  }

  ngOnDestroy(): void {
    this.teardown();
  }

  toggleMute(): void {
    this.muted = !this.muted;
    this.videoRef.nativeElement.muted = this.muted;
  }

  private attach(): void {
    this.teardown();
    if (this.whepUrl) {
      this.attachWhep(this.whepUrl);
    } else {
      this.attachHls();
    }
  }

  private async attachWhep(endpoint: string): Promise<void> {
    const video = this.videoRef.nativeElement;
    const pc = new RTCPeerConnection();
    this.pc = pc;

    pc.ontrack = (e) => {
      if (e.streams[0]) {
        video.srcObject = e.streams[0];
        video.muted = this.muted;
        video.play().catch(() => {/* autoplay blocked — user interaction needed */});
      }
    };

    pc.addTransceiver('video', { direction: 'recvonly' });
    pc.addTransceiver('audio', { direction: 'recvonly' });

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    try {
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/sdp' },
        body: pc.localDescription!.sdp,
      });
      if (!resp.ok) return;
      const sdp = await resp.text();
      await pc.setRemoteDescription({ type: 'answer', sdp });
    } catch {
      // Phone not yet streaming — component will re-attach on next src/whepUrl change
    }
  }

  private attachHls(): void {
    const video = this.videoRef.nativeElement;
    if (Hls.isSupported()) {
      this.hls = new Hls();
      this.hls.loadSource(this.src);
      this.hls.attachMedia(video);
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = this.src;
    }
    // hls.js resets the muted DOM property when attaching media; re-apply here.
    video.muted = this.muted;
  }

  private teardown(): void {
    this.hls?.destroy();
    this.hls = null;
    this.pc?.close();
    this.pc = null;
    const video = this.videoRef?.nativeElement;
    if (video) {
      video.srcObject = null;
    }
  }
}
