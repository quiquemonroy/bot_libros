# 📚 Resumidor de Libros para Mastodon 🤖

Un bot que publica resúmenes de libros en Mastodon cada 2 horas, usando la API de OpenAI para generar los resúmenes.

## 🚀 Características

- Genera resúmenes cortos (50 palabras) de libros usando GPT-3
- Publica primero el resumen y luego el título del libro como respuesta
- Evita repetir libros usando un sistema de registro
- Programa publicaciones automáticas cada 2 horas

## ⚙️ Configuración

### Requisitos

- Python 3.x
- Cuenta en [OpenAI](https://openai.com/)
- Cuenta en [Mastodon](https://mastodon.social/) (o cualquier instancia)

### Variables de entorno

Necesitarás configurar estas variables de entorno:

```
token_mast = "tu_token_de_acceso_mastodon"
openAiSecret = "tu_api_key_de_openai"
org_id = "tu_organization_id_de_openai"
```

### Archivos necesarios

1. `lista.txt`: Archivo con una lista de libros en formato Python (ej: `["Cien años de soledad - Gabriel García Márquez", ...]`)
2. `usados.txt`: Archivo para registrar los libros ya usados (puede empezar vacío)

## 🛠 Instalación

1. Clona el repositorio
2. Instala las dependencias:
   ```
   pip install openai requests mastodon.py schedule
   ```
3. Configura las variables de entorno
4. Prepara los archivos `lista.txt` y `usados.txt`
5. Ejecuta el bot:
   ```
   python bot.py
   ```

## 📝 Uso

El bot se ejecutará automáticamente y:
1. Seleccionará un libro aleatorio no usado
2. Generará un resumen con OpenAI
3. Publicará el resumen en Mastodon
4. Después de 15 minutos, publicará el título del libro como respuesta
5. Repetirá el proceso cada 2 horas

## 📄 Estructura de archivos

- `bot.py`: Código principal del bot
- `lista.txt`: Lista de libros disponibles
- `usados.txt`: Registro de libros ya publicados

## 📜 Licencia

Este proyecto está bajo la licencia MIT. Ver el archivo LICENSE para más detalles.

---

Hecho con ❤️ usando Python, OpenAI y Mastodon
