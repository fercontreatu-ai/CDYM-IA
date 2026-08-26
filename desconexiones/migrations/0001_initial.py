from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion
class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
      migrations.CreateModel(name='EstadoNormalEquipo',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('g3e_fid',models.BigIntegerField(db_index=True,unique=True)),('codigo',models.CharField(blank=True,max_length=80)),('subestacion',models.CharField(blank=True,db_index=True,max_length=120)),('circuito',models.CharField(blank=True,max_length=120)),('tipo_equipo',models.CharField(blank=True,max_length=80)),('estado_normal',models.CharField(choices=[('OPEN','Abierto'),('CLOSED','Cerrado')],max_length=10)),('observacion',models.TextField(blank=True)),('actualizado_en',models.DateTimeField(auto_now=True)),('actualizado_por',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL))],options={'ordering':['subestacion','codigo']}),
      migrations.CreateModel(name='Simulacion',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('nombre',models.CharField(max_length=180)),('subestacion_base',models.CharField(max_length=120)),('datos',models.JSONField(default=dict)),('creado_en',models.DateTimeField(auto_now_add=True)),('actualizado_en',models.DateTimeField(auto_now=True)),('creado_por',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL))],options={'ordering':['-actualizado_en']})]
