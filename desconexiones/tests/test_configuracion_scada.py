import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class ConfiguracionScadaTests(TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temporal.name)
        self.config = self.raiz / "usuario" / "config.json"
        self.scada = self.raiz / "scada"
        (self.scada / "2025").mkdir(parents=True)
        self.entorno = patch.dict(
            os.environ,
            {"CDYM_LOCAL_CONFIG_FILE": str(self.config)},
            clear=False,
        )
        self.entorno.start()

    def tearDown(self):
        self.entorno.stop()
        self.temporal.cleanup()

    def test_guarda_y_recupera_ruta_fuera_del_repositorio(self):
        respuesta = self.client.post(
            reverse("api_admin_seleccionar_carpeta_scada"),
            data=json.dumps({"ruta": str(self.scada)}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["valida"])
        self.assertTrue(self.config.is_file())
        consulta = self.client.get(reverse("api_admin_configuracion_scada"))
        self.assertEqual(consulta.status_code, 200)
        self.assertEqual(Path(consulta.json()["ruta"]), self.scada.resolve())
        self.assertEqual(consulta.json()["anios"], ["2025"])

    def test_rechaza_carpeta_sin_subcarpetas_anuales(self):
        vacia = self.raiz / "vacia"
        vacia.mkdir()
        respuesta = self.client.post(
            reverse("api_admin_seleccionar_carpeta_scada"),
            data=json.dumps({"ruta": str(vacia)}),
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(self.config.exists())

