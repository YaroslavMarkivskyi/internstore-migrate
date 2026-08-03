import { StrictMode } from 'react';

import { BrowserRouter } from 'react-router';

import { Provider } from 'react-redux';

import '@fontsource/noto-sans/400.css';
import '@fontsource/noto-sans/500.css';
import { ThemeProvider } from '@mui/material';
import { createRoot } from 'react-dom/client';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { PersistGate } from 'redux-persist/integration/react';

import { persistor, store } from '@store/store';

import App from './App';
import './index.css';
import theme from './theme';

const rootElement = document.getElementById('root');
if (!rootElement) throw new Error('Failed to find the root element');
const root = createRoot(rootElement);

root.render(
  <StrictMode>
    <Provider store={store}>
      <PersistGate loading={null} persistor={persistor}>
        <ThemeProvider theme={theme}>
          <BrowserRouter>
            <App />
            <ToastContainer toastClassName="toast" />
          </BrowserRouter>
        </ThemeProvider>
      </PersistGate>
    </Provider>
  </StrictMode>
);
