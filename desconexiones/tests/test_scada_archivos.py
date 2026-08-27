import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from openpyxl import Workbook

from desconexiones.services.scada_archivos import leer_dia, serie_dia_scada


class ScadaArchivosTests(TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temporal.name)
        self.carpeta = self.raiz / "SCADA"
        mes = self.carpeta / "2025" / "03. MARZO SCADA 2025"
        mes.mkdir(parents=True)
        self.archivo = mes / "01_SEVILLA_1320250301000000.xlsx"
        libro = Workbook()
        hoja = libro.active
        hoja.append([
            "FECHA_HORA",
            "IR_MED_SEVC3", "IS_MED_SEVC3", "IT_MED_SEVC3",
            "URS_MED_SEVC3", "UST_MED_SEVC3", "UTR_MED_SEVC3",
            "P_MED_SEVC3", "Q_MED_SEVC3", "S_MED_SEVC3",
        ])
        inicio = datetime(2025, 3, 3)
        for i in range(96):
            instante = inicio + timedelta(minutes=15 * i)
            hoja.append([instante, 100 + i, 101 + i, 102 + i, 13.8, 13.8, 13.8, 2.0, 0.5, 2.1])
        libro.save(self.archivo)
        libro.close()
        self.config = self.raiz / "config.json"
        self.config.write_text('{"scada_data_dir": ' + repr(str(self.carpeta)).replace("'", '"') + "}", encoding="utf-8")
        self.entorno = patch.dict(os.environ, {"CDYM_LOCAL_CONFIG_FILE": str(self.config)}, clear=False)
        self.entorno.start()
        leer_dia.cache_clear()

    def tearDown(self):
        leer_dia.cache_clear()
        self.entorno.stop()
        self.temporal.cleanup()

    def test_lee_96_intervalos_desde_carpeta_configurada(self):
        medida = {
            "medida_subestacion": "SEVILLA", "medida_dispositivo": "SEVC3",
            "medida_fuente": "REL", "nivel_kv": 13.8,
        }
        campos = (("IR", "I R"), ("IS", "I S"), ("IT", "I T"))
        unidades = {"IR": "A", "IS": "A", "IT": "A"}
        resultado = serie_dia_scada(medida, datetime(2025, 3, 3).date(), campos, unidades)
        self.assertEqual(resultado["cantidad_registros"], 96)
        self.assertEqual(resultado["fuente"], "MED")
        self.assertEqual(resultado["origen_datos"], "ARCHIVOS_SCADA")
        self.assertEqual(len(resultado["series"][0]["puntos"]), 96)
        self.assertEqual(resultado["series"][0]["puntos"][0][1], 100)

