import { z } from 'zod';

import { hasRequiredComplexity } from '../CustomerLogin/validation';

export const passwordRules: { label: string; test: (pw: string) => boolean }[] =
  [
    { label: 'one number', test: pw => /\d/.test(pw) },
    { label: 'one lowercase letter', test: pw => /[a-z]/.test(pw) },
    { label: 'one capital letter', test: pw => /[A-Z]/.test(pw) },
    { label: 'one symbol', test: pw => /[!@#$%^&*(),.?":{}|<>]/.test(pw) },
    { label: 'at least six characters', test: pw => pw.length >= 6 },
  ];

export const signUpSchema = z.object({
  firstName: z
    .string()
    .min(1, 'First name is required')
    .max(50, 'First name must be less than 50 characters'),

  lastName: z
    .string()
    .min(1, 'Last name is required')
    .max(50, 'Last name must be less than 50 characters'),

  email: z.string().email('Please enter a valid email address'),

  password: z
    .string()
    .min(6, 'Password must be at least 6 characters')
    .max(128, 'Password cannot exceed 128 characters')
    .refine(hasRequiredComplexity, {
      message:
        'Password must include at least 3 of the following: uppercase letters, lowercase letters, numbers, and special characters',
    }),
});

export type SignUpFormData = z.infer<typeof signUpSchema>;
export type SignUpFormErrors = Partial<Record<keyof SignUpFormData, string>>;
