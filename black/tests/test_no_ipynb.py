import pytest
import os

from tests.util import THIS_DIR
from black import main, jupyter_dependencies_are_installed
from click.testing import CliRunner
from _pytest.tmpdir import tmpdir

pytestmark = pytest.mark.no_jupyter

runner = CliRunner()


def test_ipynb_diff_with_no_change_single() -> None:
    jupyter_dependencies_are_installed.cache_clear()
    path = THIS_DIR / "data/notebook_trailing_newline.ipynb"
    result = runner.invoke(main, [str(path)])
    expected_output = (
        "Skipping .ipynb files as Jupyter dependencies are not installed.\n"
        "You can fix this by running ``pip install black[jupyter]``\n"
    )
    assert expected_output in result.output


def test_ipynb_diff_with_no_change_dir(tmpdir: tmpdir) -> None:
    jupyter_dependencies_are_installed.cache_clear()
    runner = CliRunner()
    nb = os.path.join("tests", "data", "notebook_trailing_newline.ipynb")
    tmp_nb = tmpdir / "notebook.ipynb"
    with open(nb) as src, open(tmp_nb, "w") as dst:
        dst.write(src.read())
    result = runner.invoke(main, [str(tmpdir)])
    expected_output = (
        "Skipping .ipynb files as Jupyter dependencies are not installed.\n"
        "You can fix this by running ``pip install black[jupyter]``\n"
    )
    assert expected_output in result.output
