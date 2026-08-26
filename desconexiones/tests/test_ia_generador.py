from django.test import SimpleTestCase

from desconexiones.services.ia.generador import GeneradorAislamiento


class GeneradorAislamientoTests(SimpleTestCase):
    def test_aisla_linea_con_interruptor_y_reconectador(self):
        datos = {"raiz": {"g3e_fid": 1}, "elementos": [
            {"g3e_fid": 1, "g3e_fno": 18800, "nodo1": 1, "nodo2": 2, "estado_operativo": "CLOSED", "codigo": "INT-1"},
            {"g3e_fid": 2, "g3e_fno": 19000, "nodo1": 2, "nodo2": 3, "estado_operativo": "CLOSED"},
            {"g3e_fid": 3, "g3e_fno": 19800, "nodo1": 3, "nodo2": 4, "estado_operativo": "CLOSED", "codigo": "REC-1"},
            {"g3e_fid": 4, "g3e_fno": 19000, "nodo1": 4, "nodo2": 5, "estado_operativo": "CLOSED", "codigo": "OBJ"},
        ]}
        resultado = GeneradorAislamiento(datos).generar("4")
        self.assertTrue(resultado["valido"])
        self.assertEqual(
            [(p["g3e_fid"], p["accion"], p.get("virtual", False)) for p in resultado["desenergizacion"]],
            [(3, "OPEN", False), (4, "OPEN", True), (3, "CLOSED", False)],
        )

    def test_bloquea_si_no_hay_equipo_con_capacidad_de_corte(self):
        datos = {"raiz": {"g3e_fid": 1}, "elementos": [
            {"g3e_fid": 1, "g3e_fno": 18800, "nodo1": 1, "nodo2": 2, "estado_operativo": "CLOSED"},
            {"g3e_fid": 2, "g3e_fno": 19000, "nodo1": 1, "nodo2": 3, "estado_operativo": "CLOSED"},
            {"g3e_fid": 3, "g3e_fno": 19000, "nodo1": 3, "nodo2": 4, "estado_operativo": "CLOSED"},
        ]}
        resultado = GeneradorAislamiento(datos).generar("1")
        self.assertFalse(resultado["valido"])

    def test_protege_cuchilla_con_interruptor_temporal_para_equipo(self):
        datos = {"raiz": {"g3e_fid": 1}, "elementos": [
            {"g3e_fid": 1, "g3e_fno": 18800, "nodo1": 1, "nodo2": 2, "estado_operativo": "CLOSED", "codigo": "INT"},
            {"g3e_fid": 2, "g3e_fno": 19000, "nodo1": 2, "nodo2": 3, "estado_operativo": "CLOSED"},
            {"g3e_fid": 3, "g3e_fno": 19400, "nodo1": 3, "nodo2": 4, "estado_operativo": "CLOSED", "codigo": "CUCH"},
            {"g3e_fid": 4, "g3e_fno": 20400, "nodo1": 4, "nodo2": 5, "estado_operativo": "CLOSED", "codigo": "OBJ"},
        ]}
        resultado = GeneradorAislamiento(datos).generar("4")
        self.assertTrue(resultado["valido"])
        self.assertEqual(
            [(p["g3e_fid"], p["accion"]) for p in resultado["desenergizacion"]],
            [(1, "OPEN"), (3, "OPEN"), (1, "CLOSED")],
        )
        self.assertEqual(
            [(p["g3e_fid"], p["accion"]) for p in resultado["normalizacion"]],
            [(1, "OPEN"), (3, "CLOSED"), (1, "CLOSED")],
        )

    def test_respeta_estado_estable_y_descarta_nodo_cero(self):
        datos = {"raiz": {"g3e_fid": 1}, "elementos": [
            {"g3e_fid": 1, "g3e_fno": 18800, "nodo1": 1, "nodo2": 2, "estado_estable": "CLOSED"},
            {"g3e_fid": 2, "g3e_fno": 19400, "nodo1": 2, "nodo2": 3, "estado_estable": "OPEN", "estado_operativo": "CLOSED"},
            {"g3e_fid": 3, "g3e_fno": 20400, "nodo1": 3, "nodo2": 0, "estado_estable": "CLOSED"},
            {"g3e_fid": 4, "g3e_fno": 20400, "nodo1": 4, "nodo2": 0, "estado_estable": "CLOSED"},
            {"g3e_fid": 5, "g3e_fno": 19000, "nodo1": 4, "nodo2": 5, "estado_estable": "CLOSED"},
        ]}
        generador = GeneradorAislamiento(datos)
        self.assertIsNone(generador._ruta_a_fuente("3", set(), set()))
        self.assertIsNone(generador._ruta_a_fuente("4", set(), set()))
