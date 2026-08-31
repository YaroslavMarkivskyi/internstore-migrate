import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import CustomerLayout from '../index';

jest.mock('@layouts/CustomerLayout/components/Navbar', () => () => (
  <div>Mocked Navbar</div>
));
jest.mock('@layouts/CustomerLayout/components/Footer', () => () => (
  <div>Mocked Footer</div>
));
jest.mock('@components/ChatWidget', () => () => <div>Mocked ChatWidget</div>);

describe('CustomerLayout', () => {
  it('renders layout with nested route content and mocks Navbar/Footer', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<CustomerLayout />}>
            <Route index element={<div>Test Page Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Mocked Navbar')).toBeInTheDocument();
    expect(screen.getByText('Mocked Footer')).toBeInTheDocument();

    expect(screen.getByText('Test Page Content')).toBeInTheDocument();
  });
});
