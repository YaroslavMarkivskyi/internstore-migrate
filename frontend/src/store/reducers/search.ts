import { createSlice, PayloadAction } from '@reduxjs/toolkit';

import { RootState } from '../store';

import { MAX_SEARCH_HISTORY_ITEMS } from '../../constants/search';
import {
  SearchHistoryActionPayload,
  SearchHistoryState,
} from '../../types/search/interfaces';

const initialState: SearchHistoryState = {
  admin: [],
  customer: [],
};

const searchHistorySlice = createSlice({
  name: 'searchHistory',
  initialState,
  reducers: {
    addSearchHistoryItem: (
      state,
      action: PayloadAction<SearchHistoryActionPayload>
    ) => {
      const { query, area } = action.payload;
      if (!query.trim()) return;

      state[area] = state[area].filter(item => item.query !== query);
      state[area].unshift({ query });

      if (state[area].length > MAX_SEARCH_HISTORY_ITEMS) {
        state[area] = state[area].slice(0, MAX_SEARCH_HISTORY_ITEMS);
      }
    },
    removeSearchHistoryItem: (
      state,
      action: PayloadAction<SearchHistoryActionPayload>
    ) => {
      const { query, area } = action.payload;
      state[area] = state[area].filter(item => item.query !== query);
    },
    clearSearchHistory: (
      state,
      action: PayloadAction<{ area: 'admin' | 'customer' }>
    ) => {
      const { area } = action.payload;
      state[area] = [];
    },
  },
});

export const {
  addSearchHistoryItem,
  removeSearchHistoryItem,
  clearSearchHistory,
} = searchHistorySlice.actions;

export const selectSearchHistory =
  (area: 'admin' | 'customer') => (state: RootState) =>
    state.searchHistory[area];

export default searchHistorySlice.reducer;
