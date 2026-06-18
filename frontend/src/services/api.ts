import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL ?? "/api";

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 10_000,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ?? error.message ?? "Error desconocido";
    return Promise.reject(new Error(message));
  }
);

export interface TransactionPayload {
  amount: number;
  txn_type: "PAYMENT" | "TRANSFER" | "WITHDRAWAL" | "DEPOSIT";
  source_account: string;
  destination_account: string;
  currency?: string;
  metadata?: Record<string, unknown>;
}

export interface TransactionResponse {
  txn_id: string;
  status: "PENDING" | "PROCESSED" | "FAILED" | "RETRYING";
  sns_message_id: string;
  timestamp: string;
  message: string;
}

export interface Transaction {
  txnId: string;
  timestamp: string;
  amount: string;
  currency: string;
  txn_type: string;
  source_account: string;
  destination_account: string;
  status: "PENDING" | "PROCESSED" | "FAILED" | "RETRYING";
  sqs_message_id?: string;
  retry_count?: number;
}

export interface Metrics {
  txnPerHour: number;
  successRate: number;
  dlqCount: number;
  p95Latency: number;
  timeline: Array<{ time: string; processed: number; failed: number }>;
}

export const publishEvent = async (
  payload: TransactionPayload
): Promise<TransactionResponse> => {
  const { data } = await apiClient.post<TransactionResponse>(
    "/events/publish",
    payload
  );
  return data;
};

export const getTransaction = async (txnId: string): Promise<Transaction> => {
  const { data } = await apiClient.get<Transaction>(`/events/${txnId}`);
  return data;
};

export const getMetrics = async (): Promise<Metrics> => {
  const { data } = await apiClient.get<Metrics>("/metrics");
  return data;
};

export const getTransactions = async (
  limit = 50
): Promise<Transaction[]> => {
  const { data } = await apiClient.get<Transaction[]>(
    `/events?limit=${limit}`
  );
  return data;
};
