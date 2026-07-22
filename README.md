# Plan de despliegue — Hora 2 (Lakehouse en consola)

Stack: **MinIO + PostgreSQL + Iceberg REST Catalog + Apache Spark**, usando imágenes
ya probadas y documentadas por la comunidad Iceberg (`tabulario/iceberg-rest` y
`tabulario/spark-iceberg`), para minimizar el riesgo de choques de versiones en vivo.

**Cómo ejecutar la demo**

1. **Principal:** SSH a tu VPS desde local y correr `spark-submit` / `spark-sql`
   (o abrir el proyecto por Remote-SSH en tu IDE local).
2. **Alternativa visual:** Jupyter en el puerto `8888` con `notebooks/demo_en_vivo.ipynb`
   (ingesta → snapshots → time travel → schema evolution, celda a celda).

## Antes del workshop (preparación, NO en vivo)

Esto se hace con **días de anticipación**, en el mismo VPS que usarás el día del evento:

```bash
# 1. Copiar esta carpeta al VPS
scp -r lakehouse-demo/ usuario@tu-vps:/home/usuario/

# 2. Descargar todas las imágenes de antemano (evita esperas y fallos de red en vivo)
cd lakehouse-demo
docker compose pull

# 3. Ensayo completo
docker compose up -d
# Vía SSH/terminal:
docker exec -it spark-iceberg spark-submit /home/iceberg/jobs/load_and_query.py
# Alternativa Jupyter: http://<ip-vps>:8888 → notebooks/demo_en_vivo.ipynb

# 4. Si todo corrió bien, apaga (sin borrar volúmenes) y deja el VPS listo
docker compose stop
```

Si el ensayo falla, es MUCHO mejor descubrirlo ahora que en vivo frente al público.

## El día del workshop — timeline (Hora 2, ~60-70 min)

| Minuto | Acción | Comando / URL |
|---|---|---|
| 0:00 | Verificar VPS y conexión | `ssh usuario@vps`, `docker --version` |
| 0:02 | Levantar todo el stack | `docker compose up -d` |
| 0:05 | Verificar que todo esté sano | `docker compose ps` (todo "Up"/"healthy") |
| 0:06 | Mostrar la consola de MinIO | `http://<ip-vps>:9001` (admin / password12345) — bucket `warehouse` |
| 0:08 | Verificar el catálogo REST | `curl http://localhost:8181/v1/config` |
| 0:09 | **Opción A — terminal:** pre-calentar Spark | `docker exec -it spark-iceberg spark-sql` |
| 0:09 | **Opción B — Jupyter:** abrir notebook | `http://<ip-vps>:8888` → `notebooks/demo_en_vivo.ipynb` |
| 0:12 | Ingesta CSV → tabla Iceberg | `spark-submit .../load_and_query.py` **o** celdas 1–3 del notebook |
| 0:18 | Historial de **snapshots** | `demo_en_vivo.sql` / celda 4 |
| 0:22 | **Time travel** | SQL / celda 5 |
| 0:28 | **Schema evolution** + update | SQL / celdas 6–7 |
| 0:35 | (Opcional) Thrift Server + Superset | ver sección abajo |
| 0:45-0:70 | Preguntas / cierre | — |

### Comandos de terminal (flujo principal por SSH)

```bash
docker exec -it spark-iceberg spark-submit /home/iceberg/jobs/load_and_query.py
docker exec -it spark-iceberg spark-sql   # pegar comandos de jobs/demo_en_vivo.sql
```

## Sección opcional: BI con Superset

Conectar Superset a Spark requiere el **Thrift JDBC Server** (un paso extra que no
está en el docker-compose principal para no arriesgar tiempo si no llegas a usarlo):

```bash
docker exec -it spark-iceberg /opt/spark/sbin/start-thriftserver.sh \
  --master local[*] --hiveconf hive.server2.thrift.port=10000
```

Luego, en Superset: **Data > Databases > + Database**, motor "Apache Hive", URI:
```
hive://spark-iceberg:10000/demo
```

Este paso es el más frágil y menos esencial de la demo — si el tiempo aprieta, se
omite sin problema; el Lakehouse ya quedó demostrado con los pasos anteriores.

## Notas de riesgo (léelas antes del ensayo)

- **No cambies las versiones de las imágenes el día del workshop.** Si necesitas
  actualizar algo, hazlo en el ensayo previo, nunca en vivo.
- Las contraseñas de este bundle (`password12345`, `iceberg/iceberg`) son solo para
  la demo — no usar tal cual en un despliegue real.
- El healthcheck de MinIO usa `mc ready local` (no `curl`: la imagen oficial ya no lo trae).
- Si `mc` falla al crear el bucket, corre manualmente:
  `docker exec -it minio mc alias set local http://localhost:9000 admin password12345 && docker exec -it minio mc mb -p local/warehouse`
- Para reiniciar todo desde cero: `docker compose down -v` (borra los volúmenes).
