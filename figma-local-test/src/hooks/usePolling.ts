import { useState, useEffect, useRef, useCallback } from 'react';

interface UsePollingResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function usePolling<T>(
  fetchFn: () => Promise<T>,
  intervalMs: number
): UsePollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const isMounted = useRef(true);
  const fetchFnRef = useRef(fetchFn);
  
  // Keep the latest fetch function in a ref so we don't restart intervals on every render
  useEffect(() => {
    fetchFnRef.current = fetchFn;
  }, [fetchFn]);

  const executeFetch = useCallback(async () => {
    try {
      // Don't set loading to true on subsequent requests to avoid UI flicker
      const result = await fetchFnRef.current();
      if (isMounted.current) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      if (isMounted.current) {
        setError(err instanceof Error ? err : new Error(String(err)));
        // Intentionally NOT clearing 'data' so UI retains last known good state
      }
    } finally {
      if (isMounted.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMounted.current = true;
    
    // Initial fetch
    executeFetch();

    // Start polling if interval is greater than 0
    let intervalId: number | undefined;
    if (intervalMs > 0) {
      intervalId = window.setInterval(executeFetch, intervalMs);
    }

    return () => {
      isMounted.current = false;
      if (intervalId !== undefined) {
        window.clearInterval(intervalId);
      }
    };
  }, [intervalMs, executeFetch]);

  return { data, loading, error, refetch: executeFetch };
}
