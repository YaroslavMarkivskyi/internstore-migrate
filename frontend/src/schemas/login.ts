import { z } from 'zod';

const SPECIAL_CHARS = `~\`|\\\\=/{@_\\[\\]:\\),\\(<#!%>&^?$*\\.\\+]`;
const EMAIL_REGEX =
  /^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,255}(\.[A-Za-z0-9-]{2,})+$/;

const EMAIL_MESSAGE = 'Please enter a valid email address.';
const passwordSchema = z
  .string()
  .min(6, 'Password must be at least 6 characters')
  .max(128, 'Password must be at most 128 characters')
  .refine(
    password => {
      let categories = 0;

      if (/[a-z]/.test(password)) categories++;
      if (/[A-Z]/.test(password)) categories++;
      if (/\d/.test(password)) categories++;
      if (new RegExp(`[${SPECIAL_CHARS}]`).test(password)) categories++;

      return categories >= 3;
    },
    {
      message: 'Password must include 3 of: upper, lower, digits, special.',
    }
  );

export const loginSchema = z.object({
  email: z
    .string()
    .min(1, { message: 'Email is required' })
    .max(320, { message: EMAIL_MESSAGE })
    .regex(EMAIL_REGEX, {
      message: EMAIL_MESSAGE,
    }),
  password: passwordSchema,
});
