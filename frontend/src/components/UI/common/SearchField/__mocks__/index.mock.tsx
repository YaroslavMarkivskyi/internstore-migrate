import {
  FoundProduct,
  IHistoryItem,
} from '../../../../../types/search/interfaces';

const MAX_SEARCH_RESULTS_COUNT_DROPDOWN = 3;

const MockSearchField = jest.fn(
  (props: {
    value?: string;
    onChange?: (val: string) => void;
    onSubmit?: (val: string) => void;
    foundProducts?: FoundProduct[];
    historyItems?: IHistoryItem[];
    onHistoryClear?: () => void;
    onShowAllResultsClick?: () => void;
    count?: number;
  }) => {
    return (
      <div data-testid="search-field">
        <input
          data-testid="search-input"
          value={props.value || ''}
          onChange={e => {
            const value = (e.target as HTMLInputElement).value;
            props.onChange?.(value);
          }}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              props.onSubmit?.(props.value || '');
            }
          }}
        />

        {props.foundProducts && props.foundProducts.length > 0 && (
          <div data-testid="search-results">
            {props.foundProducts.map((product: FoundProduct) => (
              <div
                key={product.id}
                data-testid={`product-${product.id}`}
                onClick={product.onClick}
              >
                {product.name}
              </div>
            ))}
          </div>
        )}

        {props.historyItems && props.historyItems.length > 0 && (
          <div data-testid="search-history">
            {props.historyItems.map((item: IHistoryItem, index: number) => (
              <div
                key={index}
                data-testid={`history-item-${index}`}
                onClick={item.onClick}
              >
                {item.name}
                <button
                  data-testid={`delete-history-${index}`}
                  onClick={e => {
                    e.stopPropagation();
                    item.onDelete();
                  }}
                >
                  Delete
                </button>
              </div>
            ))}
            <button data-testid="clear-history" onClick={props.onHistoryClear}>
              Clear History
            </button>
          </div>
        )}

        {props.count && props.count > MAX_SEARCH_RESULTS_COUNT_DROPDOWN && (
          <button
            data-testid="show-all-results"
            onClick={props.onShowAllResultsClick}
          >
            Show all results
          </button>
        )}
      </div>
    );
  }
);

export default MockSearchField;
