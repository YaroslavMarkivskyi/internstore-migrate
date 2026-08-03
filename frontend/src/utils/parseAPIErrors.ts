import axios from 'axios';

/**
 * Parses API error responses into a standardized format
 * @param error - The error object from an API call
 * @returns An object mapping field names to error messages
 */
export const parseApiErrors = (error: unknown): Record<string, string> => {
  const errors: Record<string, string> = {};

  if (axios.isAxiosError(error)) {
    const responseData = error.response?.data;

    // No response data
    if (!responseData) {
      errors.root = 'Server connection error. Please try again.';
      return errors;
    }

    // String error (simple message)
    if (typeof responseData === 'string') {
      errors.root = responseData;
      return errors;
    }

    // DRF style with 'detail' field
    if (responseData.detail) {
      errors.root = responseData.detail;
      return errors;
    }

    // Field-specific errors (common in form validations)
    if (typeof responseData === 'object') {
      Object.entries(responseData).forEach(([field, messages]) => {
        if (Array.isArray(messages) && messages.length > 0) {
          errors[field] = messages[0] as string;
        } else if (typeof messages === 'string') {
          errors[field] = messages;
        }
      });

      // If no errors were extracted, but we know there's an error
      if (Object.keys(errors).length === 0) {
        errors.root = 'An error occurred. Please try again.';
      }
    }
  } else if (error instanceof Error) {
    errors.root = error.message;
  } else {
    errors.root = 'An unknown error occurred. Please try again.';
  }

  return errors;
};
