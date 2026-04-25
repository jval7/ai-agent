# Texto que el bot dice por WhatsApp ANTES de que el paciente reciba la invitación
# de Google Calendar. En ese momento el paciente todavía no tiene el link de Meet,
# por eso le anticipamos que llegará al correo.
VIRTUAL_SESSION_BOT_INSTRUCTIONS = (
    "El enlace de Google Meet llega en la invitación de Google Calendar al correo registrado. "
    "Conéctate 5 minutos antes y valida cámara y micrófono."
)

# Texto que va en la description del evento de Google Calendar. El link de Meet
# ya es visible en el evento mismo, así que aquí solo dejamos las recomendaciones
# de uso.
VIRTUAL_SESSION_EVENT_INSTRUCTIONS = "Conéctate 5 minutos antes y valida cámara y micrófono."
