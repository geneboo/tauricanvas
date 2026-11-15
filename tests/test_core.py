from pathlib import Path
import shutil, pytest
from tauricanvas.utilities.fs import snake
from tauricanvas.contract.core import map_type
from tauricanvas.inspection.rust import inspect
def test_names():assert snake('ListRecords')=='list_records'
def test_types():assert map_type('Result<Vec<Option<String>>, E>')['item']['optional']
@pytest.mark.skipif(shutil.which("cargo") is None, reason="Cargo unavailable on host")
def test_inspection():
 r=inspect(Path('tests/fixtures/simple_records_engine'));assert {'list_records','get_record','save_record'}<={f.name for f in r.functions};assert next(f for f in r.functions if f.name=='raw_pointer').classification=='unsupported_signature'
