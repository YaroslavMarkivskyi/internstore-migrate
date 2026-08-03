import { createSlice, PayloadAction } from '@reduxjs/toolkit';

import { RootState } from '../store';

import { ICategory, ICategoryState } from '../../types/categories/interfaces';

const initialState: ICategoryState = {
  categories: {},
};

const categorySlice = createSlice({
  name: 'category',
  initialState,
  reducers: {
    setCategories: (state, action: PayloadAction<ICategory[]>) => {
      for (const category of action.payload) {
        state.categories[category.id] = category.name;
      }
    },
  },
});

export const { setCategories } = categorySlice.actions;

export const selectCategories = (state: RootState) => state.category.categories;

export default categorySlice.reducer;
