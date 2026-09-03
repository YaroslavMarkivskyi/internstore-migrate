import { resolve } from 'path';

import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  // Load environment variables that start with VITE_
  const env = loadEnv(mode, process.cwd());

  // Map the VITE_* variables to keys without the prefix.
  const processEnv = Object.keys(env)
    .filter(key => key.startsWith('VITE_'))
    .reduce(
      (acc, key) => {
        // Remove the "VITE_" prefix and expose the variable
        const newKey = key.replace(/^VITE_/, '');
        acc[`process.env.${newKey}`] = JSON.stringify(env[key]);
        return acc;
      },
      {} as Record<string, string>
    );

  return {
    define: processEnv,
    plugins: [react()],
    // Dev server. When the app is reached through a reverse proxy / tunnel
    // (nginx :8443, ngrok) rather than :5180 directly, Vite 6 rejects the
    // unknown Host unless it's listed here, and HMR's own socket can't
    // guess the public port — so allow the proxy hosts and (optionally)
    // switch HMR off. Both come from the environment (see docker-compose).
    server: {
      // loadEnv() only reads .env files, so also check process.env for the
      // values docker-compose injects.
      allowedHosts: (
        process.env.VITE_ALLOWED_HOSTS ??
        env.VITE_ALLOWED_HOSTS ??
        'localhost'
      )
        .split(',')
        .map(h => h.trim()),
      hmr:
        (process.env.VITE_DISABLE_HMR ?? env.VITE_DISABLE_HMR) === 'true'
          ? false
          : true,
    },
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
        '@components': resolve(__dirname, 'src/components'),
        '@assets': resolve(__dirname, 'src/assets'),
        '@pages': resolve(__dirname, 'src/pages'),
        '@layouts': resolve(__dirname, 'src/layouts'),
        '@constants': resolve(__dirname, 'src/constants'),
        '@utils': resolve(__dirname, 'src/utils'),
        '@services': resolve(__dirname, 'src/services'),
        '@store': resolve(__dirname, 'src/store'),
      },
    },
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      minify: 'esbuild',
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: [
              'react',
              'react-dom',
              'react-router',
              '@reduxjs/toolkit',
              'react-redux',
            ],
            mui: ['@mui/material', '@mui/icons-material'],
          },
          chunkFileNames: 'assets/js/[name]-[hash].js',
          entryFileNames: 'assets/js/[name]-[hash].js',
          assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
        },
      },
      sourcemap: false,
      cssCodeSplit: true,
      reportCompressedSize: false,
    },
  };
});
