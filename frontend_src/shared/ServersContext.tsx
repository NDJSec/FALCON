import { createContext, useState, ReactNode, useEffect } from "react";

type ServersState = Record<string, boolean>;

interface ServersContextProps {
  servers: ServersState;
  setServers: (servers: ServersState) => void;
}

export const ServersContext = createContext<ServersContextProps>({
  servers: {},
  setServers: () => {},
});

interface ServersProviderProps {
  children: ReactNode;
}

export const ServersProvider = ({ children }: ServersProviderProps) => {
  const [servers, setServersState] = useState<ServersState>({});

  const LOCAL_STORAGE_KEY = "falcon_servers";

  // Wrapped setServers to persist changes to localStorage
  const setServers = (newServers: ServersState) => {
    setServersState(newServers);
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(newServers));
    } catch (err) {
      console.error("Failed to save servers to localStorage:", err);
    }
  };

  useEffect(() => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const fetchServers = async () => {
      try {
        const res = await fetch(`${API_URL}/servers`);
        if (!res.ok) throw new Error("Failed to fetch servers");
        const data: Record<string, { url: string; transport: string }> =
          await res.json();

        // Build initial state from backend
        const backendState: ServersState = {};
        Object.keys(data).forEach((key) => (backendState[key] = true));

        // Check localStorage for persisted server states
        const stored = localStorage.getItem(LOCAL_STORAGE_KEY);
        if (stored) {
          const storedState: ServersState = JSON.parse(stored);
          // Merge stored selection with backend servers
          Object.keys(backendState).forEach((key) => {
            if (storedState.hasOwnProperty(key)) {
              backendState[key] = storedState[key];
            }
          });
        }

        setServersState(backendState);
      } catch (err) {
        console.error("Error fetching servers:", err);
      }
    };

    fetchServers();
  }, []);

  return (
    <ServersContext.Provider value={{ servers, setServers }}>
      {children}
    </ServersContext.Provider>
  );
};
