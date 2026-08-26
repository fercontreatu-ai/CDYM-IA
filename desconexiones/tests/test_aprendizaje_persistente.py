import json

from django.test import TestCase
from django.urls import reverse

from desconexiones.models import EventoAprendizajeProtocolo
from desconexiones.services.ia.aprendizaje import reconstruir_preferencias


class AprendizajePersistenteTests(TestCase):
    def test_eventos_no_se_sobrescriben_y_generan_ranking(self):
        protocolo=[
            {"tipo":"Aisladero","fno":19300,"actual":"OPEN"},
            {"tipo":"Transformador","fno":20400,"actual":"OPEN"},
            {"tipo":"Cruce aereo","actual":"OPEN"},
        ]
        for motivo in ("Correccion uno","Correccion dos"):
            EventoAprendizajeProtocolo.objects.create(
                firma="a"*64,tipo_cambio="MOVER",motivo=motivo,
                protocolo_corregido=protocolo,
            )
        preferencias=reconstruir_preferencias(EventoAprendizajeProtocolo.objects.all())
        self.assertEqual(EventoAprendizajeProtocolo.objects.count(),2)
        self.assertEqual(preferencias["ejemplos"],2)
        self.assertLess(
            preferencias["ranking"]["19300:aisladero:OPEN"],
            preferencias["ranking"][":cruce_aereo:OPEN"],
        )

    def test_api_confirma_evento_y_total_de_ejemplos(self):
        respuesta=self.client.post(
            reverse("api_guardar_aprendizaje_protocolo"),
            data=json.dumps({
                "firma":"b"*64,"tipo_cambio":"DEMOSTRACION",
                "motivo":"Secuencia manual aprobada por el operador.",
                "protocolo":[{"clave":"1","tipo":"Aisladero","fno":19300,"actual":"OPEN"}],
                "contexto":{"origen":"MODO_ENSENANZA_IA"},
            }),content_type="application/json",
        )
        self.assertEqual(respuesta.status_code,200)
        datos=respuesta.json()
        self.assertTrue(datos["evento_id"])
        self.assertEqual(datos["ejemplos"],1)
