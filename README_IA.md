# CDYM — versión IA experimental

Esta carpeta es una copia evolutiva del código funcional. La versión estable **Sin IA**
permanece en la raíz del proyecto.

Por defecto, esta edición usa `../alimentadores.sqlite`, `../datos` y `../.env`. Se pueden
aislar mediante `CDYM_IA_DATABASE` y `CDYM_IA_DATA_DIR`. No se duplican los paquetes
`dist*` ni la base de varios GB.

Para ejecutarla desde esta carpeta use `.\iniciar_ia.ps1`. Se inicia en
`http://127.0.0.1:8001`; el estado de la capa IA está en `/api/ia/estado/`.

El iniciador experimental no ejecuta migraciones automáticamente sobre la base compartida.

La IA podrá interpretar objetivos, ordenar alternativas y explicar resultados. Ninguna
maniobra será aceptada sin pasar por el motor determinista de topología y restricciones.
La ejecución autónoma está deshabilitada.

## Generador determinista inicial

El botón **Protocolo IA** recibe el FID de un elemento ya dibujado. El motor construye el
grafo del circuito, localiza fuentes alcanzables y selecciona el seccionamiento más cercano
al objetivo. Si se trata de una cuchilla o aisladero, agrega la apertura temporal del
interruptor o reconectador ubicado hacia la fuente, opera el seccionamiento descargado y
restablece el alimentador. Después verifica que los dos extremos del objetivo queden sin
fuente y crea una normalización protegida.

Esta primera versión trabaja en modo recomendación. No opera equipos, nunca propone
cuchillas o aisladeros bajo carga y exige revisión del operador.

Para una línea objetivo, propone abrir sus puentes en el nodo de alimentación. Primero
abre el reconectador o interruptor más cercano hacia la fuente, retira los puentes con el
tramo descargado y vuelve a energizar la protección. Así evita dejar abierto el alimentador
principal como solución permanente.

## Análisis del estado final dibujado

El flujo principal ya no solicita un FID. El operador dibuja los circuitos y realiza en el
mapa las aperturas, cierres, cortes, cruces o enlaces hasta representar el estado final que
desea obtener. **Analizar desconexión IA** compara ese estado con la posición normal,
expande las maniobras temporales de seguridad, ordena el protocolo y ofrece **Simular
protocolo paso a paso**.

Para paralelos de 13,8 kV se consulta la relación de transformación de las dos barras. El
paralelo se considera compatible automáticamente cuando ambas barras provienen del mismo
nivel de tensión superior. Si falta la relación de alguna barra, no se autoriza por
inferencia y se conserva la validación administrativa existente.

Las aperturas de líneas, puentes, cruces aéreos y cuchillas no pueden ejecutarse mientras
el sector que se va a separar conserve transformadores o fronteras conectados y
energizados. El protocolo debe abrir primero las protecciones necesarias, verificar la
desenergización topológica, realizar la apertura física y después restablecer lo que sea
seguro. Las corrientes históricas son información complementaria y nunca sustituyen esta
comprobación. El Brakesafe es la excepción por su capacidad de interrupción de carga.

Los cruces aéreos siguen la misma regla operativa de una cuchilla: pueden abrirse con
tensión únicamente cuando no transportan carga aguas abajo, o pueden abrirse sin tensión.
Si no existe un deslastre local, el motor debe buscar una protección hacia la fuente,
abrirla temporalmente, separar el cruce descargado y restablecerla cuando sea seguro.
# Enseñanza y chat del protocolo

Cuando el planificador no encuentra una solución, abre el panel de enseñanza e inicia la grabación manual. El operador ejecuta las maniobras en el mapa y pulsa **Terminar y aprender**. La demostración se guarda como un evento inmutable en la base de datos.

El chat funciona completamente en modo local, sin API, claves, conexión externa ni costos. Dialoga sobre el bloqueo, la propuesta y el avance de la grabación. El aprendizaje proviene de las maniobras ejecutadas y aprobadas por el operador; el chat no puede omitir las restricciones eléctricas deterministas.
