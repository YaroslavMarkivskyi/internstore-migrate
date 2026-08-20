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
  connectAuthEmulator(auth, `http://${FIREBASE_AUTH_EMULATOR_HOST}`);
}
