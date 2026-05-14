# Schweppes IRIS Export (`diazcepeda_schweppes_iris`)

Módulo desarrollado por **Guillermo Barcena Lopez** para la automatización del envío de datos de ventas de mercado a Schweppes/Suntory siguiendo la normativa técnica IRIS v1.1.

## Descripción General

Este módulo permite a los distribuidores autorizados de Schweppes generar un fichero `.txt` con formato posicional estricto que contiene toda la actividad comercial (ventas, devoluciones y descuentos) junto con la información detallada de los clientes implicados.

## Funcionamiento Técnico

### 1. Extracción de Datos
El sistema se basa en los **Pedidos de Venta** (`sale.order`) confirmados.
- Solo se procesan los pedidos cuya fecha de pedido (`date_order`) está dentro del rango seleccionado por el usuario.
- Solo se exportan las líneas de pedido cuyos productos tengan definido un **Código Artículo Schweppes**.
- Antes de generar el fichero, el usuario carga esas líneas en una tabla intermedia editable: **`schweppes.export.line`** (`schweppes_export_lines`).
- Desde esa tabla se pueden **añadir, quitar o editar** líneas manualmente antes de confirmar la exportación.
- El fichero final IRIS se genera **exclusivamente** a partir de esa tabla snapshot vinculada con la cabecera de exportación.

### 2. Estructura de Registros
El fichero generado sigue la jerarquía de registros IRIS:
- **CT**: Cabecera de transmisión (una por fichero).
- **DICP**: Cabecera de pedido (contiene cliente, ruta, fecha...).
- **DIDP**: Detalle del producto (unidades servidas, precio, código Schweppes...).
- **DIDD**: Detalle de descuentos comerciales aplicados en línea.
- **DIMC**: Maestro de datos de los clientes (dirección, NIF, tipo de establecimiento...). Se genera automáticamente para todos los clientes que aparecen en los pedidos del periodo.
- **FT**: Fin de transmisión con control de integridad (sumatorio de registros).

## Configuración y Mapeos

Para que el módulo funcione correctamente, se deben rellenar los siguientes campos:

### Configuración Global
- **Ajustes > Schweppes IRIS**: Introducir el código de distribuidor oficial (ej: 1000026677).

### Ficha de Productos
- **Inventario > Productos**: En el formulario general, rellenar el campo **Código Artículo Schweppes** (ej: SW87116). Si este campo está vacío, el producto no aparecerá en el informe de ventas.

### Ficha de Clientes
- **Contactos > Schweppes IRIS**:
  - **Código Cliente Schweppes**: El código que Schweppes tiene asignado para este cliente (si aplica).
  - **Ruta**: Código numérico de ruta de reparto.
  - **Tipo de Reparto**: Directo o Indirecto.

## Generación del Fichero

1. Acceder a **Ventas > Informes > Schweppes IRIS > Generar Exportación**.
2. Crear un nuevo registro y definir el periodo temporal.
3. Hacer clic en **Cargar / Recargar líneas** para poblar la tabla editable con las líneas encontradas.
4. Revisar, editar, añadir o eliminar las líneas necesarias directamente en el formulario.
5. Cuando la selección sea correcta, hacer clic en **Generar Fichero**.
6. El sistema guardará el fichero en el registro y lo descargará automáticamente en formato `.txt`.

---
**Autor:** Guillermo Barcena Lopez
**Soporte:** Desarrollo interno para Diaz Cepeda.
