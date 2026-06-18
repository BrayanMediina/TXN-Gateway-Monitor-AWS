import type { Transaction } from "../services/api";

const STATUS_STYLES: Record<string, string> = {
  PROCESSED: "bg-green-500/20 text-green-400 border border-green-500/30",
  PENDING: "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30",
  FAILED: "bg-red-500/20 text-red-400 border border-red-500/30",
  RETRYING: "bg-blue-500/20 text-blue-400 border border-blue-500/30",
};

interface Props {
  transactions: Transaction[];
}

export default function TransactionTable({ transactions }: Props) {
  if (transactions.length === 0) {
    return (
      <p className="text-xs text-gray-600 py-4 text-center">
        No hay transacciones recientes
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-800 text-gray-500">
            <th className="pb-2 text-left font-medium">TXN ID</th>
            <th className="pb-2 text-left font-medium">Tipo</th>
            <th className="pb-2 text-right font-medium">Monto</th>
            <th className="pb-2 text-left font-medium">Origen</th>
            <th className="pb-2 text-left font-medium">Destino</th>
            <th className="pb-2 text-center font-medium">Estado</th>
            <th className="pb-2 text-right font-medium">Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((txn) => (
            <tr
              key={txn.txnId}
              className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
            >
              <td className="py-2 text-gray-300 font-mono">
                {txn.txnId.slice(0, 8)}…
              </td>
              <td className="py-2 text-gray-400">{txn.txn_type}</td>
              <td className="py-2 text-right text-gray-200">
                {parseFloat(txn.amount).toLocaleString("es-MX", {
                  style: "currency",
                  currency: txn.currency || "USD",
                })}
              </td>
              <td className="py-2 text-gray-500">
                {txn.source_account?.slice(-6) ?? "—"}
              </td>
              <td className="py-2 text-gray-500">
                {txn.destination_account?.slice(-6) ?? "—"}
              </td>
              <td className="py-2 text-center">
                <span
                  className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
                    STATUS_STYLES[txn.status] ?? "text-gray-400"
                  }`}
                >
                  {txn.status}
                </span>
              </td>
              <td className="py-2 text-right text-gray-600">
                {new Date(txn.timestamp).toLocaleTimeString("es-MX")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
