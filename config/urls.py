from django.urls import include, path

from desconexiones.ia_views import estado_ia
from desconexiones.ia_protocol_views import generar_protocolo_ia, origenes_barras_ia, chat_protocolo_ia

urlpatterns = [
    path("api/ia/estado/", estado_ia, name="estado_ia"),
    path("api/ia/generar-protocolo/", generar_protocolo_ia, name="generar_protocolo_ia"),
    path("api/ia/origenes-barras/", origenes_barras_ia, name="origenes_barras_ia"),
    path("api/ia/chat-protocolo/", chat_protocolo_ia, name="chat_protocolo_ia"),
    path("", include("desconexiones.urls")),
]
