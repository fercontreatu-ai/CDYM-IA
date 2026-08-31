from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from desconexiones.services.tc1 import TC1Service, _TC1_CACHE


class TC1ServiceTests(SimpleTestCase):
    def setUp(self):
        _TC1_CACHE.clear()

    def test_mapea_usuarios_y_comercializador_del_ultimo_periodo(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (202407,)
        cursor.fetchall.return_value = [(
            "1T00001", "123", "CON-1", "1", 1, 1, "100", "1", "604",
            "CENS", "1", "2", "FRC", "CTO1", "54001", "1", "CALLE 1",
            "0", "", "", "4", 300, "-72.5", "7.8", "0", "0", "", "",
            "", None, "0", "", "IUA-123", "TRAFO-IUA-123",
        )]
        conexion = MagicMock()
        conexion.cursor.return_value = cursor

        usuarios, periodo = TC1Service().usuarios_por_transformadores(["1T00001"], conn=conexion)

        self.assertEqual(periodo, "202407")
        self.assertEqual(usuarios["1T00001"][0]["niu"], "123")
        self.assertTrue(usuarios["1T00001"][0]["activo_tc1"])
        self.assertTrue(usuarios["1T00001"][0]["comercializador_cens"])
        self.assertEqual(usuarios["1T00001"][0]["fuente_usuario"], "TC1_BRAE")
        sql = cursor.execute.call_args_list[1].args[0]
        self.assertIn("QA_TTC1", sql)
        self.assertIn("@BRAE", sql.upper())

    @patch.dict("os.environ", {"BRAE_SCHEMA": "BRAE", "BRAE_DB_LINK": "BRAE"})
    def test_identifica_otro_comercializador(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (202407,)
        fila = ["1T00002", "456", "", "", None, None, "", "", "564", "EPM"] + [""] * 24
        cursor.fetchall.return_value = [tuple(fila)]
        conexion = MagicMock()
        conexion.cursor.return_value = cursor

        usuarios, _ = TC1Service().usuarios_por_transformadores(["1T00002"], conn=conexion)

        self.assertTrue(usuarios["1T00002"][0]["otro_comercializador"])
        self.assertFalse(usuarios["1T00002"][0]["comercializador_cens"])
