import { defineCollection, z } from 'astro:content';

const articles = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    heroImage: z.string().optional(),
    author: z.string().default('HUGE Editorial'),
    category: z.enum([
      'Breakthrough Technologies',
      'Innovation Case Studies',
      'Visionary Profiles',
      'Future Dispatches',
      'HUGE Ideas'
    ]),
    tags: z.array(z.string()).default([]),
    featured: z.boolean().default(false),
  }),
});

const breakthroughs = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    heroImage: z.string().optional(),
    author: z.string().default('HUGE Editorial'),
    tags: z.array(z.string()).default([]),
    featured: z.boolean().default(true),
  }),
});

const profiles = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    heroImage: z.string().optional(),
    person: z.string(),
    role: z.string(),
    company: z.string().optional(),
    tags: z.array(z.string()).default([]),
  }),
});

const opinions = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    author: z.string(),
    heroImage: z.string().optional(),
    tags: z.array(z.string()).default([]),
  }),
});

export const collections = { articles, breakthroughs, profiles, opinions };
