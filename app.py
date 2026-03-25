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

# 1. RUTA DE INICIO
@app.route('/')
def home():
    return "Servidor Música Premium Activo 🚀 - Hugging Face"

# 2. CONFIGURACIÓN DE STREAMING (CORREGIDA PARA DOCKER)
ydl_opts_base = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0',
    'skip_download': True,
    'nocheckcertificate': True,
}

# IMPORTANTE: En Docker/Hugging Face, asegúrate de que el archivo se llame cookies.txt 
# y esté en la raíz del repositorio.
if os.path.exists('cookies.txt'):
    ydl_opts_base['cookiefile'] = 'cookies.txt'

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
        # Añadimos las cookies también a la búsqueda para evitar bloqueos aquí
        search_opts = {'quiet': True, 'extract_flat': True}
        if 'cookiefile' in ydl_opts_base:
            search_opts['cookiefile'] = 'cookies.txt'

        with yt_dlp.YoutubeDL(search_opts) as ydl:
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
            # Usamos las cookies en la búsqueda interna también
            search_opts = {'quiet': True, 'extract_flat': True}
            if 'cookiefile' in ydl_opts_base:
                search_opts['cookiefile'] = 'cookies.txt'

            for item in data_deezer:
                titulo = item['title']
                artista_real = item['artist']['name']
                vid_id = ""
                try:
                    with yt_dlp.YoutubeDL(search_opts) as ydl:
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
            search_opts = {'quiet': True, 'extract_flat': True}
            if 'cookiefile' in ydl_opts_base:
                search_opts['cookiefile'] = 'cookies.txt'
                
            with yt_dlp.YoutubeDL(search_opts) as ydl:
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
        with yt_dlp.YoutubeDL(ydl_opts_base) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            url_real = info.get('url')
            
            if url_real:
                return jsonify({"url_real": url_real})
            else:
                return jsonify({"error": "No se encontró el stream"}), 404
                
    except Exception as e:
        print(f"ERROR CRÍTICO: {str(e)}") 
        return jsonify({"error": "Error interno", "detalle": str(e)}), 500

# MODIFICACIÓN FINAL: Puerto 7860 para Hugging Face
if __name__ == '__main__':
    # HF requiere el puerto 7860 obligatoriamente
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)