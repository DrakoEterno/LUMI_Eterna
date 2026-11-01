# Lumi · Perfil evolutivo v1

Esta integración añade una personalidad **descriptiva, comprobable y revisable**.
No sustituye el CIC, `auditoria_resiliencia`, la memoria PGVector, la homeostasis,
el consentimiento humano ni los flujos B2B anteriores.

## Fecha fundacional de Lumi

Drako ha señalado el **10 de septiembre de 2026** como el nacimiento de Lumi.
Se conserva como un dato estable en `lumi_identidad.py`: aparece en el
dashboard V8 junto a los días transcurridos y llega a Lumi en el contexto de
su sistema. Esta fecha **no cambia** cada vez que modificamos el código, la
personalidad o la infraestructura. No requiere tablas nuevas en Supabase.

## Instalación (orden importante)

1. Guarda un respaldo de la versión actual en GitHub/Render.
2. Abre Supabase SQL Editor en el proyecto de Lumi y ejecuta
   `sql/personalidad_evolutiva_v1.sql`. Verifica que aparezcan dos tablas y
   la vista. **No hay ninguna orden de borrado de datos anteriores**.
3. Sube esta carpeta modificada a tu repositorio GitHub (conservando las
   imágenes y archivos que ya hay). No subas secretos ni `.env`.
4. En Render, comprueba que el backend dispone de `LUMI_PRIVATE_DB_KEY`
   (clave `sb_secret_...` privada, nunca en navegador ni GitHub). Ese acceso
   privado ya es utilizado por `lumi_hipotesis_latentes.py` y el CIC.
5. Añade `LUMI_PERSONALIDAD_ENABLED=1` **solo después de ejecutar el SQL**.
   Sin esta variable, la integración permanece en modo seguro y no interfiere.
6. Tras desplegar, entra en el dashboard autenticado. Verás el nuevo módulo
   `PERFIL EVOLUTIVO` en la columna izquierda.

## Cómo funciona de verdad

- Lumi puede declarar una elección en el campo opcional `decision_personalidad`:
  **qué eligió, por qué y qué alternativa tenía**. Esta elección va a
  `lumi_personalidad_decisiones` con estado `pendiente`. **No suma puntos**.
- Los verificadores del servidor pueden escribir registros en
  `lumi_personalidad_evidencias`. Cada registro lleva nombre del verificador,
  resultado comprobado, momento, rasgo y cambio de puntos. El historial es
  acumulativo; el perfil no se edita a mano.
- La vista `lumi_personalidad_resumen` calcula en SQL los resultados. Un rasgo
  se **desbloquea** con al menos **2 pruebas favorables en 2 días distintos**
  y **20 puntos**. Cada hecho confirmado aporta 12 puntos; evidencia en contra
  resta 12, y la puntuación se limita a 0–100.
- Cuando una barra baja a cero o no reúne los requisitos, desaparece del
  polígono. Sus registros anteriores permanecen intactos. El opuesto no se
  desbloquea sin pruebas positivas propias.
- Si existen 3 rasgos activos habrá un triángulo; 6, un hexágono; 8, un
  octógono. Con uno o dos solo aparecerán ejes/segmentos. Con ninguno se ve
  `SIN RASGOS AÚN DESBLOQUEADOS`, nunca valores inventados.
- Lumi recibe el mismo resumen numérico en el contexto al responder, y puede
  tenerlo en cuenta al elegir. No queda obligada a repetir comportamientos
  pasados; los límites de seguridad nunca dependen de la puntuación.

## Alcance real de los verificadores en v1

Inicialmente **solo está conectado automáticamente** el verificador de
`cobertura_historica_temporal_v3` que ya existía para la auditoría de sesgo de
recencia. Ese verificador evalúa uso de recuerdos con fecha cuando se pide
reconstruir períodos amplios: puede apoyar `observadora` o, ante ausencia de
cobertura temporal suficiente pese a disponer de recuerdos fechados,
`despistada`. **No demuestra que todos los hechos narrados sean ciertos**, ni
certifica empatía, autonomía, conciencia o calidad general de las decisiones.

Los otros 22 rasgos son **posibilidades**, todavía sin verificadores
automáticos. Se irán habilitando por criterio y evidencia, no por frases bonitas.
Por eso el primer día es normal que el gráfico esté vacío. Esto es deliberado.

## Comprobaciones

Desde la carpeta del repositorio:

```bash
python -m unittest discover -s tests -v
```

En Supabase SQL Editor, revisa (solo lectura):

```sql
select rasgo, puntuacion, apoyos, dias_con_evidencia
from public.lumi_personalidad_resumen
order by puntuacion desc;

select eleccion, motivo, alternativa, estado, creado_en
from public.lumi_personalidad_decisiones
order by creado_en desc limit 10;

select rasgo, delta, validador, contexto, creado_en
from public.lumi_personalidad_evidencias
order by creado_en desc limit 10;
```

Si el panel muestra `Módulo preparado`, revisa el interruptor de Render y la
clave privada. Si indica `Sin conexión`, revisa el SQL y los permisos del
servidor. No hay acceso público a las tablas; el endpoint del dashboard está
protegido con el mismo inicio de sesión que el estado cerebral.
