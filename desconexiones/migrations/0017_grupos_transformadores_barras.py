from django.db import migrations, models
import django.db.models.deletion


def migrar_grupos(apps, schema_editor):
    Asignacion = apps.get_model("desconexiones", "AsignacionMedidaEnergia")
    Grupo = apps.get_model("desconexiones", "GrupoTransformadorBarra")
    Membresia = apps.get_model("desconexiones", "BarraGrupoTransformador")
    especiales = {37444561, 37452909}
    for barra in Asignacion.objects.filter(tipo_objeto="BARRA", nivel_kv=13.8):
        sub = str(barra.subestacion or "").strip().upper()
        es_san_mateo = sub.replace(" ", "") == "SANMATEO" and barra.gtech_fid in especiales
        nombre = "SANMATEO_TRAFO_47MVA_BARRAS_2_3" if es_san_mateo else f"{sub}_BARRA_{barra.gtech_fid}"
        capacidad = 47 if es_san_mateo else barra.capacidad_transformador_mva
        grupo, _ = Grupo.objects.update_or_create(subestacion=sub, nombre=nombre, defaults={"capacidad_mva": capacidad})
        Membresia.objects.update_or_create(barra_fid=barra.gtech_fid, defaults={"grupo": grupo})

    # La configuracion especial debe existir aun si alguna barra de San Mateo
    # todavia no tiene una medida historica asignada en el administrador.
    grupo_san_mateo, _ = Grupo.objects.update_or_create(
        subestacion="SANMATEO",
        nombre="SANMATEO_TRAFO_47MVA_BARRAS_2_3",
        defaults={"capacidad_mva": 47},
    )
    for barra_fid in especiales:
        Membresia.objects.update_or_create(
            barra_fid=barra_fid,
            defaults={"grupo": grupo_san_mateo},
        )


class Migration(migrations.Migration):
    dependencies = [("desconexiones", "0016_aprendizajeprotocolo")]
    operations = [
        migrations.CreateModel(
            name="GrupoTransformadorBarra",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subestacion", models.CharField(db_index=True, max_length=120)),
                ("nombre", models.CharField(max_length=160)),
                ("capacidad_mva", models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["subestacion", "nombre"]},
        ),
        migrations.CreateModel(
            name="BarraGrupoTransformador",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("barra_fid", models.BigIntegerField(unique=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("grupo", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="barras", to="desconexiones.grupotransformadorbarra")),
            ],
            options={"ordering": ["grupo__subestacion", "barra_fid"]},
        ),
        migrations.AddConstraint(model_name="grupotransformadorbarra", constraint=models.UniqueConstraint(fields=("subestacion", "nombre"), name="grupo_transformador_barra_unico")),
        migrations.RunPython(migrar_grupos, migrations.RunPython.noop),
    ]