import { z } from 'zod';

import { IProductImage } from '../../types/products/interfaces';

export const MAX_FILE_SIZE = 20 * 1024 * 1024;
export const MAX_IMAGES = 4;

export const productSchema = z
  .object({
    name: z
      .string()
      .min(2, 'Must be at least 2 characters')
      .max(250, 'Must not exceed 250 characters'),
    // Catalog category ids are UUIDs, not numeric (see
    // internstore-migrate/services/catalog/src/catalog/schemas.py) --
    // this used to coerce to Number, which turned every real category id
    // into NaN and made the form permanently fail "Invalid category".
    category: z.string().min(1, 'Category is required'),
    price: z
      .string()
      .refine(
        val => {
          const num = Number(val);
          return !isNaN(num);
        },
        { message: 'Must be a number' }
      )
      .refine(
        val => {
          const num = Number(val);
          return num > 0 && num < 1000;
        },
        { message: 'Must be between 0 and 1000' }
      )
      .refine(
        val => {
          const parts = val.split('.');
          return parts.length === 1 || parts[1].length <= 2;
        },
        { message: 'Must have at most 2 decimal places' }
      ),
    minTemperature: z.preprocess(val => {
      if (val === '' || val === null || val === undefined) return undefined;
      return Number(val);
    }, z.number().optional()),
    maxTemperature: z.preprocess(val => {
      if (val === '' || val === null || val === undefined) return undefined;
      return Number(val);
    }, z.number().optional()),
    description: z
      .string()
      .max(500, 'Must not exceed 500 characters')
      .transform(val => (val === '' ? undefined : val))
      .optional(),
    photos: z
      .union([z.custom<IProductImage>(), z.instanceof(File)])
      .array()
      .max(MAX_IMAGES, `Only ${MAX_IMAGES} images are allowed`)
      .refine(
        photos => {
          if (photos.length === 0) {
            return true;
          }
          const files = photos.filter(photo => photo instanceof File);
          if (files.length === 0) {
            return true;
          }
          return files.some(file => file.size <= MAX_FILE_SIZE);
        },
        {
          message: 'Image size must be 20MB or less',
        }
      )
      .optional(),
    photosToDelete: z.custom<IProductImage>().array().default([]),
  })
  .refine(
    data => {
      if (
        data.minTemperature !== undefined &&
        data.maxTemperature !== undefined
      ) {
        return data.minTemperature < data.maxTemperature;
      }
      return true;
    },
    {
      message: 'Must be less than max temperature',
      path: ['minTemperature'],
    }
  )
  .refine(
    data => {
      if (
        data.minTemperature !== undefined &&
        data.maxTemperature !== undefined
      ) {
        return data.maxTemperature > data.minTemperature;
      }
      return true;
    },
    {
      message: 'Must be greater than min temperature',
      path: ['maxTemperature'],
    }
  );

export type ProductFormDataInput = z.input<typeof productSchema>;
export type ProductFormDataOutput = z.infer<typeof productSchema>;
