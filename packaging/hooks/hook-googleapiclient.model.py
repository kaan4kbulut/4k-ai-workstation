# pyinstaller-hooks-contrib'deki kancayı geçersiz kılar: ~500 Google API tanımı (~110 MB) yerine
# yalnızca uygulamanın kullandığı Drive v3 tanımını pakete ekler.
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

datas = copy_metadata("google_api_python_client")
datas += collect_data_files("googleapiclient.discovery_cache", includes=["documents/drive.v3.json"])
