import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
  const features = await getCollection('features');

  // Sort newest first
  features.sort((a, b) => {
    if (b.data.date !== a.data.date) return b.data.date.localeCompare(a.data.date);
    return a.data.ph_rank - b.data.ph_rank;
  });

  return rss({
    title: 'HUGE Magazine',
    description: 'Daily startup features. We write analysis, not press releases.',
    site: context.site,
    items: features.map(f => ({
      title: f.data.title,
      description: f.data.excerpt,
      link: `/feature/${f.data.ph_slug}/`,
      pubDate: new Date(f.data.date + 'T12:00:00Z'),
    })),
    customData: '<language>en-us</language>',
  });
}
