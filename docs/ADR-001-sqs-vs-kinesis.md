# ADR-001: SQS vs Kinesis para mensajería transaccional

**Estado:** Aceptado  
**Fecha:** 2024-01-01  
**Contexto:** TXN Gateway Monitor

## Contexto

Se requiere una cola de mensajes para desacoplar la ingesta de eventos transaccionales de su procesamiento. Las dos opciones principales en AWS son SQS y Kinesis Data Streams.

## Decisión

Usar **Amazon SQS** (Standard Queue) con Dead Letter Queue.

## Razonamiento

| Criterio | SQS | Kinesis |
|---|---|---|
| **DLQ nativa** | Sí, integrada | No (requiere Lambda adicional) |
| **Reintentos automáticos** | Sí (maxReceiveCount) | Manual |
| **Free Tier** | 1M requests/mes | Sin free tier generoso |
| **Latencia** | ~milliseconds | ~milliseconds (similar) |
| **Throughput** | Hasta 3,000 msg/s estándar | Hasta 1,000 registros/shard/s |
| **Ordering** | Sin garantía (FIFO disponible) | Por shard |
| **Retención** | Hasta 14 días | Hasta 7 días (365 con tiered) |
| **Complejidad operacional** | Baja | Media-Alta |

## Consecuencias

**Positivas:**
- DLQ nativa elimina la necesidad de lógica de reintentos personalizada en el productor
- `batchItemFailures` de Lambda permite partial batch failure nativo con SQS
- Integración directa con SNS fan-out via suscripción SQS
- Gratuito hasta 1M requests/mes (Free Tier)

**Negativas:**
- Sin ordering garantizado en Standard Queue (aceptable para este caso de uso)
- Si se necesita replay de todos los eventos históricos, Kinesis sería mejor
- Para throughput > 100K TPS, Kinesis escala más eficientemente

## Alternativa rechazada

**Kinesis Data Streams** fue descartado porque:
1. No tiene DLQ nativa; requeriría una arquitectura más compleja para manejar fallos
2. No tiene Free Tier comparable
3. El volumen de transacciones proyectado no justifica la complejidad adicional
4. El caso de uso no requiere replay de eventos en orden cronológico estricto

## Referencias

- [AWS SQS Developer Guide](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/)
- [Comparativa SQS vs Kinesis — AWS Blog](https://aws.amazon.com/blogs/compute/choosing-between-messaging-services-for-serverless-applications/)
