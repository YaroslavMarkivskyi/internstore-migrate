import { initializeApp } from 'firebase/app';
import { connectAuthEmulator, getAuth } from 'firebase/auth';

const FIREBASE_API_KEY = process.env.FIREBASE_API_KEY ?? 'demo-api-key';
const FIREBASE_PROJECT_ID =
  process.env.FIREBASE_PROJECT_ID ?? 'internstore-dev';
const FIREBASE_AUTH_EMULATOR_HOST = process.env.FIREBASE_AUTH_EMULATOR_HOST;

const app = initializeApp({
  apiKey: FIREBASE_API_KEY,
  authDomain: `${FIREBASE_PROJECT_ID}.firebaseapp.com`,
  projectId: FIREBASE_PROJECT_ID,
});

export const auth = getAuth(app);

if (FIREBASE_AUTH_EMULATOR_HOST) {
  // "origin" -> use the page's own origin, so the SDK's
  // identitytoolkit/securetoken calls go through whatever host served the
  // app (localhost:8443, an ngrok tunnel, …) and nginx forwards them to
  // the emulator. A bare "host:port" keeps the old direct-to-emulator
  // behaviour; a full URL is used as-is.
  const emulatorUrl =
    FIREBASE_AUTH_EMULATOR_HOST === 'origin'
      ? window.location.origin
      : /^https?:\/\//.test(FIREBASE_AUTH_EMULATOR_HOST)
        ? FIREBASE_AUTH_EMULATOR_HOST
        : `http://${FIREBASE_AUTH_EMULATOR_HOST}`;
  connectAuthEmulator(auth, emulatorUrl);
}
