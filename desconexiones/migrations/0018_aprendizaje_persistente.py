import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("desconexiones", "0017_grupos_transformadores_barras"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="EventoAprendizajeProtocolo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("firma", models.CharField(db_index=True, max_length=64)),
                ("tipo_cambio", models.CharField(max_length=20)),
                ("motivo", models.TextField()),
                ("protocolo_anterior", models.JSONField(default=list)),
                ("protocolo_corregido", models.JSONField(default=list)),
                ("contexto", models.JSONField(default=dict)),
                ("version_modelo", models.PositiveIntegerField(default=1)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("creado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-creado_en"]},
        ),
        migrations.CreateModel(
            name="PerfilAprendizajeManiobras",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(default="GLOBAL", max_length=50, unique=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("preferencias", models.JSONField(default=dict)),
                ("ejemplos", models.PositiveIntegerField(default=0)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
