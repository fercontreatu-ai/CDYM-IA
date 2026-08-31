from __future__ import annotations


ROLES_ENTRADA = {"ENTRADA_RED", "ENTRADA_TRANSFORMACION", "TRANSFORMADOR"}
ROLES_SALIDA = {"ALIMENTADOR", "SALIDA_345", "LINEA_345"}


def clasificar_dispositivos_barras(barras: list[dict]) -> list[dict]:
    """Clasifica con datos consultados de GTECH, sin escribir nunca en GTECH.

    La dirección de una red de 34,5 kV con más de un enlace no se presume:
    queda como interconexión y el motor determina importación/exportación con
    los estados eléctricos del escenario.
    """
    resultado=[]
    barras_por_interruptor={}
    for barra in barras:
        for dispositivo in barra.get("dispositivos",[]):
            if int(dispositivo.get("g3e_fno") or 0)==18800:
                barras_por_interruptor.setdefault(int(dispositivo["g3e_fid"]),set()).add(int(barra["g3e_fid"]))
    procesados=set()
    for barra in barras:
        nivel=float(barra.get("nivel_kv") or 0)
        main_kv=float(barra.get("main_kv") or 0)
        interruptores=[d for d in barra.get("dispositivos",[]) if int(d.get("g3e_fno") or 0)==18800]
        enlaces=[d for d in interruptores if len(barras_por_interruptor.get(int(d["g3e_fid"]),set()))==1]
        for dispositivo in interruptores:
            fid=int(dispositivo["g3e_fid"])
            if fid in procesados:continue
            procesados.add(fid)
            if len(barras_por_interruptor.get(fid,set()))>1:
                rol="ACOPLE"
                criterio="INTERRUPTOR_CONECTADO_A_MULTIPLES_BARRAS_LOCALES"
                confianza="ALTA"
            elif nivel==13.8:
                rol="ALIMENTADOR"
                criterio="CELDA_CONECTADA_A_BARRA_13_8"
                confianza="ALTA"
            elif nivel!=34.5:
                continue
            elif main_kv>34.5:
                rol="SALIDA_345"
                criterio=f"SUBESTACION_FUENTE_{main_kv:g}_KV"
                confianza="ALTA"
            elif len(enlaces)==1:
                rol="ENTRADA_RED"
                criterio="UNICA_CELDA_EN_SUBESTACION_NIVEL_SUPERIOR_34_5"
                confianza="ALTA"
            else:
                rol="INTERCONEXION"
                criterio="MULTIPLES_ENLACES_34_5_DIRECCION_DINAMICA"
                confianza="MEDIA"
            resultado.append({
                "g3e_fid":fid,
                "codigo":dispositivo.get("codigo") or "",
                "circuito":dispositivo.get("circuito") or "",
                "barra_fid":int(barra["g3e_fid"]),
                "nivel_kv":nivel,"main_kv":main_kv,"rol":rol,
                "criterio":criterio,"confianza":confianza,
            })
    return resultado
