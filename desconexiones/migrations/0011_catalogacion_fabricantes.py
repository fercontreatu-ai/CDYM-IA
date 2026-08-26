import json
from pathlib import Path

from django.conf import settings
from django.db import migrations, models


def importar_catalogo(apps, schema_editor):
    Catalogo = apps.get_model("desconexiones", "CatalogoConductorCens")
    ruta = Path(settings.BASE_DIR) / "datos" / "catalogo_conductores_cens.json"
    if not ruta.exists():
        return
    for item in json.loads(ruta.read_text(encoding="utf-8")):
        codigo = str(item.get("codigo") or "").strip()
        if not codigo:
            continue
        campos = {clave: item.get(clave) for clave in (
            "descripcion", "material", "calibre", "aislamiento", "configuracion",
            "familia", "tension_nominal_kv", "seccion_mm2", "ampacidad_a",
            "origen_ampacidad", "fabricante", "resistividad_ohm_mm2_m",
            "resistencia_ohm_km", "reactancia_ohm_km", "gmr_mm", "diametro_mm",
            "temperatura_referencia_c", "origen_parametros", "confianza",
            "observaciones", "fuente_tecnica",
        )}
        Catalogo.objects.update_or_create(codigo=codigo, defaults=campos)


class Migration(migrations.Migration):
    dependencies = [("desconexiones", "0010_parametros_perfil_tension")]
    operations = [
        migrations.AddField(model_name="catalogoconductorcens", name="familia", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="catalogoconductorcens", name="tension_nominal_kv", field=models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True)),
        migrations.AddField(model_name="catalogoconductorcens", name="seccion_mm2", field=models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
        migrations.AddField(model_name="catalogoconductorcens", name="origen_ampacidad", field=models.CharField(blank=True, max_length=240)),
        migrations.AddField(model_name="catalogoconductorcens", name="origen_parametros", field=models.CharField(blank=True, max_length=240)),
        migrations.AddField(model_name="catalogoconductorcens", name="confianza", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="catalogoconductorcens", name="observaciones", field=models.TextField(blank=True)),
        migrations.RunPython(importar_catalogo, migrations.RunPython.noop),
    ]
