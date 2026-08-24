# init-scripts/

Scripts ejecutados **una unica vez** por el contenedor `clipsai-db` cuando el
volumen `postgres_data` esta vacio (primera inicializacion). Documentacion
oficial: <https://hub.docker.com/_/postgres> — seccion _Initialization scripts_.

- Los archivos `.sql`, `.sql.gz` y `.sh` se ejecutan en orden alfabetico.
- Se sugiere prefijar con un numero: `01_schema.sql`, `02_indexes.sql`, etc.
- Si necesitas re-ejecutar los scripts, primero elimina el volumen:
  `docker compose down -v`.

Este directorio se monta como read-only (`:ro`) dentro del contenedor.

> El esquema DDL (`usuarios`, `videos`, `jobs`, `clips`) se agregara en el
> siguiente commit de esta misma issue.
