from django.db import migrations,models
class Migration(migrations.Migration):
    dependencies=[("desconexiones","0004_ramal_transformador_manual")]
    operations=[migrations.AddField(model_name="ramaltransformadormanual",name="tipo_manual",field=models.CharField(choices=[("TRANSFORMADOR","Ramal de transformador"),("CIRCUITO_345","Circuito de 34,5 kV")],default="TRANSFORMADOR",max_length=20))]
