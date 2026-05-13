"""Testa o endpoint de compliance e exibe o retorno formatado."""
import json
import urllib.request

CNPJ = "04632844000188"
url = f"http://localhost:8001/v1/compliance/am/{CNPJ}"

with urllib.request.urlopen(url) as resp:
    data = json.loads(resp.read().decode("utf-8"))

print(json.dumps(data, indent=2, ensure_ascii=False))
