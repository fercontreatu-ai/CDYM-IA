from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("desconexiones", "0009_catalogo_conductor_cens")]
    operations = [
        migrations.AddField(model_name="catalogoconductorcens", name="fabricante", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="catalogoconductorcens", name="resistividad_ohm_mm2_m", field=models.DecimalField(blank=True, decimal_places=8, max_digits=14, null=True)),
        migrations.AddField(model_name="catalogoconductorcens", name="resistencia_ohm_km", field=models.DecimalField(blank=True, decimal_places=8, max_digits=14, null=True)),
        migrations.AddField(model_name="catalogoconductorcens", name="reactancia_ohm_km", field=models.DecimalField(blank=True, decimal_places=8, max_digits=14, null=True)),
        migrations.AddField(model_name="catalogoconductorcens", name="gmr_mm", field=models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
        migrations.AddField(model_name="catalogoconductorcens", name="diametro_mm", field=models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
        migrations.AddField(model_name="catalogoconductorcens", name="temperatura_referencia_c", field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
        migrations.AddField(model_name="catalogoconductorcens", name="fuente_tecnica", field=models.CharField(blank=True, max_length=500)),
    ]
