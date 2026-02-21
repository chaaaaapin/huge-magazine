import { defineCollection, z } from 'astro:content';

const features = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    date: z.string(), // "2026-02-19"
    ph_rank: z.number(),
    ph_votes: z.number(),
    ph_comments: z.number(),
    ph_slug: z.string(),
    ph_url: z.string(),
    product_url: z.string(),
    logo: z.string(),
    hero_image: z.string().optional(),
    topics: z.array(z.string()),
    tagline: z.string(),
    excerpt: z.string(),
    edition: z.string(), // same as date, groups by day
    author: z.string().optional(),          // e.g. "sarah-munroe"
    twitter_url: z.string().optional(),
    linkedin_url: z.string().optional(),
    github_url: z.string().optional(),
    app_type: z.string().optional(),        // "WebApplication" | "MobileApplication" | "DesktopApplication"
  }),
});

export const collections = { features };
