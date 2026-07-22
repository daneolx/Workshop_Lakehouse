"""
Job de ingesta — Hora 2 del workshop
Lee el CSV de ejemplo y lo escribe como tabla Iceberg (formato Parquet + metadata ACID).

Ejecutar dentro del contenedor:
  docker exec -it spark-iceberg spark-submit /home/iceberg/jobs/load_and_query.py
"""
from datetime import date

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    DateType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

spark = SparkSession.builder.appName("lakehouse-ingesta").getOrCreate()

# 1) Namespace (equivalente a un "schema") dentro del catálogo Iceberg
spark.sql("CREATE NAMESPACE IF NOT EXISTS demo.sales")

# 2) Leer el CSV de origen
df = (
    spark.read.option("header", "true")
    .option("inferSchema", "true")
    .csv("/home/iceberg/data/sample_sales.csv")
)

print(">>> Datos leídos del CSV:")
df.printSchema()
df.show()

# 3) Escribir como tabla Iceberg (crea la tabla si no existe)
df.writeTo("demo.sales.orders").createOrReplace()

print(">>> Tabla Iceberg creada: demo.sales.orders")
spark.sql("SELECT * FROM demo.sales.orders").show()

# 4) Simular una segunda carga (para generar un segundo snapshot y poder
#    demostrar time travel más adelante en la sesión de spark-sql en vivo).
#    order_date debe ser DATE (igual que el CSV con inferSchema), no STRING.
extra_schema = StructType(
    [
        StructField("order_id", IntegerType(), False),
        StructField("customer", StringType(), False),
        StructField("product", StringType(), False),
        StructField("amount", DoubleType(), False),
        StructField("order_date", DateType(), False),
    ]
)
extra = spark.createDataFrame(
    [(1011, "Empresa Andina SAC", "Licencia ERP", 1200.50, date(2026, 1, 25))],
    extra_schema,
)
print(">>> Schema de la fila extra (debe coincidir con la tabla):")
extra.printSchema()
extra.writeTo("demo.sales.orders").append()

print(">>> Segunda carga aplicada (nuevo snapshot generado)")
spark.sql("SELECT * FROM demo.sales.orders.snapshots").show(truncate=False)

spark.stop()
