const isoDateFormat = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/;

export default (_key: string, value: unknown) => {
  if (typeof value === 'string' && isoDateFormat.test(value)) {
    return new Date(value);
  }
  return value;
};
