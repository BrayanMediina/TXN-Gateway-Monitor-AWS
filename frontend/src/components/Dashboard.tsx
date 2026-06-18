import { useEffect, useState } from "react";
import AlertBanner from "./AlertBanner";
import MetricsChart from "./MetricsChart";
import SimulatorPanel from "./SimulatorPanel";
import TransactionTable from "./TransactionTable";
import { useTransactions } from "../hooks/useTransactions";

export default function Dashboard() {
  const { transactions, metrics, loading, error, refresh } = useTransactions();
  const [activeAlerts, setActiveAlerts] = useState<string[]>([]);

  useEffect(() => {
    const interval = setInterval(refresh, 10_000); // Poll cada 10 seg
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-mono">
      {/* Header */}
      <header className="border-b border-orange-500/30 bg-gray-900 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-orange-400">
              TXN Gateway Monitor
            </h1>
            <p className="text-xs text-gray-500">
              Analista Automatización · Gateway de Mensajería
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-xs text-green-400">Sistema operativo</span>
          </div>
        </div>
      </header>

      {/* Alert Banner */}
      {activeAlerts.length > 0 && (
        <AlertBanner alerts={activeAlerts} onDismiss={() => setActiveAlerts([])} />
      )}

      {/* Main Grid */}
      <main className="grid grid-cols-12 gap-4 p-6">
        {/* KPI Cards */}
        <section className="col-span-12 grid grid-cols-4 gap-4">
          {metrics ? (
            <>
              <KPICard label="Transacciones / hr" value={metrics.txnPerHour} color="orange" />
              <KPICard label="Tasa de éxito" value={`${metrics.successRate}%`} color="green" />
              <KPICard label="Mensajes DLQ" value={metrics.dlqCount} color="red" />
              <KPICard label="Latencia P95 (ms)" value={metrics.p95Latency} color="blue" />
            </>
          ) : (
            <div className="col-span-4 text-xs text-gray-500">
              {loading ? "Cargando métricas..." : "Sin datos de métricas"}
            </div>
          )}
        </section>

        {/* Chart */}
        <section className="col-span-8 rounded-lg border border-gray-800 bg-gray-900 p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-400">
            Flujo de transacciones (últimas 2 horas)
          </h2>
          <MetricsChart data={metrics?.timeline ?? []} />
        </section>

        {/* Simulator */}
        <aside className="col-span-4 rounded-lg border border-gray-800 bg-gray-900 p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-400">
            Simulador de transacciones
          </h2>
          <SimulatorPanel onPublished={refresh} />
        </aside>

        {/* Transaction Table */}
        <section className="col-span-12 rounded-lg border border-gray-800 bg-gray-900 p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-400">
            Transacciones recientes
          </h2>
          {loading ? (
            <p className="text-xs text-gray-500">Cargando...</p>
          ) : error ? (
            <p className="text-xs text-red-400">Error cargando datos: {error}</p>
          ) : (
            <TransactionTable transactions={transactions} />
          )}
        </section>
      </main>
    </div>
  );
}

function KPICard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color: "orange" | "green" | "red" | "blue";
}) {
  const colorMap = {
    orange: "border-orange-500/40 text-orange-400",
    green: "border-green-500/40 text-green-400",
    red: "border-red-500/40 text-red-400",
    blue: "border-blue-500/40 text-blue-400",
  };
  return (
    <div className={`rounded-lg border bg-gray-900 p-4 ${colorMap[color]}`}>
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${colorMap[color].split(" ")[1]}`}>
        {value}
      </p>
    </div>
  );
}
