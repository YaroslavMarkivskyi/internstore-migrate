import { z } from 'zod';

const EMAIL_VALIDATION_ERROR_MSG = 'Please enter a valid email address';
const PWD_VALIDATION_ERROR_MSG = 'Please enter a valid password';

export const hasRequiredComplexity = (password: string): boolean => {
  let categories = 0;

  // Check for uppercase letters
  if (/[A-Z]/.test(password)) categories++;

  // Check for lowercase letters
  if (/[a-z]/.test(password)) categories++;

  // Check for digits
  if (/[0-9]/.test(password)) categories++;

  // Check for non-alphanumeric characters
  if (/[~|`={\\/+}@_[:);,!<#%>&^?$*.(]/.test(password)) categories++;

  return categories >= 3;
};

export const loginSchema = z.object({
  email: z
    .string()
    .email(EMAIL_VALIDATION_ERROR_MSG)
    .refine(email => {
      if (!email.includes('@')) return true; // Skip further checks, already fails .email()
      const [localPart, domain] = email.split('@');
      return localPart.length <= 64 && domain.length <= 255;
    })
    .refine(email => {
      const domain = email.split('@')[1];
      if (!domain) return true; // Skip this check, already fails .email()
      return /^[A-Za-z0-9.-]+$/.test(domain);
    }),

  password: z
    .string()
    .min(6, PWD_VALIDATION_ERROR_MSG)
    .max(128, PWD_VALIDATION_ERROR_MSG)
    .refine(hasRequiredComplexity, {
      message: PWD_VALIDATION_ERROR_MSG,
    }),

  root: z.string().optional(),
});

export type LoginSchemaType = z.infer<typeof loginSchema>;

export const validateField = (
  schema: z.ZodType<unknown>,
  value: unknown
): { valid: boolean; error?: string } => {
  try {
    schema.parse(value);
    return { valid: true };
  } catch (error) {
    if (error instanceof z.ZodError) {
      return { valid: false, error: error.errors[0]?.message };
    }
    return { valid: false, error: 'Validation failed' };
  }
};
