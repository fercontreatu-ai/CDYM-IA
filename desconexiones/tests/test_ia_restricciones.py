from django.test import SimpleTestCase

from desconexiones.services.ia.contratos import ManiobraPropuesta
from desconexiones.services.ia.restricciones import EvaluadorRestricciones


class EvaluadorRestriccionesTests(SimpleTestCase):
    def test_acepta_una_maniobra_estructuralmente_valida(self):
        resultado = EvaluadorRestricciones().evaluar([ManiobraPropuesta(elemento_id="123", accion="OPEN")])
        self.assertTrue(resultado.valido)

    def test_bloquea_accion_desconocida_y_elemento_vacio(self):
        resultado = EvaluadorRestricciones().evaluar([ManiobraPropuesta(elemento_id="", accion="INVENTAR")])
        self.assertFalse(resultado.valido)
        self.assertEqual(len(resultado.bloqueos), 2)
