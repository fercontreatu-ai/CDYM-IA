from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from desconexiones.services import consumos_transformadores as servicio


class ConsumosTransformadoresTests(SimpleTestCase):
    def test_usa_consumo_agregado_y_capacidad_como_respaldo(self):
        with TemporaryDirectory() as temporal:
            archivo=Path(temporal)/"consumos.csv"
            archivo.write_text(
                "TRANSFORMADOR;PERIODO;ENERGIASALIDA;ENERGIAENTRADA;KVA;MUNICIPIO;CANT_USU_TOTAL;CLIENTES_OC;CONSUMO_OTROS\n"
                "1T00001;202607;12.345;13.000;75;Ocaña;20;3;456\n",
                encoding="cp1252",
            )
            data={"elementos":[
                {"g3e_fno":20400,"codigo_operacion":"1T00001","capacidad":75},
                {"g3e_fno":20400,"codigo_operacion":"1T99999","capacidad":112.5},
            ]}
            servicio._cargar_catalogo.cache_clear()
            with patch.object(servicio,"ARCHIVO",archivo):
                servicio.aplicar_consumos_transformadores(data)

        encontrado,faltante=data["elementos"]
        self.assertEqual(encontrado["consumo_transformador_kwh"],12345)
        self.assertEqual(encontrado["clientes_otro_comercializador"],3)
        self.assertEqual(encontrado["criterio_peso_carga"],"CONSUMO_TRANSFORMADOR")
        self.assertEqual(faltante["criterio_peso_carga"],"CAPACIDAD_TRANSFORMADOR")
