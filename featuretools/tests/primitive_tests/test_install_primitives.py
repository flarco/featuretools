import os
import shutil
import subprocess

import pytest

import featuretools
from featuretools.primitives.base import PrimitiveBase
from featuretools.primitives.install import (
    extract_archive,
    get_installation_dir,
    get_installation_temp_dir,
    list_primitive_files,
    load_primitive_from_file,
    install_primitives
)

try:
    from builtins import reload
except Exception:
    from importlib import reload


@pytest.fixture(scope='module')
def this_dir():
    return os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope='module')
def primitives_to_install_dir(this_dir):
    return os.path.join(this_dir, "primitives_to_install")


@pytest.fixture(scope='module')
def bad_primitives_files_dir(this_dir):
    return os.path.join(this_dir, "bad_primitive_files")


@pytest.fixture
def amazon_path_s3():
    return "s3://featuretools-static/primitives_to_install.tar.gz"


@pytest.fixture
def amazon_path_http():
    return "https://s3.amazonaws.com/featuretools-static/primitives_to_install.tar.gz"


@pytest.fixture
def install_via_cli():
    return "INSTALL_VIA_CLI"


@pytest.fixture
def install_via_module():
    return "INSTALL_VIA_MODULE"


@pytest.fixture
def install_path(request):
    return request.getfixturevalue(request.param)


@pytest.mark.parametrize("install_path", [
    ("primitives_to_install_dir"),
    ("amazon_path_s3"),
    ("amazon_path_http"),
    ("install_via_cli"),
    ("install_via_module"),
], indirect=True)
def test_install_primitives(install_path, primitives_to_install_dir):
    installation_dir = get_installation_dir()
    data_dir = featuretools.config.get("primitive_data_folder")
    custom_max_file = os.path.join(installation_dir, "custom_max.py")
    custom_mean_file = os.path.join(installation_dir, "custom_mean.py")
    custom_sum_file = os.path.join(installation_dir, "custom_sum.py")
    data_file = os.path.join(data_dir, "_pytest_test.csv")

    # make sure primitive files aren't there e.g from a failed run
    for p in [custom_max_file, custom_mean_file, custom_sum_file, data_file]:
        try:
            os.unlink(p)
        except Exception:
            pass

    # handle install via command line as a special case
    if install_path == "INSTALL_VIA_CLI":
        subprocess.check_output(['featuretools', 'install', '--no-prompt', primitives_to_install_dir])
    elif install_path == "INSTALL_VIA_MODULE":
        subprocess.check_output(['python', '-m', 'featuretools', 'install', '--no-prompt', primitives_to_install_dir])
    else:
        install_primitives(install_path, prompt=False)

    # must reload submodule for it to work
    reload(featuretools.primitives.installed)
    from featuretools.primitives.installed import CustomMax, CustomSum, CustomMean  # noqa: F401

    files = list_primitive_files(installation_dir)
    assert {custom_max_file, custom_mean_file, custom_sum_file}.issubset(set(files))
    if install_path in [primitives_to_install_dir, "INSTALL_VIA_CLI", "INSTALL_VIA_MODULE"]:
        assert os.path.exists(data_file)
        os.unlink(data_file)

    # then delete to clean up
    for f in [custom_max_file, custom_mean_file, custom_sum_file]:
        os.unlink(f)


def test_list_primitive_files(primitives_to_install_dir):
    files = list_primitive_files(primitives_to_install_dir)
    custom_max_file = os.path.join(primitives_to_install_dir, "custom_max.py")
    custom_mean_file = os.path.join(primitives_to_install_dir, "custom_mean.py")
    custom_sum_file = os.path.join(primitives_to_install_dir, "custom_sum.py")
    assert {custom_max_file, custom_mean_file, custom_sum_file}.issubset(set(files))


def test_load_primitive_from_file(primitives_to_install_dir):
    primitve_file = os.path.join(primitives_to_install_dir, "custom_max.py")
    primitive_name, primitive_obj = load_primitive_from_file(primitve_file)
    assert issubclass(primitive_obj, PrimitiveBase)


def test_errors_more_than_one_primitive_in_file(bad_primitives_files_dir):
    primitive_file = os.path.join(bad_primitives_files_dir, "multiple_primitives.py")
    error_text = 'More than one primitive defined in file %s' % primitive_file
    with pytest.raises(RuntimeError, match=error_text):
        load_primitive_from_file(primitive_file)


def test_errors_no_primitive_in_file(bad_primitives_files_dir):
    primitive_file = os.path.join(bad_primitives_files_dir, "no_primitives.py")
    error_text = 'No primitive defined in file %s' % primitive_file
    with pytest.raises(RuntimeError, match=error_text):
        load_primitive_from_file(primitive_file)


def test_cleans_up_tmp_dir_on_error(bad_primitives_files_dir):
    tmp_dir = get_installation_temp_dir()
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)

    error_text = "More than one primitive defined in file "\
                 "{}/multiple_primitives\\.py".format(bad_primitives_files_dir)
    with pytest.raises(RuntimeError, match=error_text):
        install_primitives(bad_primitives_files_dir, prompt=False)
    assert not os.path.exists(tmp_dir)


def test_extract_non_archive_errors(bad_primitives_files_dir):
    primitive_file = os.path.join(bad_primitives_files_dir, "no_primitives.py")
    error_text = "Cannot extract archive from %s. Must provide archive ending in .tar or .tar.gz" % primitive_file
    with pytest.raises(RuntimeError, match=error_text):
        extract_archive(primitive_file)


def test_install_packages_from_requirements(primitives_to_install_dir):
    def pip_freeze():
        output = subprocess.check_output(['pip', 'freeze'])
        if not isinstance(output, str):
            output = output.decode()
        return output

    # make sure dummy module isn't installed
    if "featuretools-pip-tester" in pip_freeze():
        subprocess.check_call(["pip", "uninstall", "-y", "featuretools-pip-tester"])
    assert "featuretools-pip-tester" not in pip_freeze()

    # generate requirements file with correct path
    requirements_path = os.path.join(primitives_to_install_dir, "requirements.txt")
    with open(requirements_path, 'w') as f:
        f.write(os.path.join(primitives_to_install_dir, "featuretools_pip_tester"))

    installation_dir = get_installation_dir()
    data_dir = featuretools.config.get("primitive_data_folder")
    custom_max_file = os.path.join(installation_dir, "custom_max.py")
    custom_mean_file = os.path.join(installation_dir, "custom_mean.py")
    custom_sum_file = os.path.join(installation_dir, "custom_sum.py")
    data_file = os.path.join(data_dir, "_pytest_test.csv")

    # make sure primitive files aren't there e.g from a failed run
    for p in [custom_max_file, custom_mean_file, custom_sum_file, data_file]:
        try:
            os.unlink(p)
        except Exception:
            pass

    install_primitives(primitives_to_install_dir, prompt=False)

    # must reload submodule for it to work
    reload(featuretools.primitives.installed)
    from featuretools.primitives.installed import CustomMax, CustomSum, CustomMean  # noqa: F401

    files = list_primitive_files(installation_dir)
    assert {custom_max_file, custom_mean_file, custom_sum_file}.issubset(set(files))
    assert os.path.exists(data_file)
    os.unlink(data_file)
    os.unlink(requirements_path)

    # then delete to clean up
    for f in [custom_max_file, custom_mean_file, custom_sum_file]:
        os.unlink(f)

    assert "featuretools-pip-tester" in pip_freeze()
    subprocess.check_call(["pip", "uninstall", "-y", "featuretools-pip-tester"])
