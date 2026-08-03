// Helper to convert camelCase to snake_case
function toSnakeCase(str: string): string {
  return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
}

// Generic function to convert object to query string
export function toQueryParams<T extends Record<string, any>>(
  params: T
): string {
  const queryParams = Object.entries(params)
    .filter(([_, value]) => value !== undefined && value !== null)
    .map(([key, value]) => {
      const snakeKey = toSnakeCase(key);
      const encodedValue = encodeURIComponent(String(value));
      return `${snakeKey}=${encodedValue}`;
    })
    .join('&');

  return queryParams ? `?${queryParams}` : '';
}
