# Evidencia de observabilidad

Esta carpeta está preparada para evidencias reales de la corrida requerida, pero no incluye imágenes fabricadas.

Después de configurar `LANGSMITH_API_KEY`, iniciar los servicios y ejecutar `python scripts/load_test.py`, guardá aquí capturas reales de:

1. La vista de trazas, donde se vean los spans `classify_criticality`, `human_approval`, `supervisor`, `research`, `analyst` y `final` cuando correspondan.
2. La vista de la corrida de cinco solicitudes, con costo por ejecución y latencia p95 calculados por LangSmith.

No subas claves, prompts sensibles ni datos privados en las capturas.
