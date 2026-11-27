export interface Episode {
  id: string;
  guid: string;
  title: string;
  slug: string;
  description: string;
  summary: string;
  transcript?: string;
  keywords: string[];
  audioUrl: string;
  audioType?: string;
  audioLength?: number;
  duration?: string;
  publishedAt: string;
  podcastTitle: string;
  podcastAuthor?: string;
  imageUrl?: string;
  sourceFeedUrl?: string;
  status?: string;
  ingestedAt?: string;
}

export type EpisodeIndexItem = Omit<Episode, 'transcript'> & {
  transcript?: string;
};
