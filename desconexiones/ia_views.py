from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .services.ia import EvaluadorRestricciones


@require_GET
def estado_ia(request):
    evaluador = EvaluadorRestricciones()
    return JsonResponse({
        "edicion": settings.CDYM_EDITION,
        "estado": "BASE_HIBRIDA_PREPARADA",
        "motor_restricciones": True,
        "reglas_iniciales": len(evaluador.reglas),
        "ejecucion_autonoma": False,
        "database": str(settings.DATABASE_FILE),
        "data_dir": str(settings.DATA_DIR),
    })
