import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { RenderMode, ServerRoute } from '@angular/ssr';

export const serverRoutes: ServerRoute[] = [
  {
    path: '',
    renderMode: RenderMode.Prerender
  },
  {
    path: 'episode/:id',
    renderMode: RenderMode.Prerender,
    async getPrerenderParams() {
      const indexPath = resolve(process.cwd(), 'public/data/episodes-index.json');
      try {
        const raw = await readFile(indexPath, 'utf-8');
        const episodes = JSON.parse(raw) as Array<{ id: string }>;
        return episodes
          .filter(ep => Boolean(ep?.id))
          .map(ep => ({ id: ep.id }));
      } catch (err) {
        console.warn(`Could not read ${indexPath} for prerender params:`, err);
        return [];
      }
    }
  },
  {
    path: '**',
    renderMode: RenderMode.Client
  }
];
