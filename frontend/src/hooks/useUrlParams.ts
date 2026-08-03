import { useCallback, useMemo } from 'react';

import { useSearchParams } from 'react-router-dom';

export interface UrlParamConfig<T> {
  key: keyof T;
  parser: (value: string) => T[keyof T];
  serializer?: (value: T[keyof T]) => string;
}

const UseUrlParams = <T>(
  configs: UrlParamConfig<T>[],
  defaults: Partial<T> = {}
) => {
  const [searchParams, setSearchParams] = useSearchParams();

  const params = useMemo(() => {
    const result: Partial<T> = { ...defaults };
    configs.forEach(({ key, parser }) => {
      const raw = searchParams.get(key as string);
      if (raw !== null) {
        result[key] = parser(raw);
      }
    });
    return result as T;
  }, [searchParams]);

  const setParams = useCallback(
    (newValues: Partial<T>) => {
      setSearchParams(prev => {
        const params = new URLSearchParams(prev.toString());
        let changed = false;
        configs.forEach(({ key, serializer }) => {
          if (Object.prototype.hasOwnProperty.call(newValues, key)) {
            changed = true;
            const val = newValues[key];
            if (val == null || (serializer && serializer(val) === '')) {
              params.delete(key as string);
            } else if (serializer) {
              params.set(key as string, serializer(val));
            } else {
              params.set(key as string, String(val));
            }
          }
        });
        if (changed) params.set('page', '1');
        return params;
      });
    },
    [setSearchParams, configs]
  );

  return [params, setParams] as const;
};

export default UseUrlParams;
