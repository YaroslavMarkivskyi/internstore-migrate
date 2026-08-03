import { z } from 'zod';

export const stockSchema = z.object({
  id: z.number().optional(),
  name: z
    .string()
    .min(3, 'Name must be at least 3 characters')
    .max(15, 'Name must be at most 15 characters')
    .regex(
      /^[A-Za-z0-9][A-Za-z0-9+\- ]{2,14}$/,
      'Name can only include letters, digits, + and -, but not start with + or -'
    ),
});
