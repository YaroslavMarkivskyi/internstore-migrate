import {
  createContext,
  Dispatch,
  ReactNode,
  SetStateAction,
  useContext,
  useState,
} from 'react';

import {
  addItemToCart,
  getCart,
  getCartItems,
  removeItemFromCart,
  updateCartItemQuantity,
} from '@services/http/public/cart';
import showToast from '@utils/showToast';

import { ICart, ICartItem } from '../types/cart/interfaces';
import { PaginationQueryParams } from '../types/pagination/interfaces';

interface CartContextType {
  cartItemsIds: Set<string>;
  cart?: ICart;
  items: ICartItem[];
  hasMore: boolean;
  count: number;
  isLoading: boolean;
  addToCart: (productId: string) => Promise<void>;
  setCartItemsIds: Dispatch<SetStateAction<Set<string>>>;
  removeFromCart: (productId: string) => Promise<void>;
  fetchCartItems: (
    filterParams: Omit<PaginationQueryParams, 'limit'>,
    inplace?: boolean
  ) => Promise<void>;
  fetchCart: () => Promise<void>;
  editQuantity: (productId: string, newVal: number) => Promise<void>;
  totalCost: string;
  setEstimatedTotalCost: Dispatch<SetStateAction<number | null>>;
  calculateEstimatedTotal: (
    oldQuantity: number,
    newQuantity: number,
    productPrice: number
  ) => number;
}

const CartContext = createContext<CartContextType | undefined>(undefined);

export const useCart = (): CartContextType => {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCart must be used within a UseCart');
  }
  return context;
};

export const CartProvider = ({ children }: { children: ReactNode }) => {
  const [cartItemsIds, setCartItemsIds] = useState<Set<string>>(new Set());
  const [items, setItems] = useState<ICartItem[]>([]);
  const [cart, setCart] = useState<ICart>();
  const [hasMore, setHasMore] = useState(false);
  const [count, setCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [estimatedTotalCost, setEstimatedTotalCost] = useState<number | null>(
    null
  );

  const totalCost = estimatedTotalCost
    ? estimatedTotalCost.toFixed(2)
    : cart
      ? cart.totalCost
      : '0.00';

  const fetchCartItems = async (
    filterParams: PaginationQueryParams,
    inplace?: boolean
  ) => {
    try {
      setIsLoading(true);
      const data = await getCartItems({ ...filterParams, limit: 8 });
      let newItems;
      if (inplace) {
        newItems = data.results;
      } else {
        newItems = data.results.filter(
          item =>
            !items.some(existing => existing.product.id === item.product.id)
        );
      }
      setItems(prev => (inplace ? newItems : [...prev, ...newItems]));
      setHasMore(!!data.next);
      setCount(data.count);
      setCartItemsIds(prevState => {
        const newSet = new Set(prevState);
        for (const item of newItems) {
          newSet.add(item.product.id);
        }
        return newSet;
      });
    } catch {
      showToast({
        message: 'Error fetching products from cart',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const fetchCart = async () => {
    setIsLoading(true);
    try {
      const data = await getCart();
      setCart(data);
      setEstimatedTotalCost(null);
    } catch {
      showToast({
        message: 'Error fetching cart details',
        type: 'error',
      });
    }
    setIsLoading(false);
  };

  const editQuantity = async (productId: string, newVal: number) => {
    await updateCartItemQuantity(productId, newVal);
    await fetchCart();
  };

  const calculateEstimatedTotal = (
    oldQuantity: number,
    newQuantity: number,
    productPrice: number
  ) => {
    const quantityDiff = newQuantity - oldQuantity;
    const delta = productPrice * quantityDiff;
    return parseFloat(totalCost) + delta;
  };

  const addToCart = async (productId: string) => {
    try {
      setCartItemsIds(prev => {
        const newSet = new Set(prev);
        newSet.add(productId);
        return newSet;
      });
      setCount(prev => prev + 1);
      await addItemToCart(productId);
      await fetchCartItems({ offset: 0 }, true);
      await fetchCart();
    } catch {
      showToast({
        message: 'Error adding product to cart.',
        type: 'error',
      });
      setCartItemsIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(productId);
        return newSet;
      });
      setCount(prev => prev - 1);
    }
  };

  const removeFromCart = async (productId: string) => {
    const itemToDelete = items.find(item => item.product.id === productId);
    try {
      setCartItemsIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(productId);
        return newSet;
      });
      setCount(prev => prev - 1);
      if (itemToDelete) {
        setItems(prev => prev.filter(item => item.product.id !== productId));
      }
      await removeItemFromCart(productId);
      await fetchCart();
    } catch {
      showToast({
        message: 'Error removing product from cart.',
        type: 'error',
      });
      setCartItemsIds(prev => {
        const newSet = new Set(prev);
        newSet.add(productId);
        return newSet;
      });
      setCount(prev => prev + 1);
      if (itemToDelete) {
        setItems(prev => [...prev, itemToDelete]);
      }
    }
  };

  return (
    <CartContext.Provider
      value={{
        cartItemsIds,
        addToCart,
        setCartItemsIds,
        removeFromCart,
        items,
        fetchCartItems,
        fetchCart,
        editQuantity,
        hasMore,
        isLoading,
        cart,
        count,
        totalCost,
        calculateEstimatedTotal,
        setEstimatedTotalCost,
      }}
    >
      {children}
    </CartContext.Provider>
  );
};
