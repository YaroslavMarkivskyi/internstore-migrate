// utils/activityDetection.ts

/**
 * Activity routes that should trigger logout confirmation
 */
const ACTIVITY_ROUTES = ['/add', '/edit'];

/**
 * Check if current URL matches activity routes
 */
export const hasUrlActivity = (pathname: string): boolean => {
  return ACTIVITY_ROUTES.some(route => {
    if (route === '/add') {
      return pathname.endsWith('/add');
    }
    if (route === '/edit') {
      return pathname.includes('/edit/');
    }
    return false;
  });
};

/**
 * Check for forms with unsaved changes in the DOM
 */
export const hasDirtyForms = (): boolean => {
  try {
    const forms = document.querySelectorAll('form');

    for (const form of forms) {
      const inputs = form.querySelectorAll('input, textarea, select');

      for (const input of inputs) {
        if (input instanceof HTMLInputElement) {
          // Skip if no initial value to compare against
          if (!input.defaultValue && !input.value) continue;

          // Check if current value differs from initial value
          if (input.value !== input.defaultValue) {
            return true;
          }

          // Special handling for checkboxes and radio buttons
          if (input.type === 'checkbox' || input.type === 'radio') {
            if (input.checked !== input.defaultChecked) {
              return true;
            }
          }
        } else if (input instanceof HTMLTextAreaElement) {
          if (!input.defaultValue && !input.value) continue;

          if (input.value !== input.defaultValue) {
            return true;
          }
        } else if (input instanceof HTMLSelectElement) {
          const options = Array.from(input.options);
          for (const option of options) {
            if (option.selected !== option.defaultSelected) {
              return true;
            }
          }
        }
      }
    }

    return false;
  } catch (error) {
    console.warn('Error detecting form changes:', error);
    return false;
  }
};

/**
 * Main activity detection function
 */
export const hasUserActivity = (pathname: string): boolean => {
  const urlActivity = hasUrlActivity(pathname);
  const formActivity = hasDirtyForms();

  return urlActivity || formActivity;
};
