import { createSlice, PayloadAction } from '@reduxjs/toolkit';

const MAX_ITEMS = 15;

const initialState: {
  productIds: string[];
} = {
  productIds: [],
};

const recentProductsSlice = createSlice({
  name: 'recentProducts',
  initialState,
  reducers: {
    addRecentProductId: (state, action: PayloadAction<string>) => {
      const existingIndex = state.productIds.indexOf(action.payload);
      if (existingIndex !== -1) {
        state.productIds.splice(existingIndex, 1);
      }
      state.productIds.unshift(action.payload);
      if (state.productIds.length > MAX_ITEMS) {
        state.productIds.pop();
      }
    },
    clearRecentProductIds: state => {
      state.productIds = [];
    },
  },
});

export const { addRecentProductId, clearRecentProductIds } =
  recentProductsSlice.actions;
export default recentProductsSlice.reducer;
