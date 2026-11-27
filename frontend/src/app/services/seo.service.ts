import { Injectable, inject, PLATFORM_ID } from '@angular/core';
import { DOCUMENT, isPlatformServer } from '@angular/common';
import { Meta, Title } from '@angular/platform-browser';
import { Episode } from '../models/episode.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class SeoService {
  private readonly meta = inject(Meta);
  private readonly titleService = inject(Title);
  private readonly document = inject(DOCUMENT);
  private readonly platformId = inject(PLATFORM_ID);
  private readonly isServer = isPlatformServer(this.platformId);

  private readonly SCHEMA_SCRIPT_ID = 'podcast-jsonld-schema';

  /**
   * Sets all meta tags, canonical link, and injects PodcastEpisode + AudioObject + BreadcrumbList
   * JSON-LD schema into <head> during the SSG/SSR pass for full crawler visibility.
   */
  setEpisodeSeo(episode: Episode): void {
    const pageTitle = `${episode.title} - ${episode.podcastTitle}`;
    const cleanSummary = episode.summary ? episode.summary.replace(/\n+/g, ' ') : episode.description;
    const pageUrl = `${environment.siteUrl}/episode/${episode.id}`;
    const keywordsStr = episode.keywords ? episode.keywords.join(', ') : 'podcast, audio, transcript';
    const isoDuration = this.toIso8601Duration(episode.duration);

    // 1. Set Page Title & Canonical Link
    this.titleService.setTitle(pageTitle);
    this.setCanonicalUrl(pageUrl);

    // 2. Set Standard Meta Tags
    this.meta.updateTag({ name: 'description', content: cleanSummary.slice(0, 300) });
    this.meta.updateTag({ name: 'keywords', content: keywordsStr });
    this.meta.updateTag({ name: 'author', content: episode.podcastAuthor || episode.podcastTitle });
    this.meta.updateTag({ name: 'robots', content: 'index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1' });

    // 3. Set Open Graph Meta Tags (SEO + Social Crawlers)
    this.meta.updateTag({ property: 'og:title', content: episode.title });
    this.meta.updateTag({ property: 'og:description', content: cleanSummary.slice(0, 200) });
    this.meta.updateTag({ property: 'og:type', content: 'music.song' });
    this.meta.updateTag({ property: 'og:url', content: pageUrl });
    this.meta.updateTag({ property: 'og:audio', content: episode.audioUrl });
    this.meta.updateTag({ property: 'og:audio:type', content: episode.audioType || 'audio/mpeg' });
    if (episode.imageUrl) {
      this.meta.updateTag({ property: 'og:image', content: episode.imageUrl });
    }

    // 4. Set Twitter Card Tags
    this.meta.updateTag({ name: 'twitter:card', content: 'summary_large_image' });
    this.meta.updateTag({ name: 'twitter:title', content: episode.title });
    this.meta.updateTag({ name: 'twitter:description', content: cleanSummary.slice(0, 200) });
    if (episode.imageUrl) {
      this.meta.updateTag({ name: 'twitter:image', content: episode.imageUrl });
    }

    // 5. Build Standard Schema.org JSON-LD @graph (PodcastEpisode + AudioObject + BreadcrumbList)
    const schemaGraph = {
      '@context': 'https://schema.org',
      '@graph': [
        {
          '@type': 'PodcastEpisode',
          '@id': pageUrl,
          'url': pageUrl,
          'name': episode.title,
          'description': episode.summary || episode.description,
          'datePublished': episode.publishedAt,
          'inLanguage': 'he',
          'duration': isoDuration,
          'associatedMedia': {
            '@type': 'AudioObject',
            'name': `${episode.title} (שמע / Audio)`,
            'contentUrl': episode.audioUrl,
            'encodingFormat': episode.audioType || 'audio/x-m4a',
            'duration': isoDuration,
            'contentSize': episode.audioLength ? String(episode.audioLength) : undefined
          },
          'partOfSeries': {
            '@type': 'PodcastSeries',
            'name': episode.podcastTitle || 'מי האיש החפץ חיים',
            'url': environment.siteUrl
          },
          'transcript': episode.transcript,
          'keywords': keywordsStr
        },
        {
          '@type': 'BreadcrumbList',
          'itemListElement': [
            {
              '@type': 'ListItem',
              'position': 1,
              'name': episode.podcastTitle || 'מי האיש החפץ חיים',
              'item': `${environment.siteUrl}/`
            },
            {
              '@type': 'ListItem',
              'position': 2,
              'name': episode.title,
              'item': pageUrl
            }
          ]
        }
      ]
    };

    this.injectJsonLd(schemaGraph);
  }

  /**
   * Sets SEO tags and canonical link for the homepage / episode catalog.
   */
  setDefaultSeo(): void {
    const title = 'מי האיש החפץ חיים - שיעורי הרב ינאי בספר חפץ חיים | PodStream.ai';
    const description = 'פודקאסט שיעורי תורה בספר חפץ חיים מבית הכנסת תפארת ישראל רמת גן. תמלול עברי מלא (ivrit-ai), סיכום פרקים ומילות מפתח באמצעות מודלים מקומיים.';
    const homeUrl = `${environment.siteUrl}/`;

    this.titleService.setTitle(title);
    this.setCanonicalUrl(homeUrl);
    this.meta.updateTag({ name: 'description', content: description });
    this.meta.updateTag({ name: 'keywords', content: 'מי האיש החפץ חיים, חפץ חיים, שמירת הלשון, תפארת ישראל, שיעורי תורה, הרב ינאי, רמת גן' });
    this.meta.updateTag({ property: 'og:title', content: title });
    this.meta.updateTag({ property: 'og:description', content: description });
    this.meta.updateTag({ property: 'og:type', content: 'website' });
    this.meta.updateTag({ property: 'og:url', content: homeUrl });
    this.meta.updateTag({ name: 'twitter:card', content: 'summary_large_image' });

    const seriesSchema = {
      '@context': 'https://schema.org',
      '@type': 'PodcastSeries',
      'name': 'מי האיש החפץ חיים',
      'inLanguage': 'he',
      'url': environment.siteUrl,
      'description': description
    };

    this.injectJsonLd(seriesSchema);
  }

  /**
   * Converts HH:MM:SS, MM:SS, or raw seconds into ISO-8601 duration (e.g. PT32M59S).
   */
  private toIso8601Duration(raw?: string): string | undefined {
    if (!raw) return undefined;
    const trimmed = raw.trim();
    if (!trimmed) return undefined;
    if (/^PT/i.test(trimmed)) return trimmed.toUpperCase();

    let hours = 0;
    let minutes = 0;
    let seconds = 0;

    if (/^\d+$/.test(trimmed)) {
      const total = parseInt(trimmed, 10);
      hours = Math.floor(total / 3600);
      minutes = Math.floor((total % 3600) / 60);
      seconds = total % 60;
    } else if (/^\d{1,2}:\d{1,2}(:\d{1,2})?$/.test(trimmed)) {
      const parts = trimmed.split(':').map(p => parseInt(p, 10));
      if (parts.length === 3) {
        [hours, minutes, seconds] = parts;
      } else {
        [minutes, seconds] = parts;
      }
    } else {
      return undefined;
    }

    let out = 'PT';
    if (hours > 0) out += `${hours}H`;
    if (minutes > 0) out += `${minutes}M`;
    if (seconds > 0 || out === 'PT') out += `${seconds}S`;
    return out;
  }

  /**
   * Sets or updates <link rel="canonical"> inside document <head>.
   */
  private setCanonicalUrl(url: string): void {
    try {
      const head = this.document.head;
      if (!head) return;

      let linkEl = this.document.querySelector('link[rel="canonical"]') as HTMLLinkElement | null;
      if (!linkEl) {
        linkEl = this.document.createElement('link');
        linkEl.setAttribute('rel', 'canonical');
        head.appendChild(linkEl);
      }
      linkEl.setAttribute('href', url);
    } catch (e) {
      console.warn('Failed to set canonical URL:', e);
    }
  }

  /**
   * Injects JSON-LD structured data into the HTML <head>.
   * Safely removes any previous script tag to avoid duplicate schema during SPA navigation.
   */
  private injectJsonLd(schema: object): void {
    try {
      const head = this.document.head;
      if (!head) return;

      const existingScript = this.document.getElementById(this.SCHEMA_SCRIPT_ID);
      if (existingScript) {
        head.removeChild(existingScript);
      }

      const script = this.document.createElement('script');
      script.id = this.SCHEMA_SCRIPT_ID;
      script.type = 'application/ld+json';
      script.text = JSON.stringify(schema, null, 2);

      head.appendChild(script);
    } catch (e) {
      console.warn('Failed to inject JSON-LD schema into head:', e);
    }
  }
}
