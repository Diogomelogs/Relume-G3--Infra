import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from relluna.services.ingestion.api import app

from dotenv import load_dotenv
load_dotenv()



# ------------------------------------------------------------------
# CONFIGURAÇÃO DE AMBIENTE PARA TESTES
# ------------------------------------------------------------------

# garante que uploads vão para um diretório gravável
TEST_UPLOAD_DIR = Path(__file__).resolve().parent / ".uploads"
TEST_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
os.environ["RELLUNA_UPLOAD_DIR"] = str(TEST_UPLOAD_DIR)

# garante que a raiz do projeto esteja no PYTHONPATH
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ------------------------------------------------------------------
# FAKE mongo_store (ANTES de importar a app)
# ------------------------------------------------------------------

import relluna.infra.mongo_store as real_mongo
from tests.fakes import fake_mongo_store

real_mongo.init = fake_mongo_store.init
real_mongo.close = fake_mongo_store.close
real_mongo.save = fake_mongo_store.save
real_mongo.get = fake_mongo_store.get
real_mongo.list_all = fake_mongo_store.list_all
real_mongo.count_all = fake_mongo_store.count_all

# ------------------------------------------------------------------
# IMPORT DA APP (DEPOIS DE CONFIGURAR O AMBIENTE)
# ------------------------------------------------------------------

from relluna.services.ingestion.api import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as client:
        yield client

