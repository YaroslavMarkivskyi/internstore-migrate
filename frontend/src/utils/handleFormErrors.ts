import { FieldValues, Path, UseFormSetError } from 'react-hook-form';

import { parseApiErrors } from './parseAPIErrors';

/**
 * Handle form errors
 * @param error - The error object from an API call
 * @param setError - Function to set errors
 */
export function handleFormErrors<TFieldValues extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<TFieldValues>
) {
  const parsedErrors = parseApiErrors(error);

  Object.entries(parsedErrors).forEach(([field, message]) => {
    if (field === 'root') {
      setError('root', {
        type: 'server',
        message,
      });
    } else {
      setError(field as Path<TFieldValues>, {
        type: 'server',
        message,
      });
    }
  });
}
