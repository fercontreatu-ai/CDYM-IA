from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("api/kmz/", views.api_cargar_kmz, name="api_cargar_kmz"),
    path("api/circuitos/", views.api_circuitos, name="api_circuitos"),
    path("api/trazado/", views.api_trazado, name="api_trazado"),
    path("api/operar/", views.api_operar, name="api_operar"),
    path("api/restaurar-operaciones/", views.api_restaurar_operaciones, name="api_restaurar_operaciones"),
    path("api/exportar-maniobras-xlsx/", views.api_exportar_maniobras_xlsx, name="api_exportar_maniobras_xlsx"),
    path("api/medidas/grafica/", views.api_grafica_medidas, name="api_grafica_medidas"),
    path("api/protocolo/aprendizaje/", views.api_aprendizaje_protocolo, name="api_aprendizaje_protocolo"),
    path("api/protocolo/guardar-aprendizaje/", views.api_guardar_aprendizaje_protocolo, name="api_guardar_aprendizaje_protocolo"),
    path("api/admin/paralelos/", views.api_admin_paralelos, name="api_admin_paralelos"),
    path("api/admin/guardar-paralelos/", views.api_admin_guardar_paralelos, name="api_admin_guardar_paralelos"),
    path("api/admin/calibres/", views.api_admin_calibres, name="api_admin_calibres"),
    path("api/admin/guardar-ampacidades/", views.api_admin_guardar_ampacidades, name="api_admin_guardar_ampacidades"),
    path("api/admin/estados-operativos/", views.api_admin_estados_operativos, name="api_admin_estados_operativos"),
    path("api/admin/guardar-estado-operativo/", views.api_admin_guardar_estado_operativo, name="api_admin_guardar_estado_operativo"),
    path("api/conductores/guardar-tendido/", views.api_guardar_tendido_conductor, name="api_guardar_tendido_conductor"),
    path("api/admin/reglas-maniobra/", views.api_admin_reglas_maniobra, name="api_admin_reglas_maniobra"),
    path("api/admin/guardar-reglas-maniobra/", views.api_admin_guardar_reglas_maniobra, name="api_admin_guardar_reglas_maniobra"),
    path("api/admin/barras/", views.api_admin_barras, name="api_admin_barras"),
    path("api/admin/guardar-medidas/", views.api_admin_guardar_medidas, name="api_admin_guardar_medidas"),
    path("api/admin/configuracion-scada/", views.api_admin_configuracion_scada, name="api_admin_configuracion_scada"),
    path("api/admin/seleccionar-carpeta-scada/", views.api_admin_seleccionar_carpeta_scada, name="api_admin_seleccionar_carpeta_scada"),
]
