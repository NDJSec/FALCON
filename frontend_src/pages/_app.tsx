import type { AppProps } from "next/app";
import "../styles/global.css";

// This is the root component for your Next.js application.
// The global CSS is imported here to apply styles to all pages.
export default function App({ Component, pageProps }: AppProps) {
  return <Component {...pageProps} />;
}
