from django.db import migrations,models
class Migration(migrations.Migration):
    dependencies=[("desconexiones","0005_tipo_elemento_manual")]
    operations=[migrations.AlterField(model_name="relacionbarratransformacion",name="barra_primaria_fid",field=models.BigIntegerField(blank=True,null=True)),migrations.AddField(model_name="relacionbarratransformacion",name="origen_tipo",field=models.CharField(default="BARRA_GTECH",max_length=20)),migrations.AddField(model_name="relacionbarratransformacion",name="nivel_primario_kv",field=models.FloatField(blank=True,null=True))]
