-- ============================================================
-- Demo en vivo — ejecutar línea por línea dentro de spark-sql
-- docker exec -it spark-iceberg spark-sql
-- ============================================================

-- 1) Ver la tabla y su historial de snapshots
SELECT * FROM demo.sales.orders;
SELECT * FROM demo.sales.orders.history;
SELECT snapshot_id, committed_at FROM demo.sales.orders.snapshots;

-- 2) TIME TRAVEL: consultar la tabla como estaba ANTES de la segunda carga
--    (reemplazar <snapshot_id> por el primer snapshot_id que salga arriba)
SELECT * FROM demo.sales.orders VERSION AS OF <snapshot_id>;

-- También funciona por fecha/hora:
-- SELECT * FROM demo.sales.orders TIMESTAMP AS OF '2026-01-25 00:00:00';

-- 3) SCHEMA EVOLUTION: agregar una columna sin romper la tabla ni reescribir archivos
ALTER TABLE demo.sales.orders ADD COLUMN region STRING;

SELECT * FROM demo.sales.orders;  -- la columna nueva aparece en NULL para filas viejas

-- 4) Actualizar algunos registros con el nuevo campo
UPDATE demo.sales.orders SET region = 'Lima' WHERE customer = 'Empresa Andina SAC';

SELECT * FROM demo.sales.orders WHERE region IS NOT NULL;

-- 5) Confirmar que todo esto quedó registrado como nuevos snapshots
SELECT snapshot_id, operation, committed_at FROM demo.sales.orders.snapshots;
