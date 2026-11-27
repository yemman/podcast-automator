import { Component, OnInit, OnDestroy, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { EpisodeService } from '../../services/episode.service';
import { SeoService } from '../../services/seo.service';
import { Episode } from '../../models/episode.model';
import { AudioPlayerComponent } from '../../components/audio-player/audio-player.component';

@Component({
  selector: 'app-episode-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, AudioPlayerComponent],
  template: `
    @if (loading()) {
      <div class="max-w-4xl mx-auto px-4 py-20 text-center">
        <div class="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-indigo-500 mb-4"></div>
        <p class="text-slate-400 font-mono text-sm">Loading episode metadata & transcript...</p>
      </div>
    } @else if (episode(); as ep) {
      <article class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12">
        <!-- Breadcrumb Navigation -->
        <nav class="flex items-center gap-2 text-xs text-slate-400 mb-6">
          <a routerLink="/" class="hover:text-indigo-400 transition-colors flex items-center gap-1">
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            All Episodes
          </a>
          <span class="text-slate-600">/</span>
          <span class="text-slate-300 truncate max-w-xs">{{ ep.title }}</span>
        </nav>

        <!-- Episode Header -->
        <header class="mb-8">
          <div class="flex flex-wrap items-center gap-2 mb-3">
            <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              {{ ep.podcastTitle }}
            </span>
            <span class="text-xs text-slate-400">
              Published on {{ formatDate(ep.publishedAt) }}
            </span>
            @if (ep.duration) {
              <span class="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                ⏱ {{ ep.duration }}
              </span>
            }
            <span class="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
              ✓ Local AI Enriched (ivrit-ai + Ollama)
            </span>
          </div>

          <h1 dir="auto" class="text-2xl sm:text-4xl font-extrabold tracking-tight text-white mb-4 leading-tight">
            {{ ep.title }}
          </h1>

          @if (ep.podcastAuthor) {
            <p dir="auto" class="text-sm text-slate-400 mb-6">
              מאת / שיעור מאת <span class="text-slate-200 font-medium">{{ ep.podcastAuthor }}</span>
            </p>
          }
        </header>

        <!-- HTML5 Audio Player Card -->
        <section class="mb-10" aria-label="Audio Player">
          <app-audio-player
            [audioUrl]="ep.audioUrl"
            [episodeTitle]="ep.title"
          />
        </section>

        <!-- 2-Paragraph Summary Card (Local Ollama Summary) -->
        <section class="mb-10 rounded-2xl bg-slate-900/90 border border-indigo-500/30 p-6 sm:p-8 relative overflow-hidden shadow-lg shadow-indigo-950/20">
          <div class="absolute -top-12 -right-12 w-40 h-40 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>

          <div class="flex items-center gap-2 mb-4">
            <div class="w-6 h-6 rounded-md bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white text-xs">
              ✨
            </div>
            <h2 class="text-sm font-bold uppercase tracking-wider text-indigo-300">
              תמצית הפרק (Local AI Summary)
            </h2>
          </div>

          <div dir="auto" class="prose prose-invert prose-slate max-w-none space-y-4 text-slate-200 leading-relaxed text-sm sm:text-base">
            @for (para of summaryParagraphs(); track $index) {
              <p class="leading-relaxed">{{ para }}</p>
            }
          </div>

          <!-- SEO Keywords / Tags -->
          <div class="mt-6 pt-6 border-t border-slate-800/80 flex flex-wrap items-center gap-2">
            <span class="text-xs font-semibold text-slate-400 mr-1">מילות מפתח / SEO:</span>
            @for (kw of ep.keywords; track kw) {
              <span class="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-slate-800 text-indigo-300 hover:bg-slate-700 transition-colors">
                #{{ kw }}
              </span>
            }
          </div>
        </section>

        <!-- Verbatim Transcript Section -->
        <section class="rounded-2xl bg-slate-900/60 border border-slate-800 p-6 sm:p-8">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-6 border-b border-slate-800">
            <div>
              <h2 class="text-xl font-bold text-white flex items-center gap-2">
                <span>תמלול מקומי (ivrit-ai Whisper)</span>
                <span class="px-2 py-0.5 rounded text-xs font-mono font-normal bg-indigo-500/20 text-indigo-300">
                  Full Text
                </span>
              </h2>
              <p class="text-xs text-slate-400 mt-1">
                תמלול רציף שהופק מקומית מקובץ השמע באמצעות faster-whisper (ivrit-ai)
              </p>
            </div>

            <div class="flex items-center gap-3">
              <!-- Copy Transcript Button -->
              <button
                (click)="copyTranscript()"
                class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-all active:scale-95"
              >
                @if (copied()) {
                  <svg class="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                  </svg>
                  <span class="text-emerald-400">הועתק! (Copied)</span>
                } @else {
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                  </svg>
                  <span>העתק תמלול</span>
                }
              </button>
            </div>
          </div>

          <!-- Transcript Search Filter -->
          <div class="mb-6">
            <div class="relative">
              <input
                type="text"
                [value]="transcriptQuery()"
                (input)="onTranscriptSearch($event)"
                placeholder="חיפוש מילים או מושגים בתוך התמלול..."
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 pl-10 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
              />
              <svg class="w-4 h-4 text-slate-500 absolute left-3.5 top-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              @if (transcriptQuery()) {
                <span class="absolute right-3.5 top-3 text-xs text-indigo-400 font-medium">
                  {{ matchCount() }} תוצאות
                </span>
              }
            </div>
          </div>

          <!-- Transcript Content -->
          <div dir="auto" class="custom-scrollbar max-h-[600px] overflow-y-auto space-y-4 pr-2 text-slate-300 text-sm leading-relaxed font-sans">
            @for (segment of formattedTranscript(); track $index) {
              <div class="p-3.5 rounded-lg bg-slate-950/40 border border-slate-800/40 hover:border-slate-700/60 transition-colors">
                <p [innerHTML]="segment"></p>
              </div>
            }
          </div>
        </section>

        <!-- Back to Catalog -->
        <div class="mt-12 text-center">
          <a routerLink="/" class="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 text-sm font-semibold border border-slate-800 transition-colors shadow-sm">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Explore More Episodes
          </a>
        </div>
      </article>
    } @else {
      <div class="max-w-4xl mx-auto px-4 py-20 text-center">
        <h2 class="text-2xl font-bold text-white mb-2">Episode Not Found</h2>
        <p class="text-slate-400 mb-6">The requested podcast episode could not be found in the static episode catalog.</p>
        <a routerLink="/" class="inline-flex items-center px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 transition-colors">
          Return to Episodes
        </a>
      </div>
    }
  `
})
export class EpisodeDetailComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly episodeService = inject(EpisodeService);
  private readonly seoService = inject(SeoService);
  private paramSub?: Subscription;

  readonly episode = signal<Episode | null>(null);
  readonly loading = signal<boolean>(true);
  readonly copied = signal<boolean>(false);
  readonly transcriptQuery = signal<string>('');

  readonly summaryParagraphs = computed(() => {
    const ep = this.episode();
    if (!ep || !ep.summary) return [];
    return ep.summary.split(/\n\s*\n/).filter(p => p.trim().length > 0);
  });

  readonly formattedTranscript = computed(() => {
    const ep = this.episode();
    if (!ep || !ep.transcript) return [];

    const raw = ep.transcript.split(/\n\s*\n/).filter(p => p.trim().length > 0);
    const query = this.transcriptQuery().trim().toLowerCase();

    if (!query) {
      return raw.map(p => this.escapeHtml(p));
    }

    return raw.map(p => {
      const escaped = this.escapeHtml(p);
      const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
      return escaped.replace(regex, '<mark class="bg-indigo-500/40 text-white px-1 rounded font-semibold">$1</mark>');
    });
  });

  readonly matchCount = computed(() => {
    const ep = this.episode();
    const query = this.transcriptQuery().trim().toLowerCase();
    if (!ep || !ep.transcript || !query) return 0;
    const matches = ep.transcript.toLowerCase().match(new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'));
    return matches ? matches.length : 0;
  });

  ngOnInit(): void {
    const initialId = this.route.snapshot.paramMap.get('id');
    void this.loadEpisode(initialId);

    this.paramSub = this.route.paramMap.subscribe(params => {
      const id = params.get('id');
      if (id && id !== this.episode()?.id) {
        void this.loadEpisode(id);
      }
    });
  }

  ngOnDestroy(): void {
    this.paramSub?.unsubscribe();
  }

  private async loadEpisode(id: string | null): Promise<void> {
    if (!id) {
      this.loading.set(false);
      return;
    }

    this.loading.set(true);
    const found = await this.episodeService.getEpisodeById(id);
    this.episode.set(found);
    this.loading.set(false);

    if (found) {
      this.seoService.setEpisodeSeo(found);
    }
  }

  onTranscriptSearch(event: Event): void {
    const val = (event.target as HTMLInputElement).value;
    this.transcriptQuery.set(val);
  }

  copyTranscript(): void {
    const ep = this.episode();
    if (!ep || !ep.transcript) return;

    if (navigator.clipboard) {
      navigator.clipboard.writeText(ep.transcript).then(() => {
        this.copied.set(true);
        setTimeout(() => this.copied.set(false), 2500);
      });
    }
  }

  formatDate(dateStr: string): string {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateStr;
    }
  }

  private escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}
