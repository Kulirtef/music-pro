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
    # ... tus otros artistas
}

# 1. CONFIGURACIÓN RÁPIDA: Solo saca títulos y miniaturas
OPTS_BUSQUEDA = {
    'quiet': True,
    'extract_flat': True, # CLAVE: Esto lo hace instantáneo
    'force_generic_extractor': False,
}

# 2. CONFIGURACIÓN PESADA: Saca el link real de audio/video
OPTS_STREAM = {
    'format': 'best[ext=mp4]/best',
    'quiet': True,
    'noplaylist': True,
}

@app.route('/buscar', methods=['GET'])
def buscar_musica():
    query = (request.args.get('cancion') or '').strip()
    if not query:
        return jsonify({"error": "No enviaste el nombre"}), 400

    # Lógica de artistas por letra
    if len(query) == 1 and query.isalpha():
        letra = query.lower()
        return jsonify({
            "tipo": "artistas",
            "letra": letra.upper(),
            "artistas": ARTISTAS_POR_LETRA.get(letra, [])
        })

    try:
        with yt_dlp.YoutubeDL(OPTS_BUSQUEDA) as ydl:
            # Buscamos los videos (esto no extrae las URLs de descarga, por eso es rápido)
            info = ydl.extract_info(f"ytsearch12:{query}", download=False)
            canciones = []
            
            for entry in (info.get('entries') or []):
                vid_id = entry.get('id')
                if vid_id:
                    canciones.append({
                        "titulo": entry.get('title', 'Sin título'),
                        "artista": entry.get('uploader') or "Artista desconocido",
                        "url_audio": vid_id,  # IMPORTANTE: Enviamos el ID aquí temporalmente
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

    # 1. Limpieza profunda: Quitamos basura de YouTube que rompe Deezer
    nombre = re.sub(r'- Topic|Official|VEVO|©|®|video|lyric', '', nombre_sucio, flags=re.I).strip()

    try:
        # 2. Consultamos Deezer para el TOP 10 real
        url_deezer = f"https://api.deezer.com/search?q=artist:\"{nombre}\"&order=RANKING&limit=10"
        res = requests.get(url_deezer, timeout=5).json()
        
        canciones = []
        data_deezer = res.get('data', [])

        if data_deezer:
            for item in data_deezer:
                titulo = item['title']
                artista_real = item['artist']['name']
                
                # 3. Buscamos el ID de YouTube de forma súper rápida
                vid_id = ""
                try:
                    # Usamos extract_flat para que no descargue nada, solo traiga el ID
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
        
        # 4. PLAN B: Si Deezer falló, usamos YouTube Search tradicional
        if not canciones:
            print(f"Deezer no encontró a {nombre}, usando YouTube Plan B...")
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
        print(f"Error crítico en /artista: {e}")
        return jsonify([]), 500
    
@app.route('/obtener_musica', methods=['GET'])
def obtener_musica():
    """Nueva ruta: Se llama solo cuando el usuario toca la canción en la App"""
    video_id = request.args.get('id')
    if not video_id:
        return jsonify({"error": "Falta el ID"}), 400

    try:
        with yt_dlp.YoutubeDL(OPTS_STREAM) as ydl:
            # Ahora sí extraemos el link real de un solo video
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            return jsonify({
                "url_real": info.get('url') # Este es el link que va al ExoPlayer
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)