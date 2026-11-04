# Laboratorio 3.1.2 · Predicción y prescripción con FastAPI

Este laboratorio replica el microservicio de la guía **3.1.2 Aplicación de modelos**: un modelo de clasificación entrenado con datos sintéticos y expuesto mediante una API REST. El objetivo es observar el patrón completo de un sistema simple de analítica predictiva y prescriptiva, no construir un producto real.

## Qué hace

- Genera 1000 casos sintéticos con tres notas entre 1.0 y 7.0.
- Etiqueta cada caso como aprobado si el promedio es mayor o igual a 4.0.
- Entrena un `RandomForestClassifier` de 100 árboles, solo con CPU.
- Expone `POST /predict_and_prescribe`.
- Si el estudiante aprueba, entrega una recomendación de mantenimiento.
- Si reprueba, calcula el promedio actual, la brecha hacia 4.0 y la nota que necesitaría en la evaluación más baja para alcanzar el mínimo.

## Estructura

```text
3.1.2/
├── src/
│   ├── model.py          # datos sintéticos, entrenamiento y artefacto
│   └── main.py           # API FastAPI y lógica de prescripción
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Ejecución

Desde esta carpeta:

```bash
docker compose up --build -d
docker compose logs -f predictor-api
```

La API queda disponible en `http://localhost:8000`, la documentación interactiva en `http://localhost:8000/docs` y el esquema OpenAPI en `http://localhost:8000/openapi.json`.

Verificación rápida:

```bash
curl -s http://localhost:8000/health
```

## Prueba de predicción

Caso que aprueba:

```bash
curl -s -X POST http://localhost:8000/predict_and_prescribe \
  -H "Content-Type: application/json" \
  -d '{"grades": [5.5, 6.0, 5.8]}'
```

Respuesta esperada, con valores aproximados:

```json
{
  "prediction": "Aprobado",
  "pass_probability": 1.0,
  "input_grades": [5.5, 6.0, 5.8],
  "prescription": [
    "El rendimiento actual es suficiente. Mantener el ritmo de estudio."
  ]
}
```

Caso que reprueba:

```bash
curl -s -X POST http://localhost:8000/predict_and_prescribe \
  -H "Content-Type: application/json" \
  -d '{"grades": [3.0, 4.0, 2.8]}'
```

La respuesta incluye una prescripción con el promedio actual y la nota necesaria. Por ejemplo, si se repite la nota más baja, el cálculo es:

```text
nota_necesaria = 4.0 * 3 - (suma_de_las_otras_dos_notas)
```

## Detener el laboratorio

```bash
docker compose down
```

## Alcance y límites

- Los datos son **completamente sintéticos** y la regla de aprobación es una simplificación académica.
- El modelo se entrena al iniciar el contenedor para mantener el ejemplo autocontenido. En un sistema real el artefacto se entrena en un pipeline, se versiona en un registro de modelos y se descarga al servicio de inferencia.
- El laboratorio usa solo CPU, 1 núcleo y 512 MB de memoria, tal como propone el anexo.
- Este ejercicio no reemplaza la implementación del proyecto semestral; sirve como referencia aislada del patrón predictivo + prescriptivo que luego se aplica a SIGRIF en la guía 3.1.5.
