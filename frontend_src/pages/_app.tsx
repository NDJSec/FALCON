import type { AppProps } from "next/app";
import "../styles/global.css";
import { ServersProvider } from "../shared/ServersContext";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <ServersProvider>
      <Component {...pageProps} />
    </ServersProvider>
  );
}