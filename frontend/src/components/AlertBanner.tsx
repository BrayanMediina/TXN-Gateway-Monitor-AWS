interface Props {
  alerts: string[];
  onDismiss: () => void;
}

export default function AlertBanner({ alerts, onDismiss }: Props) {
  return (
    <div className="border-b border-red-500/30 bg-red-950/50 px-6 py-3">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-2">
          <span className="mt-0.5 text-red-400">⚠</span>
          <div>
            <p className="text-xs font-semibold text-red-400">
              {alerts.length} alerta{alerts.length > 1 ? "s" : ""} activa
              {alerts.length > 1 ? "s" : ""}
            </p>
            <ul className="mt-1 space-y-0.5">
              {alerts.map((alert, idx) => (
                <li key={idx} className="text-xs text-red-300">
                  {alert}
                </li>
              ))}
            </ul>
          </div>
        </div>
        <button
          onClick={onDismiss}
          className="shrink-0 text-xs text-red-500 hover:text-red-300 transition-colors"
        >
          Descartar
        </button>
      </div>
    </div>
  );
}
