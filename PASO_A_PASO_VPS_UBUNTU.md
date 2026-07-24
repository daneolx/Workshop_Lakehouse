# Paso a paso — Lakehouse en VPS Ubuntu

Guía para desplegar y ejecutar la demo en **Ubuntu** con **2 VPS** (Storage + Compute).

---

## SEEDS — completar ANTES de empezar (cada nuevo despliegue)

Al crear droplets nuevos en DigitalOcean, las IPs **cambian**. No copies IPs de un despliegue anterior.

### 1) Descubrir IPs en cada VPS

```bash
hostname -I
# Anotá: IP pública + IP VPC (la 10.116.0.x). Ignorá 172.17.0.1 / 172.18.0.1 (Docker).
```

### 2) Asignar roles por lo que vas a instalar (no por el número de IP)

| Rol | Qué corre | Variable seed |
|---|---|---|
| **VPS1 — Storage** | MinIO + Postgres + Iceberg REST | `VPS1_PUBLIC_IP`, `VPS1_PRIVATE_IP` |
| **VPS2 — Compute** | Spark + Jupyter | `VPS2_PUBLIC_IP`, `VPS2_PRIVATE_IP` |

> **Importante:** la IP privada `10.116.0.3` o `.4` **no define el rol**.  
> Storage = donde levantás `docker-compose-vps1-storage.yml`.  
> Compute = donde levantás `docker-compose-vps2-compute.yml`.  
> En Compute, `VPS1_PRIVATE_IP` debe ser la VPC del VPS donde está MinIO/REST.

### 3) Pegá tus valores aquí (ejemplo = despliegue actual)

```bash
# === SEEDS — editar solo este bloque ===
VPS1_PUBLIC_IP=142.93.118.134      # Storage (MinIO + REST) — IP pública
VPS1_PRIVATE_IP=10.116.0.4         # Storage — IP VPC 10.116.0.x
VPS2_PUBLIC_IP=159.223.143.243     # Compute (Spark) — IP pública
VPS2_PRIVATE_IP=10.116.0.3         # Compute — IP VPC 10.116.0.x
# ======================================
```

Inventario resultante (rellená con tus seeds):

| Rol | IP pública | IP privada VPC (usar entre VPS) |
|---|---|---|
| **VPS1 — Storage** | `$VPS1_PUBLIC_IP` | `$VPS1_PRIVATE_IP` |
| **VPS2 — Compute** | `$VPS2_PUBLIC_IP` | `$VPS2_PRIVATE_IP` |

**SSH:**

```bash
ssh root@$VPS1_PUBLIC_IP   # storage
ssh root@$VPS2_PUBLIC_IP   # compute
```

**Tráfico entre VPS:** siempre IPs `10.116.0.x` (misma VPC).  
No uses IPs públicas ni `172.17.0.1` / `172.18.0.1`.

### 4) Aplicar seeds en el VPS de Compute (Spark)

En **VPS2**, tras clonar/subir el repo:

```bash
cd /root/lakehouse-demo

# Pegá SOLO los seeds de tu despliegue (ejemplo actual):
VPS1_PRIVATE_IP=10.116.0.4

cat > .env << EOF
VPS1_PRIVATE_IP=${VPS1_PRIVATE_IP}
EOF

# spark-defaults.conf debe tener IP LITERAL (Spark no expande ${...})
# Si el archivo trae otra IP o el placeholder, reemplazá:
cp spark-defaults.conf.template spark-defaults.conf 2>/dev/null || true
sed -i "s|\${VPS1_PRIVATE_IP}|${VPS1_PRIVATE_IP}|g; s|VPS1_PRIVATE_IP|${VPS1_PRIVATE_IP}|g" spark-defaults.conf

# Si el conf ya tenía una IP vieja (ej. 10.116.0.3), forzá la nueva:
# sed -i "s|10.116.0.3|${VPS1_PRIVATE_IP}|g" spark-defaults.conf

grep -E "uri|endpoint" spark-defaults.conf
# Debe mostrar: http://<VPS1_PRIVATE_IP>:8181 y :9000
```

Archivos de compose:

| Rol | Archivo |
|---|---|
| Storage (VPS1) | `docker-compose-vps1-storage.yml` |
| Compute (VPS2) | `docker-compose-vps2-compute.yml` |

Ruta del proyecto en ambos VPS: `/root/lakehouse-demo`

---

## 0) Requisitos previos (en CADA VPS Ubuntu)

### 0.1 Actualizar el sistema e instalar Docker

En **VPS1** y en **VPS2**:

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

docker --version
docker compose version
```

### 0.2 Confirmar IPs y anotar seeds

```bash
hostname -I
# Completá el bloque SEEDS de arriba con la pública y la 10.116.0.x de cada VPS.
```

---

# Despliegue — Dos VPS (Storage + Compute)

## A1) Subir el proyecto desde tu PC

Desde tu máquina local, en la carpeta padre de `lakehouse-demo` (reemplazá por tus seeds):

```bash
scp -r lakehouse-demo root@142.93.118.134:~/   # VPS1_PUBLIC_IP (Storage)
scp -r lakehouse-demo root@159.223.143.243:~/  # VPS2_PUBLIC_IP (Compute)
```

En cada VPS debe quedar: `/root/lakehouse-demo/`

---

## A2) Firewall (UFW) — hacerlo ANTES de levantar servicios

### En VPS1 (Storage) — MinIO + REST

UFW debe permitir al **Compute** (`VPS2_PRIVATE_IP`), no a la IP del propio Storage.

```bash
# Ejemplo con seeds actuales: Compute = 10.116.0.3
VPS2_PRIVATE_IP=10.116.0.3

sudo ufw allow OpenSSH

# MinIO API e Iceberg REST solo desde el Compute
sudo ufw allow from ${VPS2_PRIVATE_IP} to any port 9000 proto tcp
sudo ufw allow from ${VPS2_PRIVATE_IP} to any port 8181 proto tcp

# Consola MinIO (lab); en prod restringí a tu IP
sudo ufw allow 9001/tcp

sudo ufw enable
sudo ufw status numbered
```

> Si recreás droplets: borrá reglas viejas (`sudo ufw status numbered` + `sudo ufw delete N`) y volvé a permitir desde la **nueva** `VPS2_PRIVATE_IP`.

### En VPS2 (Compute) — Spark + Jupyter

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8888/tcp   # Jupyter
sudo ufw allow 8080/tcp   # Spark UI
sudo ufw enable
sudo ufw status numbered
```

---

## A3) Levantar VPS1 — Storage + Catálogo

```bash
ssh root@142.93.118.134   # VPS1_PUBLIC_IP

cd ~/lakehouse-demo

docker compose -f docker-compose-vps1-storage.yml config
docker compose -f docker-compose-vps1-storage.yml pull
docker compose -f docker-compose-vps1-storage.yml up -d
docker compose -f docker-compose-vps1-storage.yml ps -a

# Salud local (debe responder)
curl -s http://127.0.0.1:8181/v1/config
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9000/minio/health/live
```

Consola MinIO:

```text
http://<VPS1_PUBLIC_IP>:9001
usuario: admin
password: password12345
```

Debe existir el bucket `warehouse`.

---

## A4) Configurar VPS2 — apuntar a VPS1 (seeds)

### A4.1 `.env` + `spark-defaults.conf`

En **VPS2** (Compute). `VPS1_PRIVATE_IP` = IP VPC del VPS donde corre MinIO/REST:

```bash
cd /root/lakehouse-demo

# Seed: IP privada del Storage (ejemplo actual)
VPS1_PRIVATE_IP=10.116.0.4

cat > .env << EOF
VPS1_PRIVATE_IP=${VPS1_PRIVATE_IP}
EOF

# IP literal obligatoria (Spark no expande ${VPS1_PRIVATE_IP})
sed -i "s|\${VPS1_PRIVATE_IP}|${VPS1_PRIVATE_IP}|g; s|VPS1_PRIVATE_IP|${VPS1_PRIVATE_IP}|g" spark-defaults.conf
# Si quedó una IP de otro despliegue, reemplazala explícitamente:
# sed -i "s|10.116.0.OLD|${VPS1_PRIVATE_IP}|g" spark-defaults.conf

grep -E "uri|endpoint" spark-defaults.conf
# Esperado: http://10.116.0.4:8181 y http://10.116.0.4:9000
```

### A4.2 Probar conectividad hacia Storage

Desde **VPS2** (no desde VPS1):

```bash
VPS1_PRIVATE_IP=10.116.0.4   # seed Storage

curl -s --connect-timeout 5 http://${VPS1_PRIVATE_IP}:8181/v1/config
curl -s -o /dev/null -w "%{http_code}\n" --connect-timeout 5 http://${VPS1_PRIVATE_IP}:9000/minio/health/live
# Esperado: JSON + 200
```

| Resultado | Causa típica |
|---|---|
| JSON / `200` | OK |
| `Connection timed out` | UFW/Cloud Firewall en Storage; regla debe ser `from <VPS2_PRIVATE_IP>` |
| `Connection refused` | Servicios caídos en Storage, o estás apuntando al VPS equivocado |

---

## A5) Levantar VPS2 — Spark + Jupyter

```bash
cd ~/lakehouse-demo

docker compose -f docker-compose-vps2-compute.yml pull
docker compose -f docker-compose-vps2-compute.yml up -d --force-recreate
docker compose -f docker-compose-vps2-compute.yml ps
```

---

## A6) Ejecutar la demo (SSH + terminal)

En **VPS2** (`ssh root@$VPS2_PUBLIC_IP`):

### 1) Ingesta (CSV → tabla Iceberg)

```bash
docker exec -it spark-iceberg spark-submit /home/iceberg/jobs/load_and_query.py
```

### 2) Consultas en vivo (time travel, schema evolution)

```bash
docker exec -it spark-iceberg spark-sql
```

Dentro de `spark-sql`, pegá **de a uno** los bloques de `jobs/demo_en_vivo.sql`:

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
http://<VPS2_PUBLIC_IP>:8888
```

Abrí `notebooks/demo_en_vivo.ipynb` → **Shift+Enter** celda a celda.  
Si el notebook hardcodea una IP, actualizala a `$VPS1_PRIVATE_IP`.

Spark UI:

```text
http://<VPS2_PUBLIC_IP>:8080
```

---

## A7) Apagar / reiniciar

```bash
# VPS2
ssh root@$VPS2_PUBLIC_IP
cd ~/lakehouse-demo
docker compose -f docker-compose-vps2-compute.yml stop

# VPS1
ssh root@$VPS1_PUBLIC_IP
cd ~/lakehouse-demo
docker compose -f docker-compose-vps1-storage.yml stop
```

Borrar todo (incluye datos de MinIO/Postgres):

```bash
# en VPS2
docker compose -f docker-compose-vps2-compute.yml down

# en VPS1
docker compose -f docker-compose-vps1-storage.yml down -v
```

---

## Checklist: nuevo par de VPS (reemplazar IPs)

1. [ ] Crear 2 droplets en la **misma VPC**
2. [ ] En cada uno: `hostname -I` → completar **SEEDS** arriba
3. [ ] Decidir qué droplet es Storage y cuál Compute (por compose, no por `.3`/`.4`)
4. [ ] UFW en Storage: `allow from <VPS2_PRIVATE_IP>` a `8181` y `9000`
5. [ ] Storage: `docker compose -f docker-compose-vps1-storage.yml up -d`
6. [ ] Compute: `.env` + `spark-defaults.conf` con `<VPS1_PRIVATE_IP>` literal
7. [ ] Desde Compute: `curl http://<VPS1_PRIVATE_IP>:8181/v1/config` → JSON
8. [ ] Compute: `docker compose -f docker-compose-vps2-compute.yml up -d`
9. [ ] `spark-submit` de ingesta OK

---

## Checklist rápido del día del workshop

1. [ ] Imágenes ya descargadas (`docker compose pull` días antes)
2. [ ] VPS1: `curl localhost:8181/v1/config` OK
3. [ ] Bucket `warehouse` en MinIO → `http://<VPS1_PUBLIC_IP>:9001`
4. [ ] VPS2: `.env` con `VPS1_PRIVATE_IP=<seed>` y `spark-defaults.conf` sin `${...}`
5. [ ] Desde VPS2: `curl http://<VPS1_PRIVATE_IP>:8181/v1/config` OK
6. [ ] `spark-submit` de ingesta OK
7. [ ] (Opcional) Jupyter en `http://<VPS2_PUBLIC_IP>:8888`

---

## Problemas frecuentes

| Síntoma | Qué revisar |
|---|---|
| `mc` no arranca / MinIO `unhealthy` | Healthcheck = `mc ready local` (no `curl`) |
| Spark timeout a `:8181` | UFW en Storage: `from <VPS2_PRIVATE_IP>` (no desde la IP del Storage) |
| `Connection refused` a `:8181` | Apuntás al VPS equivocado, o REST no está up en Storage |
| Roles al revés | Confirmá con `hostname -I` + `docker compose ps` en cada máquina |
| IP vieja en `spark-defaults.conf` | Reaplicá seeds (sección SEEDS §4) y `up -d --force-recreate` |
| OOM en Compute | 8 GB: preferí terminal; evitá varios jobs a la vez |
| `ADD COLUMN` falla al re-ejecutar | Columna ya existe; normal |
| Jupyter no carga | `docker logs spark-iceberg`; UFW 8888 en Compute |
| `Another SparkContext` en Jupyter | Kernel → Restart and Clear Outputs; no re-ejecutar la celda 0 |
| `NoClassDefFoundError: StorageUtils` | Falta `JAVA_TOOL_OPTIONS` (Java 17). Recrear contenedor |

### Si Jupyter falla por Java 17 / SparkContext (VPS2)

```bash
cd /root/lakehouse-demo
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

## Resumen de URLs (usar seeds)

| Qué | URL |
|---|---|
| SSH Storage | `ssh root@<VPS1_PUBLIC_IP>` |
| SSH Compute | `ssh root@<VPS2_PUBLIC_IP>` |
| MinIO consola | `http://<VPS1_PUBLIC_IP>:9001` |
| Iceberg REST (desde Compute) | `http://<VPS1_PRIVATE_IP>:8181` |
| MinIO API (desde Compute) | `http://<VPS1_PRIVATE_IP>:9000` |
| Jupyter | `http://<VPS2_PUBLIC_IP>:8888` |
| Spark UI | `http://<VPS2_PUBLIC_IP>:8080` |

**Ejemplo con seeds actuales:**

| Qué | URL |
|---|---|
| SSH Storage | `ssh root@142.93.118.134` |
| SSH Compute | `ssh root@159.223.143.243` |
| MinIO consola | http://142.93.118.134:9001 |
| Iceberg REST | http://10.116.0.4:8181 |
| MinIO API | http://10.116.0.4:9000 |
| Jupyter | http://159.223.143.243:8888 |
| Spark UI | http://159.223.143.243:8080 |
