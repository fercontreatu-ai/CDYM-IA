import json
from pathlib import Path
from django.conf import settings
from django.db import migrations, models


def cargar_catalogo(apps, schema_editor):
    Catalogo = apps.get_model("desconexiones", "CatalogoConductorCens")
    path = Path(settings.BASE_DIR) / "datos" / "catalogo_conductores_cens.json"
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as entrada:
        items = json.load(entrada)
    # El catálogo vigente contiene campos agregados por migraciones posteriores.
    # Durante una instalación limpia este modelo histórico aún no los conoce.
    campos_disponibles = {campo.name for campo in Catalogo._meta.fields}
    registros = [
        Catalogo(**{clave: valor for clave, valor in item.items() if clave in campos_disponibles})
        for item in items
    ]
    Catalogo.objects.bulk_create(registros, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [("desconexiones", "0008_capacidad_transformador")]
    operations = [
        migrations.CreateModel(
            name="CatalogoConductorCens",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=80, unique=True)),
                ("descripcion", models.CharField(blank=True, max_length=240)),
                ("material", models.CharField(blank=True, max_length=40)),
                ("calibre", models.CharField(blank=True, max_length=40)),
                ("aislamiento", models.CharField(blank=True, max_length=80)),
                ("configuracion", models.CharField(blank=True, max_length=80)),
                ("ampacidad_a", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["material", "calibre", "codigo"]},
        ),
        migrations.RunPython(cargar_catalogo, migrations.RunPython.noop),
    ]
