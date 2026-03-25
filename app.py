from flask import Flask, request, jsonify
import yt_dlp
import threading

app = Flask(__name__)

_cache = {}
_cache_lock = threading.Lock()

# Mantenemos tu diccionario ARTISTAS_POR_LETRA igual...
ARTISTAS_POR_LETRA = {
    "a": ["Ariana Grande", "Adele", "Anuel AA", "Aventura", "Alejandro Sanz"],
    "b": ["Bad Bunny", "Beyoncé", "Bruno Mars", "Billie Eilish", "Bizarrap"],
    # ... (resto de letras)
}

def _get_from_yt(query: str, max_results: int = 10):
    """
    Extrae resultados de YouTube obteniendo la URL directa.
    Cambiado a formato 'best' para asegurar que traiga VIDEO y no solo audio.
    """
    cache_key = f"{query}_{max_results}"
    with _cache_lock:
        if cache_key in _cache:
            return _cache[cache_key]

    # CONFIGURACIÓN PARA VIDEO + AUDIO:
    # 'best[ext=mp4]/best' busca el mejor archivo que combine ambos y sea compatible con Android
    opts = {
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'noplaylist': True,
        'extract_flat': False,
        # Engañamos a YT con un User-Agent moderno
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'no_warnings': True,
        'source_address': '0.0.0.0', # Fuerza el uso de IPv4
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            # Realizamos la búsqueda en YouTube
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            canciones = []
            
            for entry in (info.get('entries') or []):
                if not entry: 
                    continue
                
                # Esta URL ahora contiene el flujo de video y audio combinado
                url_directa = entry.get('url') 
                vid_id = entry.get('id', '')
                
                # Validamos que tengamos una URL antes de añadirlo
                if url_directa:
                    canciones.append({
                        "titulo":    entry.get('title', 'Sin título'),
                        "artista":   entry.get('uploader') or "Artista desconocido",
                        "url_audio": url_directa, # Mantenemos el nombre para no cambiar Kotlin
                        "portada":   f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg" if vid_id else ""
                    })

            # Guardamos en caché para que la próxima vez sea instantáneo
            with _cache_lock:
                _cache[cache_key] = canciones
                
            return canciones

    except Exception as e:
        print(f"Error detallado en yt-dlp: {e}")
        # Si falla, devolvemos una lista vacía para que la App no se cierre
        return []

@app.route('/buscar', methods=['GET'])
def buscar_musica():
    query = (request.args.get('cancion') or '').strip()
    if not query:
        return jsonify({"error": "No enviaste el nombre"}), 400

    if len(query) == 1 and query.isalpha():
        letra = query.lower()
        return jsonify({
            "tipo": "artistas",
            "letra": letra.upper(),
            "artistas": ARTISTAS_POR_LETRA.get(letra, [])
        })

    try:
        canciones = _get_from_yt(query, max_results=12)
        return jsonify(canciones)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/artista', methods=['GET'])
def canciones_artista():
    nombre = (request.args.get('nombre') or '').strip()
    if not nombre:
        return jsonify({"error": "Falta el nombre"}), 400
    try:
        # Buscamos específicamente canciones del artista
        canciones = _get_from_yt(f"{nombre} canciones", max_results=20)
        return jsonify(canciones)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    import os
    # Render usa la variable PORT, si no existe usa 5000 para local
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)