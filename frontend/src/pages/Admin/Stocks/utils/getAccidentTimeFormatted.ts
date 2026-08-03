export default () => {
  const now: Date = new Date();

  const randomMinutesAgo: number = Math.floor(Math.random() * 300) + 1;
  const pastDate: Date = new Date(now.getTime() - randomMinutesAgo * 60000);

  const options: Intl.DateTimeFormatOptions = {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  };
  const formattedTime: string = pastDate.toLocaleTimeString(undefined, options);

  const hours: number = Math.floor(randomMinutesAgo / 60);
  const minutes: number = randomMinutesAgo % 60;

  const agoParts: string[] = [];
  if (hours > 0) agoParts.push(`${hours}h`);
  if (minutes > 0 || hours === 0) agoParts.push(`${minutes} min`);

  const agoStr: string = agoParts.join(' ') + ' ago';

  return `${formattedTime}, ${agoStr}`;
};
