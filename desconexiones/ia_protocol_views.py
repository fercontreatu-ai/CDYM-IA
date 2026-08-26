import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .services.ia.generador import GeneradorAislamiento
from .views import _archivo_circuito
from .models import AsignacionMedidaEnergia, RelacionBarraTransformacion


@require_POST
def generar_protocolo_ia(request):
    try:
        payload = json.loads(request.body)
        subestacion = str(payload.get("subestacion") or "").strip().upper()
        circuito_fid = int(payload.get("circuito_fid"))
        objetivo_fid = str(int(payload.get("objetivo_fid")))
        archivo = _archivo_circuito(subestacion, circuito_fid)
        if not archivo.exists():
            return JsonResponse({"error": "Primero descargue el circuito seleccionado."}, status=409)
        with archivo.open("r", encoding="utf-8") as entrada:
            datos = json.load(entrada)
        resultado = GeneradorAislamiento(datos).generar(objetivo_fid)
        return JsonResponse(resultado, status=200 if resultado.get("valido") else 422)
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "La solicitud de protocolo no es válida."}, status=400)


@require_POST
def origenes_barras_ia(request):
    try:
        payload = json.loads(request.body)
        barras = {int(x) for x in payload.get("barras_fid", []) if x not in (None, "")}
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "La lista de barras no es válida."}, status=400)
    relaciones = {r.barra_secundaria_fid: r for r in RelacionBarraTransformacion.objects.filter(barra_secundaria_fid__in=barras)}
    primarias = {r.barra_primaria_fid for r in relaciones.values() if r.barra_primaria_fid}
    niveles_primarios = {x.gtech_fid: float(x.nivel_kv) for x in AsignacionMedidaEnergia.objects.filter(gtech_fid__in=primarias)}
    resultado = {}
    for barra in barras:
        relacion = relaciones.get(barra)
        nivel = None
        if relacion:
            nivel = relacion.nivel_primario_kv or niveles_primarios.get(relacion.barra_primaria_fid)
        resultado[str(barra)] = {
            "barra_secundaria_fid": barra,
            "barra_primaria_fid": relacion.barra_primaria_fid if relacion else None,
            "nivel_superior_kv": float(nivel) if nivel is not None else None,
            "origen_tipo": relacion.origen_tipo if relacion else "",
        }
    return JsonResponse({"origenes": resultado})


@require_POST
def chat_protocolo_ia(request):
    try:
        payload=json.loads(request.body);mensaje=str(payload.get("mensaje") or "").strip()[:4000]
        if not mensaje:return JsonResponse({"error":"Escriba una pregunta o instrucción."},status=400)
        bloqueo=str(payload.get("bloqueo") or "")[:4000];maniobras=payload.get("maniobras",[])[:50];protocolo=payload.get("protocolo",[])[:100]
        consulta=mensaje.lower();cantidad=len(maniobras)
        if any(x in consulta for x in ("qué hago","que hago","ayuda","bloqueo","no sabe")):
            texto=(f"El planificador quedó bloqueado: {bloqueo or 'no indicó el motivo'}. "
                   "Active ‘Enseñar paso a paso’, ejecute la primera maniobra correcta en el mapa y continúe hasta alcanzar el estado objetivo.")
        elif any(x in consulta for x in ("grab", "aprend", "enseñ")):
            texto=(f"Hay {cantidad} maniobra(s) grabada(s). "
                   "Cuando la secuencia esté completa pulse ‘Terminar y aprender’; se conservará como ejemplo persistente.")
        elif any(x in consulta for x in ("protocolo","pasos","secuencia")):
            nombres=[f"{i+1}. {x.get('accion','')} {x.get('codigo','')}" for i,x in enumerate(protocolo)]
            texto="Protocolo actual:\n"+("\n".join(nombres) if nombres else "No existe una propuesta completa; enséñeme la secuencia manual.")
        elif any(x in consulta for x in ("siguiente","continuar")):
            texto=(f"Ya registré {cantidad} maniobra(s). Ejecute ahora el siguiente paso que usaría en campo. "
                   "El asistente no inventará una operación cuando falte información topológica.")
        else:
            texto=("He registrado su explicación como contexto de esta enseñanza. "
                   f"Actualmente hay {cantidad} maniobra(s) manual(es). Realice el paso correspondiente en el mapa o pulse ‘Terminar y aprender’ al completar la secuencia.")
        return JsonResponse({"respuesta":texto,"modo":"LOCAL"})
    except Exception as exc:
        return JsonResponse({"error":str(exc)},status=500)
