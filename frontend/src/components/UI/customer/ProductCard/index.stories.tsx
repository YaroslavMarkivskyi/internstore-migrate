import { fn } from '@storybook/test';

import { IProductPublic } from '../../../../types/products/interfaces';

import ProductCard from './index';

import type { Meta, StoryObj } from '@storybook/react';

const exampleProduct: IProductPublic = {
  id: '10',
  name: 'Protein Whey, Optimum Nutrition, 1.7kg',
  inStock: true,
  description: 'Protein Whey, Optimum Nutrition, 1.7kg',
  price: '24.00',
  category: {
    id: '1',
    name: 'Example category',
  },
  image: 'https://picsum.photos/400',
};

const meta: Meta<typeof ProductCard> = {
  component: ProductCard,
  tags: ['autodocs'],
  args: {
    onClick: fn(),
    product: exampleProduct,
    showCart: true,
  },
};

export default meta;
type Story = StoryObj<typeof ProductCard>;

export const Base: Story = {};

export const NoImage: Story = {
  args: {
    product: { ...exampleProduct, image: undefined },
  },
};

export const NotInStock: Story = {
  args: {
    product: { ...exampleProduct, inStock: false },
  },
};

export const NoCart: Story = {
  args: {
    showCart: false,
  },
};

export const OverflowedText: Story = {
  args: {
    product: {
      ...exampleProduct,
      name: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nam ornare auctor venenatis.',
    },
  },
};
