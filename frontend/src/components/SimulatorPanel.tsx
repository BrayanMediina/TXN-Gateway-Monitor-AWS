import { useState } from "react";
import { publishEvent, type TransactionPayload } from "../services/api";

interface Props {
  onPublished: () => void;
}

const TXN_TYPES = ["PAYMENT", "TRANSFER", "WITHDRAWAL", "DEPOSIT"] as const;

const DEFAULT_FORM: TransactionPayload = {
  amount: 1500,
  txn_type: "PAYMENT",
  source_account: "1234567890AB",
  destination_account: "0987654321CD",
  currency: "USD",
};

export default function SimulatorPanel({ onPublished }: Props) {
  const [form, setForm] = useState<TransactionPayload>(DEFAULT_FORM);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("loading");
    setMessage("");

    try {
      const result = await publishEvent(form);
      setStatus("success");
      setMessage(`✓ TXN ${result.txn_id.slice(0, 8)} publicada`);
      onPublished();
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "Error desconocido");
    }
  };

  const simulateHighValue = () =>
    setForm((f) => ({ ...f, amount: 75000, txn_type: "TRANSFER" }));

  const simulateNormal = () =>
    setForm((f) => ({ ...f, amount: 1500, txn_type: "PAYMENT" }));

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {/* Quick actions */}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={simulateNormal}
          className="flex-1 rounded border border-gray-700 bg-gray-800 px-2 py-1 text-[10px] text-gray-400 hover:border-gray-500 transition-colors"
        >
          Normal
        </button>
        <button
          type="button"
          onClick={simulateHighValue}
          className="flex-1 rounded border border-red-700/50 bg-red-950/30 px-2 py-1 text-[10px] text-red-400 hover:border-red-500 transition-colors"
        >
          Alto Valor ⚠
        </button>
      </div>

      {/* Amount */}
      <div>
        <label className="block text-[10px] text-gray-500 mb-1">Monto (USD)</label>
        <input
          type="number"
          min={1}
          max={1_000_000}
          step={0.01}
          value={form.amount}
          onChange={(e) =>
            setForm((f) => ({ ...f, amount: parseFloat(e.target.value) || 0 }))
          }
          className="w-full rounded border border-gray-700 bg-gray-800 px-2 py-1.5 text-xs text-gray-200 focus:border-orange-500 focus:outline-none"
        />
      </div>

      {/* TXN Type */}
      <div>
        <label className="block text-[10px] text-gray-500 mb-1">Tipo</label>
        <select
          value={form.txn_type}
          onChange={(e) =>
            setForm((f) => ({
              ...f,
              txn_type: e.target.value as TransactionPayload["txn_type"],
            }))
          }
          className="w-full rounded border border-gray-700 bg-gray-800 px-2 py-1.5 text-xs text-gray-200 focus:border-orange-500 focus:outline-none"
        >
          {TXN_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {/* Accounts */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-[10px] text-gray-500 mb-1">Cuenta origen</label>
          <input
            type="text"
            minLength={10}
            maxLength={20}
            value={form.source_account}
            onChange={(e) =>
              setForm((f) => ({ ...f, source_account: e.target.value }))
            }
            className="w-full rounded border border-gray-700 bg-gray-800 px-2 py-1.5 text-xs text-gray-200 focus:border-orange-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-[10px] text-gray-500 mb-1">Cuenta destino</label>
          <input
            type="text"
            minLength={10}
            maxLength={20}
            value={form.destination_account}
            onChange={(e) =>
              setForm((f) => ({ ...f, destination_account: e.target.value }))
            }
            className="w-full rounded border border-gray-700 bg-gray-800 px-2 py-1.5 text-xs text-gray-200 focus:border-orange-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={status === "loading"}
        className="w-full rounded bg-orange-500 px-3 py-2 text-xs font-semibold text-gray-950 hover:bg-orange-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {status === "loading" ? "Publicando…" : "Publicar Transacción"}
      </button>

      {/* Status message */}
      {message && (
        <p
          className={`text-[10px] text-center ${
            status === "success" ? "text-green-400" : "text-red-400"
          }`}
        >
          {message}
        </p>
      )}
    </form>
  );
}
