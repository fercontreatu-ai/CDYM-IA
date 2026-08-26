from django.db import migrations, models


def cargar_ampacidades_350(apps, schema_editor):
    Catalogo = apps.get_model("desconexiones", "CatalogoConductorCens")
    Catalogo.objects.filter(codigo__in=["350MCM", "350XLPE15", "350XLPE35"]).update(
        ampacidad_ducto_a=390,
        ampacidad_aire_a=550,
    )


class Migration(migrations.Migration):
    dependencies = [("desconexiones", "0018_aprendizaje_persistente")]
    operations = [
        migrations.AddField(
            model_name="catalogoconductorcens",
            name="ampacidad_aire_a",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="catalogoconductorcens",
            name="ampacidad_ducto_a",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.CreateModel(
            name="ConfiguracionTendidoCircuito",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subestacion", models.CharField(db_index=True, max_length=120)),
                ("circuito", models.CharField(db_index=True, max_length=120)),
                ("codigo_conductor", models.CharField(max_length=80)),
                ("g3e_fid", models.BigIntegerField()),
                ("tipo_tendido", models.CharField(choices=[("DUCTO", "Ducto / subterraneo"), ("AIRE", "Aire")], max_length=12)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["subestacion", "circuito", "codigo_conductor"]},
        ),
        migrations.AddConstraint(
            model_name="configuraciontendidocircuito",
            constraint=models.UniqueConstraint(fields=("subestacion", "circuito", "codigo_conductor", "g3e_fid"), name="tendido_linea_conductor_unico"),
        ),
        migrations.RunPython(cargar_ampacidades_350, migrations.RunPython.noop),
    ]
