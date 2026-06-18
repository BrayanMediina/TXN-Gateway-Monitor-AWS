# ADR-002: FastAPI vs Flask para el microservicio gateway

**Estado:** Aceptado  
**Fecha:** 2024-01-01  
**Contexto:** TXN Gateway Monitor — gateway-service

## Contexto

Se necesita un framework Python para el microservicio REST que expone el endpoint de ingesta de transacciones y consulta de estado, desplegado en ECS Fargate.

## Decisión

Usar **FastAPI** con uvicorn como servidor ASGI.

## Razonamiento

| Criterio | FastAPI | Flask |
|---|---|---|
| **Async nativo** | Sí (async/await) | No (requiere extensiones) |
| **Validación de datos** | Pydantic v2 integrado | Manual o marshmallow |
| **Documentación API** | OpenAPI automático (/docs) | Extensión separada |
| **Type hints** | Primera clase | Opcional |
| **Performance** | Comparable a NodeJS/Go | Menor (WSGI síncrono) |
| **Ecosistema** | Moderno, creciendo | Maduro, estable |
| **Curva de aprendizaje** | Baja-Media | Baja |

## Consecuencias

**Positivas:**
- Validación de entrada automática con Pydantic v2: menos código, menos errores
- Documentación OpenAPI generada automáticamente (visible en `/docs`)
- `async def` handlers se integran naturalmente con boto3 async-compatible y X-Ray
- Dependency Injection nativa de FastAPI simplifica testing (mocking de servicios)
- mypy --strict funciona mejor con FastAPI por el tipado explícito

**Negativas:**
- Menor número de extensiones maduras comparado con Flask (ecosistema más antiguo)
- Para APIs muy simples, Flask puede ser más rápido de prototipar

## Alternativa rechazada

**Flask** fue descartado porque:
1. No tiene soporte async nativo; los handlers síncronos bloquean el event loop en un servidor ASGI
2. La validación de entrada requiere una librería externa (marshmallow, wtforms)
3. La documentación OpenAPI requiere `flask-openapi3` o `flasgger`, que añaden complejidad
4. El tipado estático es menos natural, lo que dificulta mypy --strict en CI

## Referencias

- [FastAPI vs Flask — Benchmark](https://www.techempower.com/benchmarks/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic v2 Migration Guide](https://docs.pydantic.dev/latest/migration/)
