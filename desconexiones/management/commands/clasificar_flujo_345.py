from django.core.management.base import BaseCommand

from desconexiones.models import AsignacionMedidaEnergia
from desconexiones.services.clasificacion_flujo import clasificar_dispositivos_barras
from desconexiones.services.gtech import GTechService


class Command(BaseCommand):
    help="Consulta GTECH en solo lectura y guarda localmente los roles de flujo."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar",action="store_true",help="Guarda la clasificación en la base local.")
        parser.add_argument("--subestacion",default="",help="Limita el análisis a una subestación.")

    def handle(self,*args,**options):
        servicio=GTechService()
        subs=[options["subestacion"].strip().upper()] if options["subestacion"].strip() else [x["codigo"] for x in servicio.listar_subestaciones()]
        conteo={};total=0
        for sub in subs:
            clasificaciones=clasificar_dispositivos_barras(servicio.listar_barras_dispositivos(sub))
            for item in clasificaciones:
                total+=1;conteo[item["rol"]]=conteo.get(item["rol"],0)+1
                self.stdout.write(f'{sub};{item["codigo"]};{item["g3e_fid"]};{item["nivel_kv"]:g};{item["rol"]};{item["confianza"]};{item["criterio"]}')
                if options["aplicar"]:
                    asignacion,_=AsignacionMedidaEnergia.objects.get_or_create(
                        tipo_objeto=AsignacionMedidaEnergia.TIPO_ALIMENTADOR,
                        gtech_fid=item["g3e_fid"],
                        defaults={"gtech_codigo":item["codigo"],"gtech_circuito":item["circuito"],
                                  "subestacion":sub,"nivel_kv":item["nivel_kv"],"medida_subestacion":"",
                                  "medida_dispositivo":"","medida_fuente":"TOPOLOGIA_GTECH",
                                  "coincidencia_exacta":False,"funcion_electrica":item["rol"]},
                    )
                    asignacion.gtech_codigo=item["codigo"]
                    asignacion.gtech_circuito=item["circuito"]
                    asignacion.subestacion=sub
                    asignacion.nivel_kv=item["nivel_kv"]
                    asignacion.funcion_electrica=item["rol"]
                    asignacion.save(update_fields=["gtech_codigo","gtech_circuito","subestacion","nivel_kv","funcion_electrica","actualizado_en"])
        modo="APLICADO LOCALMENTE" if options["aplicar"] else "SOLO DIAGNOSTICO"
        self.stdout.write(self.style.SUCCESS(f"{modo}: {total} celdas. {conteo}"))
