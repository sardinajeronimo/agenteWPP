import redis
import json

# Conexión a Redis 
r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

def get_estado(usuario):
    """
    Devuelve el estado del usuario desde Redis.
    Si no existe, arranca en 'esperando_receta'.
    """
    data = r.get(f"usuario:{usuario}")
    return json.loads(data) if data else {"estado": "esperando_receta", "productos": []}

def set_estado(usuario, estado, productos=None, receta=None):
    """
    Guarda el estado del usuario en Redis.
    """
    data = {"estado": estado, "productos": productos or [], "ultima_receta": receta}
    r.set(f"usuario:{usuario}", json.dumps(data))
