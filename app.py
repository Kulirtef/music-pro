from flask import Flask, request, jsonify
import yt_dlp
import threading
import os
import re
import requests

app = Flask(__name__)

# Cache para no repetir búsquedas pesadas
_cache = {}
_cache_lock = threading.Lock()

ARTISTAS_POR_LETRA = {
    "a": ["Ariana Grande", "Adele", "Anuel AA", "Aventura", "Alejandro Sanz"],
    "b": ["Bad Bunny", "Beyoncé", "Bruno Mars", "Billie Eilish", "Bizarrap"],
    "c": ["Camilo", "Christian Nodal", "Coldplay", "Cuco"],
    "d": ["Daddy Yankee", "Dua Lipa", "Drake", "David Guetta"]
}

# 1. CONFIGURACIÓN RÁPIDA: Solo para obtener metadatos (títulos, IDs)
OPTS_BUSQUEDA = {
    'quiet': True,
    'extract_flat': True, 
    'force_generic_extractor': False,
}

# 2. CONFIGURACIÓN DE STREAMING: Optimizada para servidores en la nube (Render)
OPTS_STREAM = {
    'format': 'bestaudio/best',  # Forzamos solo audio para evitar saturar la RAM de Render
    'quiet': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'source_address': '0.0.0.0', # Obligatorio: fuerza IPv4 para evitar bloqueos de Google
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
}

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
        with yt_dlp.YoutubeDL(OPTS_BUSQUEDA) as ydl:
            info = ydl.extract_info(f"ytsearch12:{query}", download=False)
            canciones = []
            for entry in (info.get('entries') or []):
                vid_id = entry.get('id')
                if vid_id:
                    canciones.append({
                        "titulo": entry.get('title', 'Sin título'),
                        "artista": entry.get('uploader') or "Artista desconocido",
                        "url_audio": vid_id,
                        "portada": f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg"
                    })
            return jsonify(canciones)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/artista', methods=['GET'])
def obtener_canciones_artista():
    nombre_sucio = request.args.get('nombre')
    if not nombre_sucio:
        return jsonify({"error": "Falta el nombre"}), 400

    nombre = re.sub(r'- Topic|Official|VEVO|©|®|video|lyric', '', nombre_sucio, flags=re.I).strip()

    try:
        url_deezer = f"https://api.deezer.com/search?q=artist:\"{nombre}\"&order=RANKING&limit=10"
        res = requests.get(url_deezer, timeout=5).json()
        canciones = []
        data_deezer = res.get('data', [])

        if data_deezer:
            for item in data_deezer:
                titulo = item['title']
                artista_real = item['artist']['name']
                vid_id = ""
                try:
                    with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                        search_query = f"ytsearch1:{titulo} {artista_real}"
                        yt_info = ydl.extract_info(search_query, download=False)
                        if yt_info and 'entries' in yt_info and yt_info['entries']:
                            vid_id = yt_info['entries'][0]['id']
                except:
                    continue 

                if vid_id:
                    canciones.append({
                        "titulo": titulo,
                        "artista": artista_real,
                        "url_audio": vid_id,
                        "portada": item['album']['cover_big'], 
                        "letra": [] 
                    })
        
        if not canciones:
            with yt_dlp.YoutubeDL(OPTS_BUSQUEDA) as ydl:
                info = ydl.extract_info(f"ytsearch10:{nombre} canciones", download=False)
                for entry in (info.get('entries') or []):
                    vid_id = entry.get('id')
                    if vid_id:
                        canciones.append({
                            "titulo": entry.get('title', 'Sin título'),
                            "artista": entry.get('uploader') or nombre,
                            "url_audio": vid_id,
                            "portada": f"https://img.youtube.com/vi/{vid_id}/maxresdefault.jpg",
                            "letra": []
                        })
        return jsonify(canciones)
    except Exception as e:
        return jsonify([]), 500
    
@app.route('/obtener_musica', methods=['GET'])
def obtener_musica():
    video_id = request.args.get('id')
    if not video_id:
        return jsonify({"error": "Falta el ID"}), 400

    try:
        with yt_dlp.YoutubeDL(OPTS_STREAM) as ydl:
            # Extraemos la URL real que ExoPlayer puede reproducir
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            url_real = info.get('url')
            if url_real:
                return jsonify({"url_real": url_real})
            else:
                return jsonify({"error": "No se pudo obtener el stream"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# CONFIGURACIÓN FINAL PARA DESPLIEGUE EN RENDER
if __name__ == '__main__':
    # Render asigna dinámicamente el puerto; usamos 10000 como respaldo
    port = int(os.environ.get("PORT", 10000))
    # host='0.0.0.0' permite conexiones externas desde tu App en Bogotá
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)