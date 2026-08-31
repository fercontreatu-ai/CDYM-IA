from django.test import SimpleTestCase

from desconexiones.services.gtech import _clasificar_estructura_poste


class ClasificacionPostesTests(SimpleTestCase):
    def test_prioriza_tipo_adecuacion_sobre_la_geometria(self):
        self.assertEqual(
            _clasificar_estructura_poste("SUSPENSION", "", []),
            ("PASO", "TIPO_ADECUACION"),
        )
        self.assertEqual(
            _clasificar_estructura_poste("RETENCION", "", []),
            ("RETENCION", "TIPO_ADECUACION"),
        )

    def test_clasifica_por_unidad_constructiva_ra2(self):
        self.assertEqual(
            _clasificar_estructura_poste("", "", [{"norma": "NC-RA2-301", "grupo": "13.2 kV"}]),
            ("PASO", "UNIDAD_CONSTRUCTIVA"),
        )
        self.assertEqual(
            _clasificar_estructura_poste("", "", [{"norma": "RA2-304-1", "grupo": "13.2 kV"}]),
            ("RETENCION", "UNIDAD_CONSTRUCTIVA"),
        )

    def test_no_inventa_clasificacion_sin_dato_constructivo(self):
        self.assertEqual(
            _clasificar_estructura_poste("", "CRUCE AEREO", [{"norma": "RA4-003", "grupo": "SECUNDARIA"}]),
            ("SIN_CLASIFICAR", "SIN_DATO_CONSTRUCTIVO"),
        )
