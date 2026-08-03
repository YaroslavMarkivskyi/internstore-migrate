import { MemoryRouter } from 'react-router-dom';

import { render } from '@testing-library/react';

export function renderWithRouter(ui: React.ReactElement, { route = '/' } = {}) {
  window.history.pushState({}, 'Test page', route);
  return render(<MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>);
}
