import { RefObject, useCallback, useEffect, useState } from 'react';

export default (
  containerRef: RefObject<HTMLElement | null>,
  itemWidth: number,
  gap: number,
  rows: number = 3
): number => {
  const [itemsPerPage, setItemsPerPage] = useState(0);

  const calculateItems = useCallback(() => {
    if (!containerRef.current?.offsetWidth) return;
    const containerWidth = containerRef.current.offsetWidth;
    const itemsPerRow = Math.floor((containerWidth + gap) / (itemWidth + gap));
    setItemsPerPage(itemsPerRow * rows);
  }, [containerRef, itemWidth, gap, rows]);

  useEffect(() => {
    calculateItems();

    const observer = new ResizeObserver(() => {
      calculateItems();
    });

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => {
      observer.disconnect();
    };
  }, [calculateItems]);

  return itemsPerPage;
};
