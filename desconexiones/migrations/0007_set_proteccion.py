import json
import re
from pathlib import Path

from django.conf import settings
from django.db import migrations, models


def cargar_sets_iniciales(apps, schema_editor):
    Asignacion = apps.get_model("desconexiones", "AsignacionMedidaEnergia")
    path = Path(settings.BASE_DIR) / "datos" / "sets_proteccion_13_8.json"
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as entrada:
        alimentadores = json.load(entrada).get("alimentadores", {})
    normalizar = lambda valor: re.sub(r"[^A-Z0-9]", "", str(valor or "").upper())
    for asignacion in Asignacion.objects.filter(tipo_objeto="ALIMENTADOR", nivel_kv=13.8):
        for valor in (asignacion.gtech_codigo, asignacion.gtech_circuito):
            codigo = normalizar(valor)
            if codigo in alimentadores:
                asignacion.set_proteccion_a = alimentadores[codigo]["set_a"]
                asignacion.save(update_fields=["set_proteccion_a"])
                break


class Migration(migrations.Migration):
    dependencies = [("desconexiones", "0006_origen_primario_transformador")]

    operations = [
        migrations.AddField(
            model_name="asignacionmedidaenergia",
            name="set_proteccion_a",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.RunPython(cargar_sets_iniciales, migrations.RunPython.noop),
    ]
