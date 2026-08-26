from django.db import migrations,models
class Migration(migrations.Migration):
    dependencies=[("desconexiones","0002_asignacion_medida_energia")]
    operations=[migrations.AddField(model_name="asignacionmedidaenergia",name="funcion_electrica",field=models.CharField(blank=True,max_length=32)),migrations.CreateModel(name="RelacionBarraTransformacion",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("barra_secundaria_fid",models.BigIntegerField(unique=True)),("barra_primaria_fid",models.BigIntegerField()),("subestacion",models.CharField(db_index=True,max_length=120)),("actualizado_en",models.DateTimeField(auto_now=True))],options={"ordering":["subestacion","barra_secundaria_fid"]})]
