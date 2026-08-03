import {
  TypedUseSelectorHook,
  useDispatch as useReduxDispatch,
  useSelector as useReduxSelector,
} from 'react-redux';

import {
  combineReducers,
  configureStore,
  PayloadAction,
} from '@reduxjs/toolkit';

import { persistReducer, persistStore } from 'redux-persist';
import localStorage from 'redux-persist/lib/storage';
import sessionStorage from 'redux-persist/lib/storage/session';

import authReducer from './reducers/auth';
import categoryReducer from './reducers/category';
import notificationsReducer from './reducers/notifications';
import recentProductsReducer from './reducers/recentViewedProducts';
import searchHistoryReducer from './reducers/search';

const authPersistConfig = {
  key: 'auth',
  storage: sessionStorage,
};

const searchHistoryPersistConfig = {
  key: 'searchHistory',
  storage: localStorage,
};

const recentProductsPersistConfig = {
  key: 'recentProducts',
  storage: localStorage,
};

const notificationsPersistConfig = {
  key: 'notifications',
  storage: localStorage,
};

const persistedAuthReducer = persistReducer(authPersistConfig, authReducer);
const persistedSearchHistoryReducer = persistReducer(
  searchHistoryPersistConfig,
  searchHistoryReducer
);
const persistedRecentProductsReducer = persistReducer(
  recentProductsPersistConfig,
  recentProductsReducer
);

const persistedNotificationsReducer = persistReducer(
  notificationsPersistConfig,
  notificationsReducer
);

const combinedReducer = combineReducers({
  auth: persistedAuthReducer,
  searchHistory: persistedSearchHistoryReducer,
  category: categoryReducer,
  recentProducts: persistedRecentProductsReducer,
  notifications: persistedNotificationsReducer,
});

const rootReducer = (state: RootState | undefined, action: PayloadAction) => {
  if (action.type === 'RESET') {
    state = undefined;
  }
  return combinedReducer(state, action);
};

export const store = configureStore({
  reducer: rootReducer,
  middleware: getDefaultMiddleware =>
    getDefaultMiddleware({
      serializableCheck: false,
    }),
});

export const persistor = persistStore(store);

export type RootState = ReturnType<typeof combinedReducer>;
export type AppDispatch = typeof store.dispatch;

export const useDispatch: () => AppDispatch = useReduxDispatch;
export const useSelector: TypedUseSelectorHook<RootState> = useReduxSelector;
