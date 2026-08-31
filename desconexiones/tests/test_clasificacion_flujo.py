from django.test import SimpleTestCase

from desconexiones.services.clasificacion_flujo import clasificar_dispositivos_barras


def barra(main_kv, nivel, *fids):
    return [{"g3e_fid":900,"nivel_kv":nivel,"main_kv":main_kv,"dispositivos":[
        {"g3e_fid":fid,"g3e_fno":18800,"codigo":f"I{fid}","circuito":f"C{fid}"} for fid in fids
    ]}]


class ClasificacionFlujoTests(SimpleTestCase):
    def test_unica_celda_345_en_receptora_es_entrada(self):
        self.assertEqual(clasificar_dispositivos_barras(barra(34.5,34.5,10))[0]["rol"],"ENTRADA_RED")

    def test_celdas_345_en_subestacion_115_son_salidas(self):
        roles={x["rol"] for x in clasificar_dispositivos_barras(barra(115,34.5,10,20))}
        self.assertEqual(roles,{"SALIDA_345"})

    def test_varias_celdas_345_en_receptora_son_bidireccionales(self):
        roles={x["rol"] for x in clasificar_dispositivos_barras(barra(34.5,34.5,10,20))}
        self.assertEqual(roles,{"INTERCONEXION"})

    def test_celda_138_es_alimentador(self):
        self.assertEqual(clasificar_dispositivos_barras(barra(115,13.8,10))[0]["rol"],"ALIMENTADOR")

    def test_interruptor_comun_a_dos_barras_es_acople(self):
        barras=barra(115,13.8,10)+[{"g3e_fid":901,"nivel_kv":13.8,"main_kv":115,"dispositivos":[
            {"g3e_fid":10,"g3e_fno":18800,"codigo":"ACOPLE","circuito":""}
        ]}]
        resultado=clasificar_dispositivos_barras(barras)
        self.assertEqual(len(resultado),1)
        self.assertEqual(resultado[0]["rol"],"ACOPLE")
