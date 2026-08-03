/** @type {import('ts-jest').JestConfigWithTsJest} **/
export default {
  testEnvironment: 'jsdom',
  transform: {
    '^.+\\.tsx?$': [
      'ts-jest',
      {
        diagnostics: { ignoreCodes: ['TS151001'] },
        tsconfig: {
          jsx: 'react-jsx',
          moduleResolution: 'node',
          baseUrl: '.',
          paths: {
            '@/*': ['src/*'],
            '@components/*': ['src/components/*'],
            '@assets/*': ['src/assets/*'],
            '@pages/*': ['src/pages/*'],
            '@layouts/*': ['src/layouts/*'],
            '@constants/*': ['src/constants/*'],
            '@utils/*': ['src/utils/*'],
            '@services/*': ['src/services/*'],
            '@store/*': ['src/store/*'],
          },
        },
      },
    ],
  },
  moduleNameMapper: {
    '\\.css$': '<rootDir>/src/__mocks__/styleMock.js',
    '\\.svg$': '<rootDir>/src/__mocks__/svgMock.js',
    '\\.(jpg|jpeg|png|gif|eot|otf|webp|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$':
      '<rootDir>/src/__mocks__/fileMock.js',
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@components/(.*)$': '<rootDir>/src/components/$1',
    '^@assets/(.*)$': '<rootDir>/src/assets/$1',
    '^@pages/(.*)$': '<rootDir>/src/pages/$1',
    '^@layouts/(.*)$': '<rootDir>/src/layouts/$1',
    '^@constants/(.*)$': '<rootDir>/src/constants/$1',
    '^@utils/(.*)$': '<rootDir>/src/utils/$1',
    '^@services/(.*)$': '<rootDir>/src/services/$1',
    '^@store/(.*)$': '<rootDir>/src/store/$1',
  },
  moduleFileExtensions: ['ts', 'tsx', 'js'],
  setupFilesAfterEnv: ['./jest.setup.ts'],
  modulePathIgnorePatterns: ['.*__mocks__.*'],
};
