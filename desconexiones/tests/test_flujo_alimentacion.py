from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from desconexiones.models import AsignacionMedidaEnergia, RelacionBarraTransformacion
from desconexiones.services.gtech import _nodos_barras
from desconexiones.views import _relaciones_transformacion_subestacion


class NodosBarraTests(SimpleTestCase):
    def test_incluye_los_dos_terminales_de_la_barra(self):
        self.assertEqual(_nodos_barras([(10, 20), (20, 30), (0, None)]), {10, 20, 30})

    def test_permita_detectar_raiz_conectada_al_segundo_terminal(self):
        barras = _nodos_barras([(100, 200)])
        raiz = {"nodo1": 300, "nodo2": 200}
        nodo_barra = next((n for n in (raiz["nodo1"], raiz["nodo2"]) if n in barras), raiz["nodo1"])
        self.assertEqual(nodo_barra, 200)


class ClasificacionEntradaEnergiaTests(TestCase):
    def test_entrega_enlace_entre_barra_345_y_barra_138(self):
        RelacionBarraTransformacion.objects.create(
            barra_secundaria_fid=38120941,
            barra_primaria_fid=40216968,
            origen_tipo="BARRA_GTECH",
            subestacion="PELAYA",
        )

        relaciones=_relaciones_transformacion_subestacion("PELAYA")

        self.assertEqual(relaciones[0]["barra_primaria_fid"], 40216968)
        self.assertEqual(relaciones[0]["barra_secundaria_fid"], 38120941)

    @patch("desconexiones.views.GTechService.listar_circuitos")
    def test_entrada_red_no_se_clasifica_como_salida_345(self, listar):
        listar.return_value = [{"g3e_fid": 40216974, "codigo": "SWTS43", "tension": 34.5}]
        AsignacionMedidaEnergia.objects.create(
            tipo_objeto=AsignacionMedidaEnergia.TIPO_ALIMENTADOR,
            gtech_fid=40216974,
            gtech_codigo="SWTS43",
            gtech_circuito="",
            subestacion="PELAYA",
            nivel_kv=34.5,
            medida_subestacion="PELAYA",
            medida_dispositivo="PEL_IT10",
            medida_fuente="REL",
            funcion_electrica="ENTRADA_RED",
        )

        respuesta=self.client.get(reverse("api_circuitos"), {"subestacion": "PELAYA"})

        self.assertEqual(respuesta.status_code, 200)
        dispositivo=respuesta.json()["circuitos"][0]
        self.assertEqual(dispositivo["funcion_electrica"], "ENTRADA_RED")
        self.assertEqual(dispositivo["rol_flujo"], "ENTRADA_RED")
        self.assertTrue(dispositivo["entrada_energia"])
        self.assertFalse(dispositivo["es_alimentador_salida"])

    @patch("desconexiones.views.GTechService.listar_circuitos")
    def test_salida_345_no_se_marca_como_entrada(self, listar):
        listar.return_value = [{"g3e_fid": 10, "codigo": "SAL10", "tension": 34.5}]
        AsignacionMedidaEnergia.objects.create(
            tipo_objeto=AsignacionMedidaEnergia.TIPO_ALIMENTADOR,
            gtech_fid=10,gtech_codigo="SAL10",gtech_circuito="SAL10",
            subestacion="FUENTE",nivel_kv=34.5,medida_subestacion="",
            medida_dispositivo="",funcion_electrica="SALIDA_345",
        )
        dispositivo=self.client.get(reverse("api_circuitos"),{"subestacion":"FUENTE"}).json()["circuitos"][0]
        self.assertFalse(dispositivo["entrada_energia"])
        self.assertTrue(dispositivo["es_alimentador_salida"])
