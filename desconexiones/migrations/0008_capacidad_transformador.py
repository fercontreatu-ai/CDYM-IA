from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("desconexiones", "0007_set_proteccion")]

    operations = [
        migrations.AddField(
            model_name="asignacionmedidaenergia",
            name="capacidad_transformador_mva",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True),
        ),
    ]
