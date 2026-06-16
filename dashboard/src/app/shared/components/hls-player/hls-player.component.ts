import { AfterViewInit, Component, ElementRef, Input, OnChanges, OnDestroy, SimpleChanges, ViewChild } from '@angular/core';
import { NgIf } from '@angular/common';
import Hls from 'hls.js';

/** Plays an HLS stream (e.g. MediaMTX's `:8888/<path>/index.m3u8`) in a <video>
 * element, using hls.js where needed and native HLS on Safari. */
@Component({
  selector: 'app-hls-player',
  imports: [NgIf],
  templateUrl: './hls-player.component.html',
})
export class HlsPlayerComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input({ required: true }) src!: string;

  @ViewChild('video') private readonly videoRef!: ElementRef<HTMLVideoElement>;

  muted = true;

  private hls: Hls | null = null;

  ngAfterViewInit(): void {
    this.attach();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['src'] && this.videoRef) {
      this.attach();
    }
  }

  toggleMute(): void {
    this.muted = !this.muted;
    this.videoRef.nativeElement.muted = this.muted;
  }

  ngOnDestroy(): void {
    this.hls?.destroy();
  }

  private attach(): void {
    const video = this.videoRef.nativeElement;
    this.hls?.destroy();
    this.hls = null;

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
}
