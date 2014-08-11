from datapackage import DataPackage
from nose.tools import raises


def test_get_name():
    dpkg = DataPackage("tests/test.dpkg")
    assert dpkg.name == "test.dpkg"


@raises(KeyError)
def test_get_missing_name():
    dpkg = DataPackage("tests/test.dpkg")
    del dpkg.descriptor['name']
    dpkg.name


@raises(KeyError)
def test_get_empty_name():
    dpkg = DataPackage("tests/test.dpkg")
    dpkg.descriptor['name'] = ""
    dpkg.name


@raises(KeyError)
def test_get_empty_name2():
    dpkg = DataPackage("tests/test.dpkg")
    dpkg.descriptor['name'] = None
    dpkg.name


def test_set_name():
    dpkg = DataPackage("tests/test.dpkg")
    dpkg.name = "foo"
    assert dpkg.name == "foo"


@raises(ValueError)
def test_set_empty_name():
    dpkg = DataPackage("tests/test.dpkg")
    dpkg.name = ""


@raises(ValueError)
def test_set_empty_name2():
    dpkg = DataPackage("tests/test.dpkg")
    dpkg.name = None


def test_get_license():
    dpkg = DataPackage("tests/test.dpkg")
    assert dpkg.license == "ODC-BY"


def test_get_licenses():
    dpkg = DataPackage("tests/test.dpkg")
    licenses = dpkg.licenses
    assert len(licenses) == 1
    assert licenses[0]["type"] == "ODC-BY"
    assert licenses[0]["url"] == "http://opendefinition.org/licenses/odc-by"


@raises(KeyError)
def test_get_missing_license():
    dpkg = DataPackage("tests/test.dpkg")
    del dpkg.descriptor['license']
    dpkg.license


@raises(KeyError)
def test_get_missing_licenses():
    dpkg = DataPackage("tests/test.dpkg")
    del dpkg.descriptor['license']
    dpkg.licenses


@raises(KeyError)
def test_get_license_and_licenses():
    dpkg = DataPackage("tests/test.dpkg")
    dpkg.descriptor['licenses'] = [
        {"type": "ODC-BY", "url": "http://opendefinition.org/licenses/odc-by"}]
    dpkg._get_licenses()


def test_get_datapackage_version():
    dpkg = DataPackage("tests/test.dpkg")
    assert dpkg.datapackage_version == "1.0-beta.10"


@raises(KeyError)
def test_get_missing_datapackage_version():
    dpkg = DataPackage("tests/test.dpkg")
    del dpkg.descriptor['datapackage_version']
    dpkg.datapackage_version


@raises(KeyError)
def test_get_empty_datapackage_version():
    dpkg = DataPackage("tests/test.dpkg")
    dpkg.descriptor['datapackage_version'] = ""
    dpkg.datapackage_version


@raises(KeyError)
def test_get_empty_datapackage_version2():
    dpkg = DataPackage("tests/test.dpkg")
    dpkg.descriptor['datapackage_version'] = None
    dpkg.datapackage_version