"""
upload_gdrive.py — Sube un archivo .doc al Google Drive de ACL Chile
Uso: python scripts/upload_gdrive.py "Cencosud/SRE Semi Senior/challenge-xxx.doc"
"""
import sys
import os
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ID de la carpeta raíz en Google Drive
ROOT_FOLDER_ID = "1etoKNfcV3e5E0cMzDDghpsf_ysQRSpjx"

SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"


def authenticate() -> object:
    """Autentica con Google Drive (abre browser la primera vez)."""
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, name: str, parent_id: str) -> str:
    """Obtiene o crea una carpeta en Drive. Retorna el ID."""
    query = (
        f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    folder = service.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]},
        fields="id",
    ).execute()
    print(f"  Carpeta creada: {name}")
    return folder["id"]


def upload_challenge(file_path: str) -> None:
    """Sube el challenge al Drive respetando la estructura Cliente/Puesto/."""
    path = Path(file_path)
    if not path.exists():
        print(f"❌ Archivo no encontrado: {file_path}")
        sys.exit(1)

    # Estructura esperada: Cliente/Puesto/archivo.doc
    # path.parts[-3] = Cliente, path.parts[-2] = Puesto, path.parts[-1] = archivo
    parts = path.parts
    if len(parts) < 3:
        print("❌ Ruta inválida. Usar formato: Cliente/Puesto/archivo.doc")
        sys.exit(1)

    cliente = parts[-3]
    puesto  = parts[-2]
    archivo = parts[-1]

    print(f"\nSubiendo challenge a Google Drive...")
    print(f"   Cliente : {cliente}")
    print(f"   Puesto  : {puesto}")
    print(f"   Archivo : {archivo}")

    service = authenticate()

    # Crear/obtener carpetas en Drive
    cliente_id = get_or_create_folder(service, cliente, ROOT_FOLDER_ID)
    puesto_id  = get_or_create_folder(service, puesto, cliente_id)

    # Verificar si ya existe el archivo (para actualizar en vez de duplicar)
    query = f"name='{archivo}' and '{puesto_id}' in parents and trashed=false"
    existing = service.files().list(q=query, fields="files(id, name)").execute().get("files", [])

    media = MediaFileUpload(str(path), mimetype="application/msword", resumable=True)

    if existing:
        file_id = existing[0]["id"]
        service.files().update(fileId=file_id, media_body=media).execute()
        print(f"  OK - Archivo actualizado: {archivo}")
    else:
        service.files().create(
            body={"name": archivo, "parents": [puesto_id]},
            media_body=media,
            fields="id",
        ).execute()
        print(f"  OK - Archivo subido: {archivo}")

    print(f"\n  Ver en Drive: https://drive.google.com/drive/folders/{puesto_id}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/upload_gdrive.py <ruta_relativa_al_challenge>")
        print("Ejemplo: python scripts/upload_gdrive.py \"Cencosud/SRE Semi Senior/challenge-sre-semisanior.doc\"")
        sys.exit(1)
    upload_challenge(sys.argv[1])
