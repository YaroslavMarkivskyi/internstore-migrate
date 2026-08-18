# InternStore India – Frontend

## Overview

This is frontend part of the InternStore India Application.

## Requirements

- [Node.js](https://nodejs.org/en/download)

## Backend (internstore-migrate)

This directory lives inside [internstore-migrate](../), which provides the
gateway/domain-services stack this app talks to. `.env` points at it:
`VITE_SERVER_URL=https://localhost:8443/api/` (nginx gateway) — see
[../nginx](../nginx).

**Login is currently broken against this backend.** `.env`'s
`VITE_KEYCLOAK_URL=http://localhost:8081`/realm/client
`internstore`/`internstore-web` target Keycloak, which the backend removed
(STR-192, see
[../docs/adr/0004-replace-keycloak-with-firebase.md](../docs/adr/0004-replace-keycloak-with-firebase.md))
in favor of Firebase Authentication. Migrating this app's login flow to the
Firebase JS SDK is flagged there as a real dependency, not built yet —
`VITE_KEYCLOAK_*` is left in `docker-compose.yml` for now only so the build
doesn't fail on a missing env var, not because it still works. Catalog
browsing and guest checkout don't need login and are unaffected.

Either run locally (`npm run dev`, default port `5173`) or as part of the
compose stack:

```bash
cd ..
docker compose up -d --build frontend
```

which publishes on **`:5180`**, not `:5173` — pick whichever port is free
on your machine and update all three of these to match if `:5180` also
collides:

- `docker-compose.yml`'s `frontend` service `ports:` and `--port` in this
  project's `Dockerfile`
- nginx's CORS allowlist (`$cors_origin` map in
  [nginx/nginx.conf](../nginx/nginx.conf))

(Keycloak's `internstore-web` client `redirectUris` used to be a third
place to update here — moot since Keycloak was removed, see above.)

### "CORS request did not succeed" / "Status code: (null)"

If every API call fails with this exact Firefox/Chrome message, it's
almost never a real CORS misconfiguration — it means the TLS handshake to
`https://localhost:8443` failed *before* CORS was ever evaluated, and the
browser mis-reports it as a CORS error because the failing calls are
background `fetch`/XHR, not a page navigation (so you never see the normal
"connection is not secure" interstitial).

nginx's dev cert is self-signed (`nginx/docker-entrypoint-certs.sh`) and
persisted in the `nginx_certs` volume so it survives `docker compose up
--build nginx` — but you still have to accept it once per browser
profile, and again any time that volume is removed (`docker compose down
-v`) since a removed volume regenerates a brand new cert with a different
fingerprint, invalidating whatever exception you'd already granted:

1. Open `https://localhost:8443/api/catalog/categories` directly in a new
   tab.
2. Click through the browser's "not secure" warning (Advanced -> Proceed /
   Accept the Risk and Continue).
3. Reload the frontend tab.

## Getting Started

To get started simply install all required packages with

```bash
  npm install
```

## How to run

To start development server you need to run

```bash
  npm run dev
```

## How to test

To run all tests use

```bash
  npm run test
```

## How to build

To build app for production use

```bash
  npm run build
```

## Project Structure

```
internstore-india-frontend/
├── .husky/ # Precommit hooks
├── public/ # Static assets
├── src/
│   ├── __mocks__ # Mocks
│   ├── assets/ # Images and media
│   ├── components/ # Reusable components
│   │   ├── Example/
│   │   │   ├── Example.tsx
│   │   │   ├── Example.test.tsx
│   ├── hooks/  # Custom hooks
│   ├── pages/  # Page-level components
│   │   ├── Example/
│   │   │   ├── Example.tsx
│   │   │   ├── Example.test.tsx
│   ├── services/ # Services
│   │   ├── http/
│   │   │   ├── api.ts
│   │   │   ├── example.ts
│   ├── store/  # Redux store
│   │   ├── reducers/
│   │   ├── store.ts
│   ├── types/  # App-wide types
│   ├── utils/  # Utility functions
│   │   ├── example/
│   │   │   ├── example.tsx
│   │   │   ├── example.test.tsx
│   ├── App.tsx
│   ├── index.css
│   ├── main.tsx
│   ├── theme.ts
│   ├── vite-env.d.ts
├── .env  # Environment variables for local development
├── .env.production # Environemnt variables for production
├── .gitignore
├── .prettierignore
├── .prettierrc
├── README.md
├── eslint.config.js
├── index.html
├── jest.config.ts
├── package-lock.json
├── package.json
├── tsconfig.app.json
├── tsconfig.json
├── tsconfig.node.json
└── vite.config.ts
```

### How to add component/page/utils

To add component, page or utility function:

- Create folder in corresponding directory
- Create needed file (for example Home.tsx)
- Create file for tests (for example Home.test.tsx)

### How to add Redux reducer

All redux reducers go to [src/store/reducers](./src/store/reducers) folder. Then wire it in
the [store.ts](src/store/store.ts) file.

### How to add service

To add separate service:

- Create folder in [src/services](src/services) folder (for example http)
- Add configuration file and setup handler to connect to service (for example api.ts)
- For each resource add separate file (for example users.ts or orders.ts)

## ESLint and Prettier

Project contains ESLint and Prettier configuration to maintain consistent code style. Configuration files can be
found in [.prettierrc](.prettierrc) and [eslint.config.js](eslint.config.js)

This project uses ESLint v9 with the new flat config format, providing enhanced linting capabilities for JavaScript and TypeScript files. The configuration includes:

- TypeScript integration with typescript-eslint
- React Hooks and React Refresh plugins
- Import ordering and organization rules
- Special configurations for test files

## Precommit hooks

Project includes husky and lint-staged to run few commands before commiting. Those commands include running ESLint and
Prettier, so you don't have to worry about constantly running them before each commit.

## GitLab CI/CD

The project uses GitLab CI/CD for automated testing, building, and deployment. The pipeline is configured in [.gitlab-ci.yml](.gitlab-ci.yml) and consists of the following stages:

### Pipeline Stages

1. **Setup**

   - Installs npm dependencies
   - Caches node_modules for subsequent jobs

2. **Test**

   - Runs linting (ESLint)
   - Runs formatting checks (Prettier)
   - Executes test suite (Jest)

3. **Build**

   - Compiles TypeScript and builds the application for production
   - Creates optimized assets in the `dist` directory

4. **Deploy**
   - Deploys the application to AWS S3 buckets
   - Two deployment environments:
     - Development (manual trigger)
     - Production (manual trigger, only on main branch)

### CI/CD Environment Variables

The deployment process uses the following environment variables:

- `AWS_ACCESS_KEY_ID`: AWS access key for authentication
- `AWS_SECRET_ACCESS_KEY`: AWS secret key for authentication
- `AWS_S3_BUCKET`: S3 bucket name
- `AWS_REGION`: AWS region
- `VITE_SERVER_URL`: API server URL for the frontend to connect to

These variables should be configured in GitLab project's CI/CD settings.

## How to create merge requests

- Create a local branch for the task following the naming convention:

```
{branch-type}/{jira-task-id}-{branch-name}
```

> **_NOTE:_** Branch types: feature | fix

- Work on your local implementation, ensuring that your code adheres to linting and type-checking standards.
- Commit changes with messages following the convention:

```
{commit-branch}:{commit-description}
```

- Before pushing your branch, make sure all checks and tests pass. Avoid using bypass flags like --no-verify.

## Code Formatting & Linting

This project uses ESLint and Prettier for code quality and formatting consistency.

### Available Scripts

- `npm run lint` - Run ESLint to check for code quality issues
- `npm run lint:fix` - Run ESLint and fix issues automatically
- `npm run prettier` - Check for formatting issues
- `npm run prettier:fix` - Fix formatting issues automatically
- `npm run format` - Check for linting and formatting issues without fixing
- `npm run format:fix` - Automatically fix linting and formatting issues

### Editor Integration

For the best development experience, install the ESLint and Prettier extensions for your editor:

- **VS Code / Cursor**:
  - [ESLint](https://marketplace.visualstudio.com/items?itemName=dbaeumer.vscode-eslint)
  - [Prettier](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode)

Configure your editor to:

- Format on save
- Fix ESLint issues on save
