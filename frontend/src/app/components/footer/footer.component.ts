import { Component } from '@angular/core';

@Component({
  selector: 'app-footer',
  standalone: true,
  template: `
    <footer class="mt-24 border-t border-slate-800/80 bg-slate-950/60 py-12 text-sm text-slate-400">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
          <div class="col-span-1 md:col-span-2 space-y-3">
            <div class="flex items-center gap-2">
              <div class="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-xs">
                P
              </div>
              <span class="text-base font-semibold text-white">PodStream.ai</span>
            </div>
            <p class="text-slate-400 text-xs sm:text-sm max-w-md leading-relaxed">
              $0/month SEO-optimized podcast delivery platform powered by local faster-whisper (ivrit-ai) transcription, 
              Ollama summaries, Angular Static Site Generation (SSG), and Firebase Hosting.
            </p>
          </div>

          <div>
            <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-3">Architecture</h4>
            <ul class="space-y-2 text-xs">
              <li class="flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                <span>Local Python RSS Pipeline</span>
              </li>
              <li class="flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full bg-blue-400"></span>
                <span>faster-whisper (ivrit-ai) + Ollama</span>
              </li>
              <li class="flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                <span>Static JSON + Sitemap.xml</span>
              </li>
              <li class="flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full bg-red-400"></span>
                <span>Angular SSG + Firebase Hosting</span>
              </li>
            </ul>
          </div>

          <div>
            <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-3">SEO Standards</h4>
            <ul class="space-y-2 text-xs">
              <li><span class="text-indigo-400">PodcastEpisode</span> JSON-LD</li>
              <li><span class="text-indigo-400">AudioObject</span> Schema</li>
              <li>Open Graph & Twitter Audio Cards</li>
              <li>Server-Side Pre-Rendered Transcripts</li>
            </ul>
          </div>
        </div>

        <div class="pt-8 border-t border-slate-800/60 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-400 gap-4">
          <p>© 2026 PodStream.ai. Built for modern SEO and automated podcast ingestion.</p>
          <div class="flex items-center gap-6">
            <span class="inline-flex items-center gap-1.5 text-emerald-400">
              <span class="relative flex h-2 w-2">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              Pipeline Online
            </span>
          </div>
        </div>
      </div>
    </footer>
  `
})
export class FooterComponent {}
