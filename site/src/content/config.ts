import { defineCollection, z } from 'astro:content';

const articleSchema = z.object({
  title: z.string(),
  description: z.string(),
  pubDate: z.coerce.date(),
  category: z.string(),
  image: z.string().optional(),
  imageCredit: z.string().optional(),
});

const articles = defineCollection({
  type: 'content',
  schema: articleSchema,
});

const breakthroughs = defineCollection({
  type: 'content',
  schema: articleSchema,
});

const opinions = defineCollection({
  type: 'content',
  schema: articleSchema,
});

const profiles = defineCollection({
  type: 'content',
  schema: articleSchema,
});

export const collections = {
  articles,
  breakthroughs,
  opinions,
  profiles,
};
