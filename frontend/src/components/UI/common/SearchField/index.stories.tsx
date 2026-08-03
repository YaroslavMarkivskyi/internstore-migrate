import { fn } from '@storybook/test';

import Product1Image from '../../../../assets/products/product_1.png';
import Product2Image from '../../../../assets/products/product_2.png';
import Product3Image from '../../../../assets/products/product_3.png';
import { FoundProduct } from '../../../../types/search/interfaces';

import SearchField from '.';

import type { Meta, StoryObj } from '@storybook/react';

const foundProducts: FoundProduct[] = [
  {
    id: '1',
    name: 'High <b>Protein</b> Fitness Bar, VPLAB, 100g',
    imageSrc: Product1Image,
    onClick: fn(),
  },
  {
    id: '2',
    name: 'High Protein Low Carb Bar, Musashi, 90g',
    imageSrc: Product2Image,
    onClick: fn(),
  },
  {
    id: '3',
    name: 'Zero Bar, 20g Protein, BioTechUSA, 90g',
    imageSrc: Product3Image,
    onClick: fn(),
  },
];

const historyItems = [
  { name: 'Protein bar', onClick: fn(), onDelete: fn() },
  { name: 'VPLAB', onClick: fn(), onDelete: fn() },
  { name: 'Protein', onClick: fn(), onDelete: fn() },
  { name: 'D3', onClick: fn(), onDelete: fn() },
  { name: 'Nutramino', onClick: fn(), onDelete: fn() },
];

const meta: Meta<typeof SearchField> = {
  component: SearchField,
  tags: ['autodocs'],
  args: {
    onChange: fn(),
    onHistoryClear: fn(),
    onShowAllResultsClick: fn(),
  },
};

export default meta;
type Story = StoryObj<typeof SearchField>;

export const Base: Story = {
  args: {
    foundProducts: foundProducts,
    count: 10,
  },
};

export const NotFound: Story = {
  args: {
    foundProducts: [],
  },
};

export const History: Story = {
  args: {
    foundProducts,
    historyItems,
  },
};

export const HistoryEmpty: Story = {};
