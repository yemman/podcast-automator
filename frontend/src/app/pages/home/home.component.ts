import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { EpisodeService } from '../../services/episode.service';
import { SeoService } from '../../services/seo.service';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
      <!-- Hero Section -->
      <section class="text-center max-w-3xl mx-auto mb-12 sm:mb-16">
        <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 mb-4">
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          100% Local AI (ivrit-ai + Ollama) • Static Angular SSG
        </div>

        <div class="flex flex-col sm:flex-row items-center justify-center gap-6 mb-6">
          <img
            src="https://d3t3ozftmdmh3i.cloudfront.net/staging/podcast_uploaded_nologo/38820759/38820759-1693120060958-6e29115094b23.jpg"
            alt="מי האיש החפץ חיים - עטיפת הפודקאסט"
            class="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl shadow-xl shadow-indigo-950/40 border border-slate-700 object-cover"
          />
          <div class="text-center sm:text-right">
            <h1 dir="auto" class="text-3xl sm:text-4xl font-black tracking-tight text-white mb-2">
              מי האיש החפץ חיים
            </h1>
            <p dir="auto" class="text-sm sm:text-base text-slate-300">
              שיעורי הרב ינאי בספר "חפץ חיים" • בית הכנסת תפארת ישראל, רמת גן
            </p>
            <p class="text-xs text-indigo-400 font-mono mt-1">
              Local Whisper Transcription &amp; Static SSG on Firebase Hosting
            </p>
          </div>
        </div>

        <!-- Search Bar -->
        <div class="mt-4 max-w-xl mx-auto">
          <div class="relative">
            <input
              type="text"
              [value]="episodeService.searchQuery()"
              (input)="onSearchChange($event)"
              placeholder="חיפוש שיעורים, נושאים, או מילות מפתח מתוך התמלול..."
              class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-5 py-3.5 pl-11 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 shadow-xl shadow-indigo-950/20 transition-all text-right"
              dir="auto"
            />
            <svg class="w-5 h-5 text-slate-400 absolute left-4 top-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>

        <!-- Keyword Filter Pills -->
        <div class="mt-6 flex flex-wrap items-center justify-center gap-2">
          <button
            (click)="selectKeyword(null)"
            [class.bg-indigo-600]="episodeService.selectedKeyword() === null"
            [class.text-white]="episodeService.selectedKeyword() === null"
            [class.bg-slate-900]="episodeService.selectedKeyword() !== null"
            [class.text-slate-400]="episodeService.selectedKeyword() !== null"
            class="px-3 py-1 rounded-full text-xs font-semibold border border-slate-800 transition-colors hover:text-white"
          >
            כל השיעורים (All Topics)
          </button>
          @for (keyword of episodeService.allKeywords(); track keyword) {
            <button
              (click)="selectKeyword(keyword)"
              [class.bg-indigo-600]="episodeService.selectedKeyword() === keyword"
              [class.text-white]="episodeService.selectedKeyword() === keyword"
              [class.bg-slate-900]="episodeService.selectedKeyword() !== keyword"
              [class.text-slate-400]="episodeService.selectedKeyword() !== keyword"
              class="px-3 py-1 rounded-full text-xs font-semibold border border-slate-800 transition-colors hover:text-white"
            >
              #{{ keyword }}
            </button>
          }
        </div>
      </section>

      <!-- Episode Grid -->
      <section class="space-y-6">
        <div class="flex items-center justify-between pb-4 border-b border-slate-800">
          <h2 class="text-xl font-bold text-white flex items-center gap-2">
            <span>פרקים אחרונים</span>
            <span class="text-xs font-mono font-normal px-2 py-0.5 rounded bg-slate-800 text-slate-400">
              {{ episodeService.filteredEpisodes().length }} שיעורים
            </span>
          </h2>
        </div>

        @if (episodeService.loading()) {
          <div class="py-16 text-center text-slate-400">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-indigo-500 mb-2"></div>
            <p class="text-xs">Loading episodes catalog...</p>
          </div>
        } @else if (episodeService.filteredEpisodes().length === 0) {
          <div class="py-16 text-center bg-slate-900/40 rounded-2xl border border-slate-800">
            <p class="text-slate-400 text-sm mb-3">לא נמצאו פרקים התואמים את החיפוש.</p>
            <button
              (click)="resetFilters()"
              class="px-4 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 transition-colors"
            >
              אפס סינונים (Reset Filters)
            </button>
          </div>
        } @else {
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            @for (episode of episodeService.filteredEpisodes(); track episode.id) {
              <article class="flex flex-col rounded-2xl bg-slate-900/60 border border-slate-800/80 overflow-hidden hover:border-indigo-500/50 hover:shadow-xl hover:shadow-indigo-950/30 transition-all group">
                <!-- Card Image Thumbnail -->
                <div class="relative h-48 w-full bg-slate-950 overflow-hidden">
                  @if (episode.imageUrl) {
                    <img
                      [src]="episode.imageUrl"
                      [alt]="episode.title"
                      loading="lazy"
                      class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                  } @else {
                    <div class="w-full h-full bg-gradient-to-tr from-indigo-950 via-slate-900 to-purple-950 flex items-center justify-center">
                      <svg class="w-12 h-12 text-indigo-400/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 100-6 3 3 0 000 6z" />
                      </svg>
                    </div>
                  }
                  <div class="absolute bottom-3 right-3 px-2 py-0.5 rounded bg-black/75 backdrop-blur-sm text-xs font-mono text-white">
                    ⏱ {{ episode.duration || 'Audio' }}
                  </div>
                </div>

                <!-- Card Content -->
                <div class="p-5 flex-1 flex flex-col justify-between">
                  <div>
                    <div class="flex items-center gap-2 mb-2 text-xs text-slate-400">
                      <span class="font-medium text-indigo-400">{{ episode.podcastTitle }}</span>
                      <span>•</span>
                      <span>{{ formatDate(episode.publishedAt) }}</span>
                    </div>

                    <h3 dir="auto" class="text-base font-bold text-white group-hover:text-indigo-300 transition-colors line-clamp-2 mb-3">
                      <a [routerLink]="['/episode', episode.id]">
                        {{ episode.title }}
                      </a>
                    </h3>

                    <p dir="auto" class="text-xs text-slate-300 line-clamp-3 mb-4 leading-relaxed">
                      {{ episode.summary || episode.description }}
                    </p>
                  </div>

                  <div>
                    <!-- Keywords Tags -->
                    <div class="flex flex-wrap gap-1.5 mb-4">
                      @for (tag of episode.keywords.slice(0, 3); track tag) {
                        <span class="px-2 py-0.5 text-[10px] font-medium rounded bg-slate-800 text-slate-300">
                          #{{ tag }}
                        </span>
                      }
                      @if (episode.keywords.length > 3) {
                        <span class="px-1.5 py-0.5 text-[10px] rounded bg-slate-800 text-slate-500">
                          +{{ episode.keywords.length - 3 }}
                        </span>
                      }
                    </div>

                    <!-- Action Link -->
                    <a
                      [routerLink]="['/episode', episode.id]"
                      class="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 transition-all"
                    >
                      <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                        <path fill-rule="evenodd" clip-rule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z" />
                      </svg>
                      Listen & View Transcript
                    </a>
                  </div>
                </div>
              </article>
            }
          </div>
        }
      </section>

      <!-- Architecture Explainer Card -->
      <section id="pipeline-info" class="mt-20 rounded-3xl bg-slate-900/40 border border-slate-800 p-8 sm:p-12">
        <div class="text-center max-w-2xl mx-auto mb-10">
          <h3 class="text-2xl font-bold text-white mb-2">100% Local AI & Static SSG Architecture</h3>
          <p class="text-sm text-slate-400">
            Zero-cost pipeline transcribing RSS feeds locally with faster-whisper & Ollama, built to static HTML for Firebase Hosting.
          </p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div class="p-5 rounded-2xl bg-slate-950/80 border border-slate-800">
            <div class="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold text-sm mb-3">1</div>
            <h4 class="text-sm font-bold text-white mb-1">RSS Parse & Local Deduplication</h4>
            <p class="text-xs text-slate-400 leading-relaxed">
              Local Python script parses Anchor RSS XML, hashes GUIDs, and skips episodes already stored in <code class="text-indigo-300">episodes-index.json</code>.
            </p>
          </div>

          <div class="p-5 rounded-2xl bg-slate-950/80 border border-slate-800">
            <div class="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center font-bold text-sm mb-3">2</div>
            <h4 class="text-sm font-bold text-white mb-1">Local Hebrew Transcription</h4>
            <p class="text-xs text-slate-400 leading-relaxed">
              Streams <code class="text-indigo-300">.m4a</code> enclosures locally and transcribes verbatim Hebrew using <code class="text-indigo-300">faster-whisper</code> (<code class="text-indigo-300">ivrit-ai</code>).
            </p>
          </div>

          <div class="p-5 rounded-2xl bg-slate-950/80 border border-slate-800">
            <div class="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center font-bold text-sm mb-3">3</div>
            <h4 class="text-sm font-bold text-white mb-1">Ollama Summary & SEO Tags</h4>
            <p class="text-xs text-slate-400 leading-relaxed">
              Local Ollama (<code class="text-indigo-300">gemma3:4b</code>) generates a 2-paragraph Hebrew summary and SEO keywords, saving static JSON + <code class="text-indigo-300">sitemap.xml</code>.
            </p>
          </div>

          <div class="p-5 rounded-2xl bg-slate-950/80 border border-slate-800">
            <div class="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center font-bold text-sm mb-3">4</div>
            <h4 class="text-sm font-bold text-white mb-1">Angular SSG & Firebase Hosting</h4>
            <p class="text-xs text-slate-400 leading-relaxed">
              Prerenders every <code class="text-indigo-300">/episode/:id</code> page with <code class="text-indigo-300">PodcastEpisode</code> JSON-LD and deploys for $0/month.
            </p>
          </div>
        </div>
      </section>
    </div>
  `
})
export class HomeComponent implements OnInit {
  readonly episodeService = inject(EpisodeService);
  private readonly seoService = inject(SeoService);

  ngOnInit(): void {
    this.seoService.setDefaultSeo();
  }

  onSearchChange(event: Event): void {
    const val = (event.target as HTMLInputElement).value;
    this.episodeService.setSearchQuery(val);
  }

  selectKeyword(keyword: string | null): void {
    this.episodeService.setSelectedKeyword(keyword);
  }

  resetFilters(): void {
    this.episodeService.setSearchQuery('');
    this.episodeService.setSelectedKeyword(null);
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
}
