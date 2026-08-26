from django.conf import settings
from django.db import models

class EstadoNormalEquipo(models.Model):
    ESTADOS=[("OPEN","Abierto"),("CLOSED","Cerrado")]
    g3e_fid=models.BigIntegerField(db_index=True,unique=True)
    codigo=models.CharField(max_length=80,blank=True)
    subestacion=models.CharField(max_length=120,blank=True,db_index=True)
    circuito=models.CharField(max_length=120,blank=True)
    tipo_equipo=models.CharField(max_length=80,blank=True)
    estado_normal=models.CharField(max_length=10,choices=ESTADOS)
    observacion=models.TextField(blank=True)
    actualizado_en=models.DateTimeField(auto_now=True)
    actualizado_por=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
    class Meta:ordering=["subestacion","codigo"]

class EstadoOperativoVigente(models.Model):
    ESTADOS=[("OPEN","Abierto"),("CLOSED","Cerrado")]
    g3e_fid=models.BigIntegerField(unique=True,db_index=True)
    codigo=models.CharField(max_length=120,blank=True)
    subestacion=models.CharField(max_length=120,blank=True,db_index=True)
    circuito=models.CharField(max_length=120,blank=True)
    tipo_equipo=models.CharField(max_length=100,blank=True)
    fecha_inicio=models.DateField(db_index=True)
    estado=models.CharField(max_length=10,choices=ESTADOS)
    habilitado=models.BooleanField(default=True)
    observacion=models.TextField(blank=True)
    actualizado_en=models.DateTimeField(auto_now=True)
    actualizado_por=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
    class Meta:ordering=["-habilitado","subestacion","circuito","codigo"]
    def save(self,*args,**kwargs):
        self.codigo=(self.codigo or "").strip().upper()
        self.subestacion=(self.subestacion or "").strip().upper()
        self.circuito=(self.circuito or "").strip().upper()
        super().save(*args,**kwargs)

class Simulacion(models.Model):
    nombre=models.CharField(max_length=180)
    subestacion_base=models.CharField(max_length=120)
    datos=models.JSONField(default=dict)
    creado_en=models.DateTimeField(auto_now_add=True)
    actualizado_en=models.DateTimeField(auto_now=True)
    creado_por=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
    class Meta:ordering=["-actualizado_en"]

class AsignacionMedidaEnergia(models.Model):
    TIPO_BARRA="BARRA"; TIPO_ALIMENTADOR="ALIMENTADOR"
    TIPOS=[(TIPO_BARRA,"Barra"),(TIPO_ALIMENTADOR,"Alimentador")]
    tipo_objeto=models.CharField(max_length=16,choices=TIPOS)
    gtech_fid=models.BigIntegerField()
    gtech_codigo=models.CharField(max_length=120,blank=True)
    gtech_circuito=models.CharField(max_length=120,blank=True)
    subestacion=models.CharField(max_length=120,db_index=True)
    nivel_kv=models.FloatField()
    medida_subestacion=models.CharField(max_length=120)
    medida_dispositivo=models.CharField(max_length=160)
    medida_fuente=models.CharField(max_length=20,blank=True)
    coincidencia_exacta=models.BooleanField(default=False)
    funcion_electrica=models.CharField(max_length=32,blank=True)
    set_proteccion_a=models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
    capacidad_transformador_mva=models.DecimalField(max_digits=10,decimal_places=3,null=True,blank=True)
    capacidad_transformador_mva=models.DecimalField(max_digits=10,decimal_places=3,null=True,blank=True)
    actualizado_en=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["tipo_objeto","gtech_fid"],name="medida_energia_objeto_unico")]
        ordering=["subestacion","nivel_kv","tipo_objeto","gtech_codigo"]


class GrupoTransformadorBarra(models.Model):
    subestacion=models.CharField(max_length=120,db_index=True)
    nombre=models.CharField(max_length=160)
    capacidad_mva=models.DecimalField(max_digits=10,decimal_places=3,null=True,blank=True)
    actualizado_en=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["subestacion","nombre"],name="grupo_transformador_barra_unico")]
        ordering=["subestacion","nombre"]


class BarraGrupoTransformador(models.Model):
    grupo=models.ForeignKey(GrupoTransformadorBarra,related_name="barras",on_delete=models.CASCADE)
    barra_fid=models.BigIntegerField(unique=True)
    actualizado_en=models.DateTimeField(auto_now=True)
    class Meta:ordering=["grupo__subestacion","barra_fid"]

class RelacionBarraTransformacion(models.Model):
    barra_secundaria_fid=models.BigIntegerField(unique=True)
    barra_primaria_fid=models.BigIntegerField(null=True,blank=True)
    origen_tipo=models.CharField(max_length=20,default="BARRA_GTECH")
    nivel_primario_kv=models.FloatField(null=True,blank=True)
    subestacion=models.CharField(max_length=120,db_index=True)
    actualizado_en=models.DateTimeField(auto_now=True)
    class Meta:ordering=["subestacion","barra_secundaria_fid"]


class RamalTransformadorManual(models.Model):
    TIPOS=[("TRANSFORMADOR","Ramal de transformador"),("CIRCUITO_345","Circuito de 34,5 kV")]
    tipo_manual=models.CharField(max_length=20,choices=TIPOS,default="TRANSFORMADOR")
    subestacion=models.CharField(max_length=120,db_index=True)
    nombre=models.CharField(max_length=120)
    barra_primaria_fid=models.BigIntegerField()
    barra_secundaria_fid=models.BigIntegerField(null=True,blank=True)
    medida_subestacion=models.CharField(max_length=120,blank=True)
    medida_dispositivo=models.CharField(max_length=160,blank=True)
    medida_fuente=models.CharField(max_length=20,blank=True)
    actualizado_en=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["subestacion","nombre"],name="ramal_transformador_manual_unico")]
        ordering=["subestacion","nombre"]


class CatalogoConductorCens(models.Model):
    codigo=models.CharField(max_length=80,unique=True)
    descripcion=models.CharField(max_length=240,blank=True)
    material=models.CharField(max_length=40,blank=True)
    calibre=models.CharField(max_length=40,blank=True)
    aislamiento=models.CharField(max_length=80,blank=True)
    configuracion=models.CharField(max_length=80,blank=True)
    familia=models.CharField(max_length=120,blank=True)
    tension_nominal_kv=models.DecimalField(max_digits=8,decimal_places=3,null=True,blank=True)
    seccion_mm2=models.DecimalField(max_digits=12,decimal_places=4,null=True,blank=True)
    ampacidad_a=models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
    ampacidad_ducto_a=models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
    ampacidad_aire_a=models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
    origen_ampacidad=models.CharField(max_length=240,blank=True)
    fabricante=models.CharField(max_length=120,blank=True)
    resistividad_ohm_mm2_m=models.DecimalField(max_digits=14,decimal_places=8,null=True,blank=True)
    resistencia_ohm_km=models.DecimalField(max_digits=14,decimal_places=8,null=True,blank=True)
    reactancia_ohm_km=models.DecimalField(max_digits=14,decimal_places=8,null=True,blank=True)
    gmr_mm=models.DecimalField(max_digits=12,decimal_places=6,null=True,blank=True)
    diametro_mm=models.DecimalField(max_digits=12,decimal_places=4,null=True,blank=True)
    temperatura_referencia_c=models.DecimalField(max_digits=6,decimal_places=2,null=True,blank=True)
    origen_parametros=models.CharField(max_length=240,blank=True)
    confianza=models.CharField(max_length=20,blank=True)
    observaciones=models.TextField(blank=True)
    fuente_tecnica=models.CharField(max_length=500,blank=True)
    actualizado_en=models.DateTimeField(auto_now=True)
    class Meta:ordering=["material","calibre","codigo"]


class ConfiguracionTendidoCircuito(models.Model):
    TIPO_DUCTO="DUCTO"
    TIPO_AIRE="AIRE"
    TIPOS=((TIPO_DUCTO,"Ducto / subterraneo"),(TIPO_AIRE,"Aire"))
    subestacion=models.CharField(max_length=120,db_index=True)
    circuito=models.CharField(max_length=120,db_index=True)
    codigo_conductor=models.CharField(max_length=80)
    g3e_fid=models.BigIntegerField()
    tipo_tendido=models.CharField(max_length=12,choices=TIPOS)
    actualizado_en=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["subestacion","circuito","codigo_conductor","g3e_fid"],name="tendido_linea_conductor_unico")]
        ordering=["subestacion","circuito","codigo_conductor"]
    def save(self,*args,**kwargs):
        self.subestacion=(self.subestacion or "").strip().upper()
        self.circuito=(self.circuito or "").strip().upper()
        self.codigo_conductor=(self.codigo_conductor or "").strip().upper()
        super().save(*args,**kwargs)


class ParaleloCeldaPermitido(models.Model):
    subestacion_a=models.CharField(max_length=120,db_index=True)
    celda_a_fid=models.BigIntegerField()
    celda_a_codigo=models.CharField(max_length=120)
    subestacion_b=models.CharField(max_length=120,db_index=True)
    celda_b_fid=models.BigIntegerField()
    celda_b_codigo=models.CharField(max_length=120)
    nivel_kv=models.FloatField(default=13.8)
    observacion=models.CharField(max_length=300,blank=True)
    activo=models.BooleanField(default=True)
    actualizado_en=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["celda_a_fid","celda_b_fid"],name="paralelo_celdas_unico")]
        ordering=["subestacion_a","celda_a_codigo","subestacion_b","celda_b_codigo"]
    def save(self,*args,**kwargs):
        self.subestacion_a=(self.subestacion_a or "").strip().upper()
        self.subestacion_b=(self.subestacion_b or "").strip().upper()
        self.celda_a_codigo=(self.celda_a_codigo or "").strip().upper()
        self.celda_b_codigo=(self.celda_b_codigo or "").strip().upper()
        if (self.subestacion_b,self.celda_b_codigo,self.celda_b_fid)<(self.subestacion_a,self.celda_a_codigo,self.celda_a_fid):
            self.subestacion_a,self.subestacion_b=self.subestacion_b,self.subestacion_a
            self.celda_a_codigo,self.celda_b_codigo=self.celda_b_codigo,self.celda_a_codigo
            self.celda_a_fid,self.celda_b_fid=self.celda_b_fid,self.celda_a_fid
        super().save(*args,**kwargs)

class AprendizajeProtocolo(models.Model):
    firma=models.CharField(max_length=64,unique=True)
    tipo_cambio=models.CharField(max_length=20)
    motivo=models.TextField()
    protocolo=models.JSONField(default=list)
    contexto=models.JSONField(default=dict)
    actualizado_en=models.DateTimeField(auto_now=True)
    actualizado_por=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
    class Meta:ordering=["-actualizado_en"]

class EventoAprendizajeProtocolo(models.Model):
    """Ejemplo inmutable aportado por el operador; nunca se sobrescribe."""
    firma=models.CharField(max_length=64,db_index=True)
    tipo_cambio=models.CharField(max_length=20)
    motivo=models.TextField()
    protocolo_anterior=models.JSONField(default=list)
    protocolo_corregido=models.JSONField(default=list)
    contexto=models.JSONField(default=dict)
    version_modelo=models.PositiveIntegerField(default=1)
    creado_en=models.DateTimeField(auto_now_add=True)
    creado_por=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
    class Meta:ordering=["-creado_en"]

class PerfilAprendizajeManiobras(models.Model):
    """Preferencias generalizadas reconstruibles desde los eventos inmutables."""
    nombre=models.CharField(max_length=50,unique=True,default="GLOBAL")
    version=models.PositiveIntegerField(default=1)
    preferencias=models.JSONField(default=dict)
    ejemplos=models.PositiveIntegerField(default=0)
    actualizado_en=models.DateTimeField(auto_now=True)

class ConfiguracionManiobras(models.Model):
    corriente_max_apertura_aisladero_a=models.DecimalField(max_digits=8,decimal_places=2,default=12)
    corriente_max_cierre_aisladero_a=models.DecimalField(max_digits=8,decimal_places=2,default=12)
    usuarios_totales_cens=models.PositiveBigIntegerField(default=0)
    maniobra_inicio_desenergizacion=models.TextField(default="Solicitar a centro de control la apertura del permiso operativo y el inicio de maniobras")
    maniobra_fin_desenergizacion=models.TextField(default="Verificar las 5 reglas de oro para trabajo eléctrico seguro y realizar la entrega de campo")
    maniobra_inicio_energizacion=models.TextField(default="Solicitar a centro de control la apertura del permiso operativo y el inicio de maniobras de energización")
    maniobra_fin_energizacion=models.TextField(default="Informar a centro de control la terminación y normalización de los trabajos")
    actualizado_en=models.DateTimeField(auto_now=True)

    @classmethod
    def actual(cls):
        obj,_=cls.objects.get_or_create(pk=1)
        return obj
