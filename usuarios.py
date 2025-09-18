usuarios = {}  # diccionario en memoria: {numero: nombre}

def get_nombre(from_number: str, profile_name: str = None) -> str:
    """
    Devuelve el nombre asociado a un número de WhatsApp.
    Si no existe, lo registra usando el profile_name (si está disponible).
    """
    if from_number not in usuarios:
    
        nombre = profile_name or f"Usuario{len(usuarios)+1}"
        usuarios[from_number] = nombre
        print(f"Nuevo usuario registrado: {from_number} -> {nombre}")
    return usuarios[from_number]
