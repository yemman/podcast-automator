import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Episode, EpisodeIndexItem } from '../models/episode.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class EpisodeService {
  private readonly http = inject(HttpClient);
  private readonly fullEpisodeCache = new Map<string, Episode>();

  // --- Core State Signals ---
  readonly episodes = signal<EpisodeIndexItem[]>([]);
  readonly selectedEpisode = signal<Episode | null>(null);
  readonly loading = signal<boolean>(false);
  readonly error = signal<string | null>(null);

  // --- Filter & Search Signals ---
  readonly searchQuery = signal<string>('');
  readonly selectedKeyword = signal<string | null>(null);

  // --- Computed Signals ---
  readonly filteredEpisodes = computed(() => {
    const list = this.episodes();
    const query = this.searchQuery().toLowerCase().trim();
    const keyword = this.selectedKeyword();

    return list.filter(ep => {
      if (keyword && !ep.keywords.some(k => k.toLowerCase() === keyword.toLowerCase())) {
        return false;
      }

      if (!query) return true;

      const titleMatch = ep.title.toLowerCase().includes(query);
      const summaryMatch = (ep.summary || '').toLowerCase().includes(query);
      const descMatch = (ep.description || '').toLowerCase().includes(query);
      const transcriptMatch = (ep.transcript || '').toLowerCase().includes(query);
      const keywordMatch = ep.keywords.some(k => k.toLowerCase().includes(query));

      return titleMatch || summaryMatch || descMatch || transcriptMatch || keywordMatch;
    });
  });

  readonly allKeywords = computed(() => {
    const set = new Set<string>();
    for (const ep of this.episodes()) {
      for (const k of ep.keywords) {
        set.add(k);
      }
    }
    return Array.from(set).slice(0, 15);
  });

  constructor() {
    void this.fetchEpisodes();
  }

  /**
   * Fetches the static catalog index from /data/episodes-index.json.
   * Angular TransferState caches this response automatically during SSG prerendering.
   */
  async fetchEpisodes(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);

    try {
      const list = await firstValueFrom(
        this.http.get<EpisodeIndexItem[]>(environment.episodesIndexUrl).pipe(
          catchError(err => {
            this.error.set(err?.message || 'Failed to load episodes index');
            return of([] as EpisodeIndexItem[]);
          })
        )
      );

      this.episodes.set(Array.isArray(list) ? list : []);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to load episodes index';
      this.error.set(msg);
      this.episodes.set([]);
    } finally {
      this.loading.set(false);
    }
  }

  /**
   * Fetches a complete episode (including verbatim transcript) by ID from /data/episodes/<id>.json.
   * Always resolves full episode data rather than returning an index entry without transcript.
   */
  async getEpisodeById(id: string): Promise<Episode | null> {
    const cached = this.fullEpisodeCache.get(id);
    if (cached) {
      this.selectedEpisode.set(cached);
      return cached;
    }

    this.loading.set(true);
    const docUrl = `${environment.episodeDetailBaseUrl}/${encodeURIComponent(id)}.json`;

    try {
      const episode = await firstValueFrom(
        this.http.get<Episode>(docUrl).pipe(
          catchError(() => of(null))
        )
      );

      if (episode && episode.id) {
        this.fullEpisodeCache.set(id, episode);
        this.selectedEpisode.set(episode);
        return episode;
      }
    } catch (err) {
      console.warn(`Could not load episode ${id} from static JSON:`, err);
    } finally {
      this.loading.set(false);
    }

    this.selectedEpisode.set(null);
    return null;
  }

  setSearchQuery(query: string): void {
    this.searchQuery.set(query);
  }

  setSelectedKeyword(keyword: string | null): void {
    if (this.selectedKeyword() === keyword) {
      this.selectedKeyword.set(null);
    } else {
      this.selectedKeyword.set(keyword);
    }
  }
}
