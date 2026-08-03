import js from '@eslint/js';
import importsPlugin from 'eslint-plugin-import';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  // Base configuration (applies to all files)
  { ignores: ['dist', 'node_modules', 'build', 'coverage', '.git'] },

  // JavaScript files
  {
    files: ['**/*.{js,jsx,mjs,cjs}'],
    extends: [js.configs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
      globals: {
        ...globals.browser,
        ...globals.es2021,
        ...globals.node,
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      import: importsPlugin,
    },
    rules: {
      // React Hooks Rules
      ...reactHooks.configs.recommended.rules,

      // React Refresh Rules
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],

      // Common ESLint rules
      'no-console': ['warn', { allow: ['warn', 'error', 'info', 'log'] }],
      'no-debugger': 'warn',
      'no-alert': 'warn',
      'prefer-const': 'error',
      'no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
        },
      ],

      // Padding rules
      'padding-line-between-statements': [
        'error',
        { blankLine: 'always', prev: '*', next: 'function' },
        { blankLine: 'always', prev: 'import', next: 'function' },
        { blankLine: 'always', prev: 'function', next: 'export' },
      ],

      // Import rules
      'import/order': [
        'error',
        {
          groups: [
            'builtin', // Node.js built-in modules
            'external', // Installed dependencies
            'internal', // Paths aliased in the monorepo
            'parent', // Parent directories
            'sibling', // Same directory
            'index', // Current directory index file
            'object', // Object imports
            'type', // Type imports
          ],
          'newlines-between': 'always',
          alphabetize: {
            order: 'asc',
            caseInsensitive: true,
          },
          pathGroups: [
            // 1. Standard library imports (React, Redux, etc.)
            { pattern: 'react', group: 'external', position: 'before' },
            { pattern: 'react-dom', group: 'external', position: 'before' },
            { pattern: 'react-router', group: 'external', position: 'before' },
            {
              pattern: 'react-router-dom',
              group: 'external',
              position: 'before',
            },
            { pattern: 'react-redux', group: 'external', position: 'before' },
            { pattern: 'redux', group: 'external', position: 'before' },
            { pattern: '@reduxjs/**', group: 'external', position: 'before' },
            { pattern: 'axios', group: 'external', position: 'before' },

            // 2. Other external libraries with @ prefix (MUI, etc.)
            { pattern: '@mui/**', group: 'external' },
            { pattern: '@emotion/**', group: 'external' },
            { pattern: '@hookform/**', group: 'external' },

            // 3. Internal alias imports (our own modules)
            { pattern: '@components/**', group: 'internal' },
            { pattern: '@assets/**', group: 'internal' },
            { pattern: '@pages/**', group: 'internal' },
            { pattern: '@layouts/**', group: 'internal' },
            { pattern: '@constants/**', group: 'internal' },
            { pattern: '@utils/**', group: 'internal' },
            { pattern: '@services/**', group: 'internal' },
            { pattern: '@store/**', group: 'internal' },
            { pattern: '@/**', group: 'internal' },

            // 4. Relative imports - components from parent/sibling directories
            {
              pattern: '../**',
              group: 'parent',
              position: 'before',
            },
            {
              pattern: './**',
              group: 'sibling',
              position: 'before',
            },

            // 5. Type imports (must come last before styles)
            { pattern: '**/**/types', group: 'type' },
            { pattern: '**/**/types/**', group: 'type' },
            { pattern: '**/**/interfaces', group: 'type' },
            { pattern: '**/**/interfaces/**', group: 'type' },
            { pattern: '**/*.type', group: 'type' },
            { pattern: '**/*.types', group: 'type' },

            // 6. Style imports very last
            {
              pattern: './**/*styles.{ts,tsx}',
              group: 'sibling',
              position: 'after',
            },
            {
              pattern: './**/styles.{ts,tsx}',
              group: 'sibling',
              position: 'after',
            },
            {
              pattern: './**/*.styles.{ts,tsx}',
              group: 'sibling',
              position: 'after',
            },
            {
              pattern: './**/*.style.{ts,tsx}',
              group: 'sibling',
              position: 'after',
            },
            { pattern: './**/*.css', group: 'sibling', position: 'after' },
          ],
          pathGroupsExcludedImportTypes: ['builtin'],
          warnOnUnassignedImports: false,
        },
      ],
      'import/first': 'error',
      'import/newline-after-import': 'error',
      'import/no-duplicates': 'error',
    },
  },

  // TypeScript files
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
      globals: {
        ...globals.browser,
        ...globals.es2021,
        ...globals.node,
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      import: importsPlugin,
    },
    rules: {
      // React Hooks Rules
      ...reactHooks.configs.recommended.rules,

      // React Refresh Rules
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],

      // Common ESLint rules
      'no-console': ['warn', { allow: ['warn', 'error', 'info', 'log'] }],
      'no-debugger': 'warn',
      'no-alert': 'warn',
      'prefer-const': 'error',

      // TypeScript-specific rules
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
        },
      ],
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/explicit-module-boundary-types': 'off',
      '@typescript-eslint/no-non-null-assertion': 'warn',
      '@typescript-eslint/ban-ts-comment': 'warn',
      '@typescript-eslint/consistent-type-definitions': 'off',

      // Padding rules
      'padding-line-between-statements': [
        'error',
        { blankLine: 'always', prev: '*', next: 'function' },
        { blankLine: 'always', prev: 'import', next: 'function' },
        { blankLine: 'always', prev: 'function', next: 'export' },
      ],

      // Replace basic sort-imports with comprehensive import ordering
      'sort-imports': [
        'error',
        {
          ignoreCase: true,
          ignoreDeclarationSort: true,
        },
      ],

      // Import rules - same structure as JS config
      'import/order': [
        'error',
        {
          groups: [
            'builtin', // Node.js built-in modules
            'external', // Installed dependencies
            'internal', // Paths aliased in the monorepo
            'parent', // Parent directories
            'sibling', // Same directory
            'index', // Current directory index file
            'object', // Object imports
            'type', // Type imports
          ],
          'newlines-between': 'always',
          alphabetize: {
            order: 'asc',
            caseInsensitive: true,
          },
          pathGroups: [
            // 1. Standard library imports (React, Redux, etc.)
            { pattern: 'react', group: 'external', position: 'before' },
            { pattern: 'react-dom', group: 'external', position: 'before' },
            { pattern: 'react-router', group: 'external', position: 'before' },
            {
              pattern: 'react-router-dom',
              group: 'external',
              position: 'before',
            },
            { pattern: 'react-redux', group: 'external', position: 'before' },
            { pattern: 'redux', group: 'external', position: 'before' },
            { pattern: '@reduxjs/**', group: 'external', position: 'before' },
            { pattern: 'axios', group: 'external', position: 'before' },

            // 2. Other external libraries with @ prefix (MUI, etc.)
            { pattern: '@mui/**', group: 'external' },
            { pattern: '@emotion/**', group: 'external' },
            { pattern: '@hookform/**', group: 'external' },

            // 3. Internal alias imports (our own modules)
            { pattern: '@components/**', group: 'internal' },
            { pattern: '@assets/**', group: 'internal' },
            { pattern: '@pages/**', group: 'internal' },
            { pattern: '@layouts/**', group: 'internal' },
            { pattern: '@constants/**', group: 'internal' },
            { pattern: '@utils/**', group: 'internal' },
            { pattern: '@services/**', group: 'internal' },
            { pattern: '@store/**', group: 'internal' },
            { pattern: '@/**', group: 'internal' },

            // 4. Relative imports - components from parent/sibling directories
            {
              pattern: '../**',
              group: 'parent',
              position: 'before',
            },
            {
              pattern: './**',
              group: 'sibling',
              position: 'before',
            },

            // 5. Type imports (must come last before styles)
            { pattern: '**/**/types', group: 'type' },
            { pattern: '**/**/types/**', group: 'type' },
            { pattern: '**/**/interfaces', group: 'type' },
            { pattern: '**/**/interfaces/**', group: 'type' },
            { pattern: '**/*.type', group: 'type' },
            { pattern: '**/*.types', group: 'type' },

            // 6. Style imports very last
            {
              pattern: './**/*styles.{ts,tsx}',
              group: 'sibling',
              position: 'after',
            },
            {
              pattern: './**/styles.{ts,tsx}',
              group: 'sibling',
              position: 'after',
            },
            {
              pattern: './**/*.styles.{ts,tsx}',
              group: 'sibling',
              position: 'after',
            },
            {
              pattern: './**/*.style.{ts,tsx}',
              group: 'sibling',
              position: 'after',
            },
            { pattern: './**/*.css', group: 'sibling', position: 'after' },
          ],
          pathGroupsExcludedImportTypes: ['builtin'],
          warnOnUnassignedImports: false,
        },
      ],
      'import/first': 'error',
      'import/newline-after-import': 'error',
      'import/no-duplicates': 'error',
    },
  },

  // Test files - Disable import order rules
  {
    files: ['**/*.test.{ts,tsx,js,jsx}', '**/*.spec.{ts,tsx,js,jsx}'],
    rules: {
      'no-console': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-non-null-assertion': 'off',
      // Disable import ordering rules for test files
      'import/order': 'off',
      'import/first': 'off',
      'sort-imports': 'off',
    },
  },

  // Deploy scripts (special handling)
  {
    files: ['**/scripts/deploy.js'],
    rules: {
      'no-console': 'off',
      'no-unused-vars': [
        'warn',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
        },
      ],
    },
  }
);
