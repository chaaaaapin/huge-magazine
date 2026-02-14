import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
  // Get all articles from all categories
  const breakthroughs = await import.meta.glob('../content/breakthroughs/*.md', { eager: true });
  const articles = await import.meta.glob('../content/articles/*.md', { eager: true });
  const opinions = await import.meta.glob('../content/opinions/*.md', { eager: true });
  const profiles = await import.meta.glob('../content/profiles/*.md', { eager: true });

  // Combine all posts
  const allPosts = [
    ...Object.values(breakthroughs),
    ...Object.values(articles),
    ...Object.values(opinions),
    ...Object.values(profiles)
  ].map(post => ({
    title: post.frontmatter.title,
    description: post.frontmatter.description,
    pubDate: new Date(post.frontmatter.pubDate),
    link: post.url,
  }));

  // Sort by date
  allPosts.sort((a, b) => b.pubDate - a.pubDate);

  return rss({
    title: 'HUGE Magazine',
    description: 'Where Innovation Meets Impact. Breakthrough ideas, emerging technologies, and the innovations shaping tomorrow.',
    site: context.site,
    items: allPosts,
    customData: '<language>en-us</language>',
  });
}
