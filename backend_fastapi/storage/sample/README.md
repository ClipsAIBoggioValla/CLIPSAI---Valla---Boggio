# Video de muestra — Issue 34

Colocá aquí el archivo `sample.mp4` (clip liviano, ~10-30 segundos) para que el botón **"Probar con video de ejemplo"** funcione sin subir archivos pesados.

## Ubicación

```
backend_fastapi/storage/sample/sample.mp4
```

## Requisitos del video

- Formato: `.mp4`
- Duración: 10-30 segundos (suficiente para generar 1-3 clips)
- Tamaño: menor a 5 MB (ideal para evaluación rápida)
- Contenido: preferiblemente con audio claro y habla (el motor usa Whisper + análisis de audio)

## Configuración alternativa

Si querés usar otra ruta, definí la variable de entorno:

```bash
SAMPLE_VIDEO_PATH=/ruta/a/tu/video.mp4
```

## Cómo probar

1. Colocá el video en la ubicación indicada
2. Iniciá la aplicación y navegá a `/upload`
3. Hacé clic en **"Probar con video de muestra"**
4. El sistema creará un video de muestra, iniciará un job y te redirigirá a la página de progreso

## Nota

Si el archivo no existe, el endpoint devuelve un error 404 con instrucciones claras sobre dónde colocarlo.