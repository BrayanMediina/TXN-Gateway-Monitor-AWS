import { useCallback, useEffect, useState } from "react";
import { getMetrics, getTransactions, type Metrics, type Transaction } from "../services/api";

interface UseTransactionsResult {
  transactions: Transaction[];
  metrics: Metrics | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useTransactions(): UseTransactionsResult {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      setError(null);
      const [txns, metricsData] = await Promise.all([
        getTransactions(50),
        getMetrics(),
      ]);
      setTransactions(txns);
      setMetrics(metricsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error cargando datos");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return { transactions, metrics, loading, error, refresh: fetchAll };
}
