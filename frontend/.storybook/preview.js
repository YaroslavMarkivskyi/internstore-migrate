import React from 'react';

import '@fontsource/noto-sans/400.css';
import '@fontsource/noto-sans/500.css';
import { CssBaseline, ThemeProvider } from '@mui/material';
import { withThemeFromJSXProvider } from '@storybook/addon-themes';

import theme from '../src/theme.js';

const preview = {
  parameters: {
    layout: 'centered',
    controls: {
      expanded: true,
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },

  decorators: [
    withThemeFromJSXProvider({
      GlobalStyles: CssBaseline,
      Provider: ThemeProvider,
      themes: {
        light: theme,
      },
      defaultTheme: 'light',
    }),
    Story =>
      React.createElement('div', {
        children: React.createElement(Story),
        style: {
          display: 'inline-block',
        },
      }),
  ],
};

export default preview;
