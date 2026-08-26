import json
from django.test import TestCase
from django.urls import reverse


class ChatIATests(TestCase):
    def test_chat_local_solicita_demostracion(self):
        respuesta=self.client.post(
            reverse("chat_protocolo_ia"),
            data=json.dumps({"mensaje":"¿Qué hago?","bloqueo":"No encontró protección"}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code,200)
        datos=respuesta.json()
        self.assertEqual(datos["modo"],"LOCAL")
        self.assertIn("paso a paso",datos["respuesta"])
