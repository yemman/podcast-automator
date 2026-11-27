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
   * Sets all meta tags and injects PodcastEpisode + AudioObject JSON-LD schema into <head>.
   * Executed during the server-side rendering pass for full search engine crawler visibility.
   */
  setEpisodeSeo(episode: Episode): void {
    const pageTitle = `${episode.title} - ${episode.podcastTitle}`;
    const cleanSummary = episode.summary ? episode.summary.replace(/\n+/g, ' ') : episode.description;
    const pageUrl = `${environment.siteUrl}/episode/${episode.id}`;
    const keywordsStr = episode.keywords ? episode.keywords.join(', ') : 'podcast, audio, transcript';

    // 1. Set Page Title
    this.titleService.setTitle(pageTitle);

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

    // 5. Build Standard Schema.org JSON-LD (PodcastEpisode & AudioObject)
    const schemaJsonLd = {
      '@context': 'https://schema.org',
      '@type': 'PodcastEpisode',
      '@id': pageUrl,
      'url': pageUrl,
      'name': episode.title,
      'description': episode.summary || episode.description,
      'datePublished': episode.publishedAt,
      'inLanguage': 'he',
      'duration': episode.duration || undefined,
      'associatedMedia': {
        '@type': 'AudioObject',
        'name': `${episode.title} (שמע / Audio)`,
        'contentUrl': episode.audioUrl,
        'encodingFormat': episode.audioType || 'audio/x-m4a',
        'contentSize': episode.audioLength ? String(episode.audioLength) : undefined
      },
      'partOfSeries': {
        '@type': 'PodcastSeries',
        'name': episode.podcastTitle || 'מי האיש החפץ חיים',
        'url': environment.siteUrl
      },
      'transcript': episode.transcript,
      'keywords': keywordsStr
    };

    this.injectJsonLd(schemaJsonLd);
  }

  /**
   * Sets SEO tags for the homepage / episode catalog.
   */
  setDefaultSeo(): void {
    const title = 'מי האיש החפץ חיים - שיעורי הרב ינאי בספר חפץ חיים | PodStream.ai';
    const description = 'פודקאסט שיעורי תורה בספר חפץ חיים מבית הכנסת תפארת ישראל רמת גן. תמלול עברי מלא (ivrit-ai), סיכום פרקים ומילות מפתח באמצעות מודלים מקומיים.';

    this.titleService.setTitle(title);
    this.meta.updateTag({ name: 'description', content: description });
    this.meta.updateTag({ name: 'keywords', content: 'מי האיש החפץ חיים, חפץ חיים, שמירת הלשון, תפארת ישראל, שיעורי תורה, הרב ינאי, רמת גן' });
    this.meta.updateTag({ property: 'og:title', content: title });
    this.meta.updateTag({ property: 'og:description', content: description });
    this.meta.updateTag({ property: 'og:type', content: 'website' });
    this.meta.updateTag({ property: 'og:url', content: environment.siteUrl });
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
   * Injects JSON-LD structured data into the HTML <head>.
   * Safely removes any previous script tag to avoid duplicate schema during SPA navigation.
   */
  private injectJsonLd(schema: object): void {
    try {
      const head = this.document.head;
      if (!head) return;

      // Remove existing script element if present
      const existingScript = this.document.getElementById(this.SCHEMA_SCRIPT_ID);
      if (existingScript) {
        head.removeChild(existingScript);
      }

      // Create new JSON-LD script element
      const script = this.document.createElement('script');
      script.id = this.SCHEMA_SCRIPT_ID;
      script.type = 'application/ld+json';
      script.text = JSON.stringify(schema, null, 2);

      head.appendChild(script);
    } catch (e) {
      // In SSR or restrictive environments, log warning
      console.warn('Failed to inject JSON-LD schema into head:', e);
    }
  }
}
