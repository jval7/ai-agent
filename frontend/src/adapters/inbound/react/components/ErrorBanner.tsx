interface ErrorBannerProps {
  message: string;
  className?: string;
}

const defaultClassName = "rounded-md bg-red-100 px-3 py-2 text-sm text-red-700";

export function ErrorBanner(props: ErrorBannerProps) {
  const className =
    props.className === undefined ? defaultClassName : `${defaultClassName} ${props.className}`;
  return <p className={className}>{props.message}</p>;
}
