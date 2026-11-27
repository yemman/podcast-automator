import {
  Component,
  Input,
  ElementRef,
  ViewChild,
  signal,
  inject,
  PLATFORM_ID,
  OnChanges,
  SimpleChanges
} from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

@Component({
  selector: 'app-audio-player',
  standalone: true,
  template: `
    <div class="rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-800 p-4 sm:p-6 shadow-xl">
      <!-- Standard HTML5 Audio Tag (Ensures SEO crawlability and native fallback) -->
      <audio
        #audioElement
        [src]="audioUrl"
        preload="metadata"
        (timeupdate)="onTimeUpdate()"
        (loadedmetadata)="onLoadedMetadata()"
        (ended)="onEnded()"
        (play)="isPlaying.set(true)"
        (pause)="isPlaying.set(false)"
        class="w-full mb-4 accent-indigo-500 rounded-lg"
        controls
      >
        Your browser does not support the audio element.
      </audio>

      <!-- Custom Enhanced Audio Controls Bar -->
      <div class="flex flex-col gap-4 mt-2">
        <!-- Progress Bar & Timestamps -->
        <div class="space-y-1.5">
          <div class="relative w-full h-2 bg-slate-800 rounded-full cursor-pointer overflow-hidden group" (click)="seek($event)">
            <div
              class="absolute top-0 left-0 h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all group-hover:from-indigo-400 group-hover:to-purple-400"
              [style.width.%]="progressPercent()"
            ></div>
          </div>
          <div class="flex justify-between items-center text-xs font-mono text-slate-400">
            <span>{{ formatTime(currentTime()) }}</span>
            <span class="text-indigo-400 font-semibold">{{ episodeTitle || 'Audio Track' }}</span>
            <span>{{ formatTime(duration()) }}</span>
          </div>
        </div>

        <!-- Control Buttons -->
        <div class="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-800/80">
          <!-- Playback controls -->
          <div class="flex items-center gap-2">
            <!-- Skip Backward 15s -->
            <button
              (click)="skip(-15)"
              title="Rewind 15 seconds"
              class="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0019 16V8a1 1 0 00-1.6-.8l-5.334 4zM4.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0011 16V8a1 1 0 00-1.6-.8l-5.334 4z" />
              </svg>
            </button>

            <!-- Big Play / Pause -->
            <button
              (click)="togglePlay()"
              class="w-11 h-11 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center shadow-lg shadow-indigo-600/30 transition-transform active:scale-95"
            >
              @if (isPlaying()) {
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path fill-rule="evenodd" clip-rule="evenodd" d="M6.75 5.25a.75.75 0 01.75.75v12a.75.75 0 01-1.5 0v-12a.75.75 0 01.75-.75zm10.5 0a.75.75 0 01.75.75v12a.75.75 0 01-1.5 0v-12a.75.75 0 01.75-.75z" />
                </svg>
              } @else {
                <svg class="w-5 h-5 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                  <path fill-rule="evenodd" clip-rule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z" />
                </svg>
              }
            </button>

            <!-- Skip Forward 15s -->
            <button
              (click)="skip(15)"
              title="Fast forward 15 seconds"
              class="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.933 12.8a1 1 0 000-1.6L6.6 7.2A1 1 0 005 8v8a1 1 0 001.6.8l5.333-4zM19.933 12.8a1 1 0 000-1.6l-5.333-4A1 1 0 0013 8v8a1 1 0 001.6.8l5.333-4z" />
              </svg>
            </button>
          </div>

          <!-- Secondary controls: Speed & Volume & Direct Download -->
          <div class="flex items-center gap-3">
            <!-- Speed Switcher -->
            <button
              (click)="cyclePlaybackSpeed()"
              class="px-2.5 py-1 text-xs font-semibold rounded-md bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 transition-colors border border-slate-700"
            >
              {{ playbackRate() }}x
            </button>

            <!-- Direct Download Enclosure -->
            <a
              [href]="audioUrl"
              download
              target="_blank"
              rel="noopener noreferrer"
              title="Download original audio file"
              class="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-md bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 transition-colors border border-slate-700"
            >
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              <span>Download</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  `
})
export class AudioPlayerComponent implements OnChanges {
  @Input({ required: true }) audioUrl!: string;
  @Input() episodeTitle: string = '';

  @ViewChild('audioElement') audioRef?: ElementRef<HTMLAudioElement>;

  private readonly platformId = inject(PLATFORM_ID);
  private readonly isBrowser = isPlatformBrowser(this.platformId);

  // Reactive State Signals
  readonly isPlaying = signal<boolean>(false);
  readonly currentTime = signal<number>(0);
  readonly duration = signal<number>(0);
  readonly playbackRate = signal<number>(1);
  readonly progressPercent = signal<number>(0);

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['audioUrl'] && !changes['audioUrl'].firstChange) {
      this.isPlaying.set(false);
      this.currentTime.set(0);
      this.progressPercent.set(0);
    }
  }

  togglePlay(): void {
    if (!this.isBrowser || !this.audioRef) return;
    const audio = this.audioRef.nativeElement;
    if (audio.paused) {
      audio.play().catch(e => console.warn('Audio play request interrupted:', e));
    } else {
      audio.pause();
    }
  }

  skip(seconds: number): void {
    if (!this.isBrowser || !this.audioRef) return;
    const audio = this.audioRef.nativeElement;
    audio.currentTime = Math.max(0, Math.min(audio.currentTime + seconds, audio.duration || 0));
  }

  seek(event: MouseEvent): void {
    if (!this.isBrowser || !this.audioRef) return;
    const audio = this.audioRef.nativeElement;
    const bar = event.currentTarget as HTMLElement;
    const rect = bar.getBoundingClientRect();
    const clickX = event.clientX - rect.left;
    const percent = Math.max(0, Math.min(1, clickX / rect.width));
    if (audio.duration) {
      audio.currentTime = percent * audio.duration;
    }
  }

  cyclePlaybackSpeed(): void {
    if (!this.isBrowser || !this.audioRef) return;
    const speeds = [1, 1.25, 1.5, 2];
    const current = this.playbackRate();
    const next = speeds[(speeds.indexOf(current) + 1) % speeds.length];
    this.playbackRate.set(next);
    this.audioRef.nativeElement.playbackRate = next;
  }

  onTimeUpdate(): void {
    if (!this.isBrowser || !this.audioRef) return;
    const audio = this.audioRef.nativeElement;
    this.currentTime.set(audio.currentTime);
    if (audio.duration) {
      this.progressPercent.set((audio.currentTime / audio.duration) * 100);
    }
  }

  onLoadedMetadata(): void {
    if (!this.isBrowser || !this.audioRef) return;
    const audio = this.audioRef.nativeElement;
    this.duration.set(audio.duration || 0);
  }

  onEnded(): void {
    this.isPlaying.set(false);
    this.progressPercent.set(100);
  }

  formatTime(secs: number): string {
    if (isNaN(secs) || secs < 0) return '00:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    const mm = m < 10 ? `0${m}` : `${m}`;
    const ss = s < 10 ? `0${s}` : `${s}`;
    return `${mm}:${ss}`;
  }
}
