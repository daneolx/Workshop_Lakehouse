# Paso a paso — Lakehouse en VPS Ubuntu

Guía para desplegar y ejecutar la demo en **Ubuntu** con los VPS ya provisionados.

## Inventario de servidores (datos reales)

| Rol | Hostname | IP pública | IP privada (usar esta) | IP privada alt. | Docker bridge (ignorar) |
|---|---|---|---|---|---|
| **VPS1 — Storage** (MinIO + Postgres + REST) | `vps01` | `134.122.118.159` | `10.116.0.3` | `10.10.0.6` | `172.17.0.1` |
| **VPS2 — Compute** (Spark + Jupyter) | `vps02` | `157.245.249.86` | `10.116.0.4` | `10.10.0.7` | `172.17.0.1` |

**SSH:**

```bash
ssh root@134.122.118.159   # vps01
ssh root@157.245.249.86    # vps02
```

**Tráfico entre VPS:** usar siempre las IPs `10.116.0.x` (misma VPC).  
No uses las públicas (`134…` / `157…`) ni `172.17.0.1` (bridge de Docker).

Hay dos modos:

| Modo | Cuándo usarlo | Archivos |
|---|---|---|
| **A — 2 VPS** (este inventario) | vps01 storage + vps02 compute | `docker-compose-vps1-storage.yml` + `docker-compose-vps2-compute.yml` |
| **B — 1 VPS** | Un solo servidor con ≥16 GB RAM | `docker-compose.yml` |

Ruta del proyecto en ambos VPS: `/root/lakehouse-demo`

---

## 0) Requisitos previos (en CADA VPS Ubuntu)

### 0.1 Actualizar el sistema e instalar Docker

En **vps01** y en **vps02**:

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Ya sos root: Docker funciona sin usermod extra
docker --version
docker compose version
```

### 0.2 Confirmar IPs (ya verificadas)

```bash
# vps01
hostname -I
# esperado: 134.122.118.159 10.10.0.6 10.116.0.3 172.17.0.1

# vps02
hostname -I
# esperado: 157.245.249.86 10.10.0.7 10.116.0.4 172.17.0.1
```

---

# MODO A — Dos VPS (vps01 + vps02)

## A1) Subir el proyecto desde tu PC

Desde tu máquina local, en la carpeta padre de `lakehouse-demo`:

```bash
scp -r lakehouse-demo root@134.122.118.159:~/
scp -r lakehouse-demo root@157.245.249.86:~/
```

En cada VPS debe quedar: `/root/lakehouse-demo/`

---

## A2) Firewall (UFW) — hacerlo ANTES de levantar servicios

### En vps01 (Storage + Catálogo) — `134.122.118.159`

```bash
# Permitir SSH
sudo ufw allow OpenSSH

# Permitir acceso al API de MinIO únicamente desde la IP privada del vps02
sudo ufw allow from 10.116.0.4 to any port 9000 proto tcp

# Permitir acceso al Iceberg REST Catalog únicamente desde la IP privada del vps02
sudo ufw allow from 10.116.0.4 to any port 8181 proto tcp

# Si utilizás la otra red privada (10.10.0.x), habilitá también estas reglas:
# sudo ufw allow from 10.10.0.7 to any port 9000 proto tcp
# sudo ufw allow from 10.10.0.7 to any port 8181 proto tcp

# Consola web de administración de MinIO
# (Para laboratorios puede quedar pública. En producción se recomienda
# restringirla únicamente a tu IP pública).
sudo ufw allow 9001/tcp

# Habilitar firewall
sudo ufw enable

# Verificar reglas
sudo ufw status numbered
```

---

### En vps02 (Compute) — `157.245.249.86`

```bash
# Permitir SSH
sudo ufw allow OpenSSH

# Jupyter Notebook
sudo ufw allow 8888/tcp

# Spark Web UI
sudo ufw allow 8080/tcp

# Habilitar firewall
sudo ufw enable

# Verificar reglas
sudo ufw status numbered
```

---

## A3) Levantar vps01 — Storage + Catálogo

```bash
ssh root@134.122.118.159

cd ~/lakehouse-demo

# Validar el archivo docker-compose
docker compose -f docker-compose-vps1-storage.yml config

# Descargar imágenes
docker compose -f docker-compose-vps1-storage.yml pull

# Levantar los servicios
docker compose -f docker-compose-vps1-storage.yml up -d

# Verificar estado de todos los contenedores
docker compose -f docker-compose-vps1-storage.yml ps -a


# Consola MinIO:

```text
http://134.122.118.159:9001
usuario: admin
password: password12345
```

Debe existir el bucket `warehouse`.

---

## A4) Configurar vps02 — apuntar a vps01

### A4.1 Crear `.env`

```bash
cat > .env << EOF
VPS1_PRIVATE_IP=10.116.0.3
EOF
```

### A4.2 Verificar `spark-defaults.conf` (IP literal, sin placeholders)

> Si ves `${VPS1_PRIVATE_IP}` en el archivo, Spark falla con:
> `Failed to create request URI from base http://${VPS1_PRIVATE_IP}:8181`

El repo ya trae la IP de vps01 (`10.116.0.3`). Verificá y reiniciá:

```bash
cd /root/lakehouse-demo
grep -E "uri|endpoint" spark-defaults.conf
# Debe mostrar http://10.116.0.3:8181 y http://10.116.0.3:9000

# Si aún tiene el placeholder:
sed -i "s|\${VPS1_PRIVATE_IP}|10.116.0.3|g; s|VPS1_PRIVATE_IP|10.116.0.3|g" spark-defaults.conf
docker compose -f docker-compose-vps2-compute.yml restart
```

### A4.3 Probar conectividad hacia vps01

Desde **vps02**:

```bash
curl -s --connect-timeout 5 http://10.116.0.3:8181/v1/config
curl -s -o /dev/null -w "%{http_code}\n" http://10.116.0.3:9000/minio/health/live
```

Si fallan: revisá UFW en vps01 y que ambos estén en la VPC `10.116.0.0`.

---

## A5) Levantar vps02 — Spark + Jupyter

```bash
cd ~/lakehouse-demo

docker compose -f docker-compose-vps2-compute.yml pull
docker compose -f docker-compose-vps2-compute.yml up -d
docker compose -f docker-compose-vps2-compute.yml ps
```

---

## A6) Ejecutar la demo (flujo principal: SSH + terminal)

En **vps02** (`root@157.245.249.86`):

### 1) Ingesta (CSV → tabla Iceberg)

```bash
docker exec -it spark-iceberg spark-submit /home/iceberg/jobs/load_and_query.py
```

### 2) Consultas en vivo (time travel, schema evolution)

```bash
docker exec -it spark-iceberg spark-sql
```

Dentro de `spark-sql`, pegá **de a uno** los bloques de `jobs/demo_en_vivo.sql`:

properties.put(CatalogProperties.URI, "http://10.116.0.3:8181");
properties.put(S3FileIOProperties.ENDPOINT, "http://10.116.0.3:9000");

.config("spark.sql.catalog.demo.uri", "http://10.116.0.3:8181")
.config("spark.sql.catalog.demo.s3.endpoint", "http://10.116.0.3:9000")

```sql
SELECT * FROM demo.sales.orders;
SELECT * FROM demo.sales.orders.history;
SELECT snapshot_id, committed_at FROM demo.sales.orders.snapshots;

-- Reemplazá <snapshot_id> por el PRIMERO de la lista
SELECT * FROM demo.sales.orders VERSION AS OF <snapshot_id>;

ALTER TABLE demo.sales.orders ADD COLUMN region STRING;
SELECT * FROM demo.sales.orders;

UPDATE demo.sales.orders SET region = 'Lima' WHERE customer = 'Empresa Andina SAC';
SELECT * FROM demo.sales.orders WHERE region IS NOT NULL;

SELECT snapshot_id, operation, committed_at FROM demo.sales.orders.snapshots;
```

Salir: `Ctrl+D` o `exit;`.

### Alternativa visual: Jupyter

```text
http://157.245.249.86:8888
```

Abrí `notebooks/demo_en_vivo.ipynb` → **Shift+Enter** celda a celda.

Spark UI:

```text
http://157.245.249.86:8080
```

---

## A7) Apagar / reiniciar

```bash
# vps02
ssh root@157.245.249.86
cd ~/lakehouse-demo
docker compose -f docker-compose-vps2-compute.yml stop

# vps01
ssh root@134.122.118.159
cd ~/lakehouse-demo
docker compose -f docker-compose-vps1-storage.yml stop
```

Borrar todo (incluye datos de MinIO/Postgres):

```bash
# en vps02
docker compose -f docker-compose-vps2-compute.yml down

# en vps01
docker compose -f docker-compose-vps1-storage.yml down -v
```

---

# MODO B — Un solo VPS

Usá solo si el servidor tiene **≥16 GB RAM**. Con 8 GB no es ideal.

```bash
ssh root@134.122.118.159   # o el VPS que elijas
cd ~/lakehouse-demo

sudo ufw allow OpenSSH
sudo ufw allow 9001/tcp
sudo ufw allow 8888/tcp
sudo ufw allow 8080/tcp
sudo ufw enable

docker compose -f docker-compose.yml pull
docker compose -f docker-compose.yml up -d
docker compose -f docker-compose.yml ps

docker exec -it spark-iceberg spark-submit /home/iceberg/jobs/load_and_query.py
docker exec -it spark-iceberg spark-sql
```

---

## Checklist rápido del día del workshop

1. [ ] Imágenes ya descargadas (`docker compose pull` días antes)
2. [ ] vps01: `curl localhost:8181/v1/config` OK
3. [ ] Bucket `warehouse` en MinIO → http://134.122.118.159:9001
4. [ ] vps02: `.env` con `VPS1_PRIVATE_IP=10.116.0.3` y `spark-defaults.conf` sin `${...}`
5. [ ] Desde vps02: `curl http://10.116.0.3:8181/v1/config` OK
6. [ ] `spark-submit` de ingesta OK
7. [ ] (Opcional) Jupyter en http://157.245.249.86:8888

---

## Problemas frecuentes

| Síntoma | Qué revisar |
|---|---|
| `mc` no arranca / MinIO `unhealthy` | Healthcheck = `mc ready local` (no `curl`) |
| Spark no conecta al catálogo | IP `10.116.0.3` literal en `spark-defaults.conf`; UFW 8181/9000 desde `10.116.0.4` |
| `Connection refused` a MinIO | No uses IP pública entre VPS; usá `10.116.0.3` |
| OOM en vps02 | 8 GB: preferí terminal; evitá varios jobs a la vez |
| `ADD COLUMN` falla al re-ejecutar | Columna ya existe; normal |
| Jupyter no carga | `docker logs spark-iceberg`; UFW 8888 en vps02 |
| `Another SparkContext` en Jupyter | Kernel → Restart and Clear Outputs; no re-ejecutar la celda 0 |
| `NoClassDefFoundError: StorageUtils` | Falta `JAVA_TOOL_OPTIONS` (Java 17). Recrear contenedor tras actualizar el compose |

### Si Jupyter falla por Java 17 / SparkContext (vps02)

```bash
cd /root/lakehouse-demo
# Subí el docker-compose-vps2-compute.yml actualizado (con JAVA_TOOL_OPTIONS)
docker compose -f docker-compose-vps2-compute.yml down
docker compose -f docker-compose-vps2-compute.yml up -d
```

Luego en Jupyter: **Kernel → Restart Kernel and Clear All Outputs**, ejecutá solo la celda 0 una vez.

```bash
docker logs spark-iceberg --tail 100
docker logs iceberg-rest --tail 100
docker logs minio --tail 50
```

---

## Credenciales de demo (NO usar en producción)

| Servicio | Usuario | Password |
|---|---|---|
| MinIO | `admin` | `password12345` |
| Postgres (interno) | `iceberg` | `iceberg` |

---

## Resumen de URLs

| Qué | URL |
|---|---|
| SSH vps01 | `ssh root@134.122.118.159` |
| SSH vps02 | `ssh root@157.245.249.86` |
| MinIO consola | http://134.122.118.159:9001 |
| Iceberg REST (desde vps02) | http://10.116.0.3:8181 |
| MinIO API (desde vps02) | http://10.116.0.3:9000 |
| Jupyter | http://157.245.249.86:8888 |
| Spark UI | http://157.245.249.86:8080 |
